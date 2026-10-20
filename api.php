<?php
// Community API for the atlas.
//   GET  api.php?action=state            vote tallies, your votes, approved community GIFs, flagged GIFs
//   POST api.php?action=vote             JSON {animation, target, value: 1 | -1 | 0}
//   POST api.php?action=submit           multipart: animation, replaces?, url | file, note?, name?
//                                        (a url is downloaded and stored like an upload; nothing is public until approved)
//   GET  api.php?action=file&id=N        an approved uploaded GIF
// Voters are identified by a random token the page keeps in localStorage and sends as X-Voter-Token.
declare(strict_types=1);
require __DIR__ . '/lib/bootstrap.php';

header('X-Content-Type-Options: nosniff');
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin && in_array($origin, (array) cfg('allowed_origins'), true)) {
    header('Access-Control-Allow-Origin: ' . $origin);
    header('Vary: Origin');
    header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type, X-Voter-Token');
    header('Access-Control-Max-Age: 86400');
}
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') exit;

function out($data, int $code = 200): never
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

function fail(string $msg, int $code = 400): never { out(['error' => $msg], $code); }

function voter(): ?string
{
    $t = $_SERVER['HTTP_X_VOTER_TOKEN'] ?? '';
    return preg_match('/^[A-Za-z0-9_-]{16,64}$/', $t) ? h('voter:' . $t) : null;
}

$action = $_GET['action'] ?? '';
try {
    switch ($action) {
        case 'state': state(); break;
        case 'vote': vote(); break;
        case 'submit': submit(); break;
        case 'file': serve_file(); break;
        default: fail('unknown action', 404);
    }
} catch (Throwable $e) {
    error_log('api.php: ' . $e);
    fail('server error', 500);
}

function state(): void
{
    $pdo = db();
    $tally = [];
    foreach ($pdo->query('SELECT target, SUM(CASE WHEN value > 0 THEN 1 ELSE 0 END) up, SUM(CASE WHEN value < 0 THEN 1 ELSE 0 END) down FROM votes GROUP BY target') as $r) {
        $tally[$r['target']] = [(int) $r['up'], (int) $r['down']];
    }
    $mine = [];
    if ($v = voter()) {
        $s = $pdo->prepare('SELECT target, value FROM votes WHERE voter = ?');
        $s->execute([$v]);
        foreach ($s as $r) $mine[$r['target']] = (int) $r['value'];
    }
    $community = [];
    // Only approved, server-stored files are ever public. mode 'replace' rows take the place of the library GIF in `replaces`.
    foreach ($pdo->query("SELECT id, animation, replaces, mode, url, mime, note, submitter, source FROM submissions WHERE status = 'approved' AND kind = 'file' ORDER BY id") as $r) {
        $community[$r['animation']][] = [
            'id' => (int) $r['id'],
            'target' => 'sub:' . $r['id'],
            'replaces' => $r['replaces'],
            'mode' => $r['replaces'] && $r['mode'] === 'replace' ? 'replace' : 'add',
            'src' => 'api.php?action=file&id=' . $r['id'],
            'source_url' => $r['url'],
            'mime' => $r['mime'],
            'note' => $r['note'],
            'by' => $r['source'] === 'search' ? 'search' : ($r['submitter'] ?: 'anonymous'),
        ];
    }
    $flagged = [];
    foreach ($pdo->query('SELECT target FROM replacement_queue') as $r) $flagged[] = $r['target'];
    out(['tally' => (object) $tally, 'mine' => (object) $mine, 'community' => (object) $community, 'flagged' => $flagged, 'max_upload' => cfg('max_upload_bytes')]);
}

function vote(): void
{
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') fail('POST only', 405);
    $v = voter() ?? fail('missing voter token');
    $in = json_decode((string) file_get_contents('php://input'), true) ?: [];
    $animation = (string) ($in['animation'] ?? '');
    $target = (string) ($in['target'] ?? '');
    $value = (int) ($in['value'] ?? 0);
    if (!isset(library()[$animation])) fail('unknown animation');
    if (!in_array($value, [-1, 0, 1], true)) fail('bad value');
    if (preg_match('/^sub:(\d+)$/', $target, $m)) {
        $s = db()->prepare("SELECT id FROM submissions WHERE id = ? AND animation = ? AND status = 'approved'");
        $s->execute([(int) $m[1], $animation]);
        if (!$s->fetch()) fail('unknown GIF');
    } elseif (!library_gif($animation, $target)) {
        fail('unknown GIF');
    }
    if (!rate_ok('vote', (int) cfg('votes_per_hour'))) fail('too many votes, try again later', 429);
    $pdo = db();
    $pdo->beginTransaction();
    $pdo->prepare('DELETE FROM votes WHERE target = ? AND voter = ?')->execute([$target, $v]);
    if ($value !== 0) {
        $pdo->prepare('INSERT INTO votes (target, animation, voter, ip_hash, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)')
            ->execute([$target, $animation, $v, h(client_ip()), $value, now(), now()]);
    }
    update_flag($target, $animation);
    $pdo->commit();
    $s = $pdo->prepare('SELECT SUM(CASE WHEN value > 0 THEN 1 ELSE 0 END) up, SUM(CASE WHEN value < 0 THEN 1 ELSE 0 END) down FROM votes WHERE target = ?');
    $s->execute([$target]);
    $t = $s->fetch();
    $q = $pdo->prepare('SELECT 1 FROM replacement_queue WHERE target = ?');
    $q->execute([$target]);
    out(['target' => $target, 'up' => (int) $t['up'], 'down' => (int) $t['down'], 'mine' => $value, 'flagged' => (bool) $q->fetch()]);
}

function submit(): void
{
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') fail('POST only', 405);
    $v = voter() ?? fail('missing voter token');
    if (($_POST['website'] ?? '') !== '') out(['ok' => true]); // honeypot: bots fill every field
    $animation = (string) ($_POST['animation'] ?? '');
    if (!isset(library()[$animation])) fail('unknown animation');
    $replaces = trim((string) ($_POST['replaces'] ?? ''));
    if ($replaces !== '' && !library_gif($animation, $replaces)) fail('unknown GIF to replace');
    $note = mb_substr(trim((string) ($_POST['note'] ?? '')), 0, 500);
    $name = mb_substr(trim((string) ($_POST['name'] ?? '')), 0, 60);
    $url = trim((string) ($_POST['url'] ?? ''));
    $file = $_FILES['file'] ?? null;
    $hasFile = $file && ($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_NO_FILE;
    if ($hasFile === ($url !== '')) fail('send either a URL or a file');
    if (!rate_ok('submit', (int) cfg('submissions_per_hour'))) fail('too many submissions, try again later', 429);

    if ($url !== '') {
        if (strlen($url) > 1000 || !preg_match('#^https?://[^\s/$.?\#].[^\s]*$#i', $url)) fail('that does not look like a web address');
        // Linked GIFs are downloaded and stored here too, so what gets approved is exactly what is shown.
        try { $m = fetch_media($url); } catch (RuntimeException $e) { fail($e->getMessage()); }
        $row = ['kind' => 'file', 'url' => $url] + $m;
    } else {
        if ($file['error'] === UPLOAD_ERR_INI_SIZE || $file['error'] === UPLOAD_ERR_FORM_SIZE) fail('file is too large');
        if ($file['error'] !== UPLOAD_ERR_OK || !is_uploaded_file($file['tmp_name'])) fail('upload failed');
        if ($file['size'] > cfg('max_upload_bytes')) fail('file is too large');
        $media = sniff_media((string) file_get_contents($file['tmp_name'], false, null, 0, 16));
        if (!$media) fail('only GIF, WebP or MP4 files are accepted');
        // Stored under a random name with a non-executable extension; served only through api.php/admin.php.
        $stored = bin2hex(random_bytes(16)) . '.' . $media[1] . '.upload';
        if (!move_uploaded_file($file['tmp_name'], upload_dir() . '/' . $stored)) fail('could not store file', 500);
        $row = ['kind' => 'file', 'url' => null, 'file' => $stored, 'mime' => $media[0], 'bytes' => (int) $file['size']];
    }
    db()->prepare("INSERT INTO submissions (animation, replaces, kind, url, file, mime, bytes, note, submitter, source, voter, ip_hash, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'community', ?, ?, 'pending', ?)")
        ->execute([$animation, $replaces ?: null, $row['kind'], $row['url'], $row['file'], $row['mime'], $row['bytes'], $note, $name, $v, h(client_ip()), now()]);
    out(['ok' => true]);
}

function serve_file(): void
{
    $s = db()->prepare("SELECT file, mime FROM submissions WHERE id = ? AND kind = 'file' AND status = 'approved'");
    $s->execute([(int) ($_GET['id'] ?? 0)]);
    $r = $s->fetch() ?: fail('not found', 404);
    $path = upload_dir() . '/' . basename($r['file']);
    if (!is_file($path)) fail('not found', 404);
    header('Content-Type: ' . $r['mime']);
    header('Content-Length: ' . filesize($path));
    header('Cache-Control: public, max-age=86400');
    header('Content-Security-Policy: default-src \'none\'');
    readfile($path);
    exit;
}

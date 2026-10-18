<?php
// Owner review page: approve or reject community and search-found GIFs, see GIFs flagged by downvotes,
// run a replacement search on demand, and export approved GIFs as JSON.
declare(strict_types=1);
require __DIR__ . '/lib/bootstrap.php';

session_name('libadmin');
session_set_cookie_params(['httponly' => true, 'samesite' => 'Strict', 'secure' => !empty($_SERVER['HTTPS'])]);
session_start();
header('X-Frame-Options: DENY');
header('X-Content-Type-Options: nosniff');

function e(?string $s): string { return htmlspecialchars((string) $s, ENT_QUOTES, 'UTF-8'); }

$hash = (string) cfg('admin_password_hash');
if ($hash === '') {
    http_response_code(503);
    exit('Review page is disabled. Set admin_password_hash in config.php (see DEPLOY-XCLOUD.md).');
}
if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(16));
$csrf = $_SESSION['csrf'];
$post = $_SERVER['REQUEST_METHOD'] === 'POST';
if ($post && !hash_equals($csrf, (string) ($_POST['csrf'] ?? ''))) { http_response_code(400); exit('Stale form, reload the page.'); }

if ($post && isset($_POST['password'])) {
    if (!rate_ok('login', 10)) { http_response_code(429); exit('Too many attempts, try again later.'); }
    if (password_verify((string) $_POST['password'], $hash)) {
        session_regenerate_id(true);
        $_SESSION['admin'] = true;
    }
    header('Location: admin.php');
    exit;
}

if (empty($_SESSION['admin'])) {
    ?><!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Library review</title>
    <style>body{font:15px system-ui;max-width:360px;margin:15vh auto;padding:0 16px}input,button{font:inherit;padding:8px;width:100%;margin-top:8px;box-sizing:border-box}</style>
    <h1>Library review</h1><form method="post"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><input type="password" name="password" placeholder="Password" autofocus required><button>Sign in</button></form><?php
    exit;
}

$pdo = db();

// Uploaded file preview (any status) for the signed-in owner
if (isset($_GET['file'])) {
    $s = $pdo->prepare("SELECT file, mime FROM submissions WHERE id = ? AND kind = 'file'");
    $s->execute([(int) $_GET['file']]);
    $r = $s->fetch();
    $path = $r ? upload_dir() . '/' . basename($r['file']) : '';
    if (!$r || !is_file($path)) { http_response_code(404); exit; }
    header('Content-Type: ' . $r['mime']);
    header("Content-Security-Policy: default-src 'none'");
    readfile($path);
    exit;
}

if (isset($_GET['export'])) {
    $rows = $pdo->query("SELECT id, animation, replaces, kind, url, file, mime, note, submitter, source, created_at, reviewed_at FROM submissions WHERE status = 'approved' ORDER BY animation, id")->fetchAll();
    foreach ($rows as &$r) if ($r['kind'] === 'file') $r['download'] = 'api.php?action=file&id=' . $r['id'];
    header('Content-Type: application/json');
    header('Content-Disposition: attachment; filename="approved-gifs.json"');
    echo json_encode($rows, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

$msg = '';
if ($post) {
    $id = (int) ($_POST['id'] ?? 0);
    switch ($_POST['do'] ?? '') {
        case 'approve':
        case 'reject':
            $pdo->prepare('UPDATE submissions SET status = ?, reviewed_at = ? WHERE id = ?')->execute([$_POST['do'] === 'approve' ? 'approved' : 'rejected', now(), $id]);
            break;
        case 'delete':
            $s = $pdo->prepare('SELECT file FROM submissions WHERE id = ?');
            $s->execute([$id]);
            if (($f = $s->fetchColumn()) && is_file(upload_dir() . '/' . basename($f))) unlink(upload_dir() . '/' . basename($f));
            $pdo->prepare('DELETE FROM submissions WHERE id = ?')->execute([$id]);
            break;
        case 'search':
            $msg = search_replacements((string) $_POST['target'], (string) $_POST['animation']);
            break;
        case 'unflag':
            $pdo->prepare('DELETE FROM replacement_queue WHERE target = ?')->execute([(string) $_POST['target']]);
            break;
    }
    $_SESSION['msg'] = $msg;
    header('Location: admin.php?' . http_build_query(['status' => $_GET['status'] ?? 'pending']));
    exit;
}
$msg = $_SESSION['msg'] ?? '';
unset($_SESSION['msg']);

$status = in_array($_GET['status'] ?? '', ['pending', 'approved', 'rejected'], true) ? $_GET['status'] : 'pending';
$counts = [];
foreach ($pdo->query('SELECT status, COUNT(*) n FROM submissions GROUP BY status') as $r) $counts[$r['status']] = (int) $r['n'];
$s = $pdo->prepare('SELECT * FROM submissions WHERE status = ? ORDER BY id DESC LIMIT 200');
$s->execute([$status]);
$subs = $s->fetchAll();
$flagged = $pdo->query('SELECT q.*, (SELECT SUM(CASE WHEN value > 0 THEN 1 ELSE 0 END) FROM votes v WHERE v.target = q.target) up, (SELECT SUM(CASE WHEN value < 0 THEN 1 ELSE 0 END) FROM votes v WHERE v.target = q.target) down FROM replacement_queue q ORDER BY flagged_at DESC')->fetchAll();
$lib = library();

function media(string $src, ?string $mime): string
{
    $isVideo = $mime === 'video/mp4' || preg_match('/\.mp4(\?|$)/i', $src);
    $isImg = $mime || preg_match('/\.(gif|webp|png|jpe?g)(\?|$)/i', $src) || preg_match('#//media\d*\.(giphy|tenor)\.com/#', $src);
    if ($isVideo) return '<video src="' . e($src) . '" autoplay loop muted playsinline></video>';
    if ($isImg) return '<img src="' . e($src) . '" alt="" loading="lazy" referrerpolicy="no-referrer">';
    return '<div class="nopreview">No inline preview. Open the link.</div>';
}
function form(string $do, string $label, array $fields, string $csrf, string $cls = ''): string
{
    $h = '<form method="post"><input type="hidden" name="csrf" value="' . e($csrf) . '"><input type="hidden" name="do" value="' . e($do) . '">';
    foreach ($fields as $k => $v) $h .= '<input type="hidden" name="' . e($k) . '" value="' . e((string) $v) . '">';
    return $h . '<button class="' . e($cls) . '">' . e($label) . '</button></form>';
}
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Library review</title>
<style>
body{font:14px/1.45 system-ui,sans-serif;margin:0;background:#f3f2ee;color:#1c1b19}
@media (prefers-color-scheme:dark){body{background:#17181a;color:#ecebe6}.card,.flag{background:#202125!important;border-color:#33343a!important}}
main{max-width:1100px;margin:0 auto;padding:16px}
nav{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
nav a{padding:6px 12px;border:1px solid #d8d5cc;border-radius:6px;text-decoration:none;color:inherit}
nav a.on{background:#1c1b19;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.card,.flag{background:#fff;border:1px solid #d8d5cc;border-radius:6px;padding:10px;display:grid;gap:6px;align-content:start;min-width:0}
.card img,.card video,.flag img{width:100%;border-radius:4px;background:#e9e7e1}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:6px}.pair small{display:block;color:#6b6860}
.nopreview{padding:24px 8px;text-align:center;color:#6b6860;border:1px dashed #d8d5cc;border-radius:4px}
.acts{display:flex;gap:6px;flex-wrap:wrap}.acts form{margin:0}
button{font:inherit;padding:5px 10px;border-radius:4px;border:1px solid #d8d5cc;background:#efece5;cursor:pointer}
button.ok{background:#2f7a6b;color:#fff;border-color:#2f7a6b}button.no{background:#c2412d;color:#fff;border-color:#c2412d}
a{overflow-wrap:anywhere}small{color:#6b6860}.msg{padding:8px 12px;background:#ffb02033;border-radius:6px;margin-bottom:12px}
h2{margin:24px 0 8px}
</style></head><body><main>
<h1>Library review</h1>
<?php if ($msg): ?><div class="msg"><?= e($msg) ?></div><?php endif; ?>
<nav>
<?php foreach (['pending', 'approved', 'rejected'] as $st): ?><a class="<?= $st === $status ? 'on' : '' ?>" href="?status=<?= $st ?>"><?= ucfirst($st) ?> (<?= $counts[$st] ?? 0 ?>)</a><?php endforeach; ?>
<a href="?export=1">Export approved JSON</a> <a href="./">Open atlas</a>
</nav>

<?php if ($flagged): ?>
<h2>Flagged by downvotes (<?= count($flagged) ?>)</h2>
<p><small>These library GIFs crossed the downvote threshold. Search candidates land in Pending with source “search”.</small></p>
<div class="grid">
<?php foreach ($flagged as $f): $a = $lib[$f['animation']] ?? null; $g = library_gif($f['animation'], $f['target']); ?>
<div class="flag">
  <b><?= e($a['name'] ?? $f['animation']) ?></b>
  <?php if (!empty($g['local'])): ?><img src="<?= e($g['local']) ?>" alt=""><?php endif; ?>
  <small>▲ <?= (int) $f['up'] ?> ▼ <?= (int) $f['down'] ?> · flagged <?= e($f['flagged_at']) ?><?= $f['searched_at'] ? ' · searched: ' . e($f['result']) : ' · not searched yet' ?></small>
  <a href="<?= e($g['page_url'] ?? '#') ?>" target="_blank" rel="noopener noreferrer"><?= e($g['title'] ?? $f['target']) ?></a>
  <div class="acts"><?= form('search', 'Search now', ['target' => $f['target'], 'animation' => $f['animation']], $csrf) ?><?= form('unflag', 'Keep this GIF', ['target' => $f['target']], $csrf) ?></div>
</div>
<?php endforeach; ?>
</div>
<?php endif; ?>

<h2><?= ucfirst($status) ?> submissions</h2>
<?php if (!$subs): ?><p><small>Nothing here.</small></p><?php endif; ?>
<div class="grid">
<?php foreach ($subs as $r): $a = $lib[$r['animation']] ?? null; $old = $r['replaces'] ? library_gif($r['animation'], $r['replaces']) : null;
  $src = $r['kind'] === 'file' ? 'admin.php?file=' . $r['id'] : (string) $r['url']; ?>
<div class="card">
  <b><?= e($a['name'] ?? $r['animation']) ?></b>
  <small><?= $r['source'] === 'search' ? 'Found by search' : 'From ' . e($r['submitter'] ?: 'anonymous') ?> · <?= e($r['created_at']) ?><?= $r['bytes'] ? ' · ' . round($r['bytes'] / 1024) . ' KB' : '' ?></small>
  <?php if ($old): ?>
    <div class="pair"><div><small>Current</small><?= !empty($old['local']) ? '<img src="' . e($old['local']) . '" alt="">' : '<div class="nopreview">no copy</div>' ?></div><div><small>Proposed</small><?= media($src, $r['mime']) ?></div></div>
  <?php else: ?><?= media($src, $r['mime']) ?><small>New GIF for this entry</small><?php endif; ?>
  <?php if ($r['kind'] === 'url'): ?><a href="<?= e($r['url']) ?>" target="_blank" rel="noopener noreferrer"><?= e($r['url']) ?></a><?php endif; ?>
  <?php if ($r['note']): ?><small><?= e($r['note']) ?></small><?php endif; ?>
  <div class="acts">
    <?php if ($r['status'] !== 'approved') echo form('approve', 'Approve', ['id' => $r['id']], $csrf, 'ok'); ?>
    <?php if ($r['status'] !== 'rejected') echo form('reject', 'Reject', ['id' => $r['id']], $csrf, 'no'); ?>
    <?= form('delete', 'Delete', ['id' => $r['id']], $csrf) ?>
  </div>
</div>
<?php endforeach; ?>
</div>
</main></body></html>

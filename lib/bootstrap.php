<?php
// Shared setup for index.php, api.php, admin.php and tools/*.php:
// config, database (SQLite by default, MySQL/MariaDB optional), library lookups and small helpers.
declare(strict_types=1);

const APP_ROOT = __DIR__ . '/..';

function cfg(?string $key = null)
{
    static $c = null;
    if ($c === null) {
        $c = [
            // 'sqlite' (zero setup, file in storage/) or 'mysql' (xCloud site database)
            'db_driver' => 'sqlite',
            'sqlite_path' => APP_ROOT . '/storage/library.sqlite',
            'mysql_host' => '127.0.0.1',
            'mysql_port' => 3306,
            'mysql_database' => '',
            'mysql_user' => '',
            'mysql_password' => '',
            // Folder for uploaded GIFs and the SQLite file. Keep it out of public reach (see .htaccess / DEPLOY-XCLOUD.md).
            'storage_dir' => APP_ROOT . '/storage',
            // password_hash() of the review page password; empty disables admin.php
            'admin_password_hash' => getenv('LIBRARY_ADMIN_PASSWORD_HASH') ?: '',
            // Random string used to hash IPs and voter tokens; set your own in config.php
            'secret' => getenv('LIBRARY_SECRET') ?: '',
            'max_upload_bytes' => 8 * 1024 * 1024,
            // Rate limits per IP per hour
            'votes_per_hour' => 300,
            'submissions_per_hour' => 10,
            // A library GIF is flagged for a replacement search once it has at least
            // flag_min_downvotes downvotes and (downvotes - upvotes) >= flag_net_score
            'flag_min_downvotes' => 3,
            'flag_net_score' => 2,
            // Replacement search providers (optional). Leave empty to skip a provider.
            'giphy_api_key' => getenv('GIPHY_API_KEY') ?: '',
            'tenor_api_key' => getenv('TENOR_API_KEY') ?: '',
            'search_candidates' => 4,
            // Other origins allowed to call api.php (e.g. the GitHub Pages copy of the atlas)
            'allowed_origins' => [],
        ];
        $file = APP_ROOT . '/config.php';
        if (is_file($file)) {
            $c = array_merge($c, (array) require $file);
        }
        if ($c['secret'] === '') {
            $c['secret'] = 'unset-secret-' . php_uname('n');
        }
    }
    return $key === null ? $c : ($c[$key] ?? null);
}

function db(): PDO
{
    static $pdo = null;
    if ($pdo) return $pdo;
    if (cfg('db_driver') === 'mysql') {
        $dsn = sprintf('mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4', cfg('mysql_host'), cfg('mysql_port'), cfg('mysql_database'));
        $pdo = new PDO($dsn, cfg('mysql_user'), cfg('mysql_password'), [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
    } else {
        $path = cfg('sqlite_path');
        if (!is_dir(dirname($path))) mkdir(dirname($path), 0775, true);
        $pdo = new PDO('sqlite:' . $path, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
        $pdo->exec('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON');
    }
    migrate($pdo);
    return $pdo;
}

function migrate(PDO $pdo): void
{
    $mysql = $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'mysql';
    $id = $mysql ? 'INT AUTO_INCREMENT PRIMARY KEY' : 'INTEGER PRIMARY KEY AUTOINCREMENT';
    $str = $mysql ? 'VARCHAR(191)' : 'TEXT';
    $tail = $mysql ? ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4' : '';
    $pdo->exec("CREATE TABLE IF NOT EXISTS votes (
        target $str NOT NULL, animation $str NOT NULL, voter CHAR(64) NOT NULL, ip_hash CHAR(64) NOT NULL,
        value SMALLINT NOT NULL, created_at $str NOT NULL, updated_at $str NOT NULL,
        PRIMARY KEY (target, voter))$tail");
    $pdo->exec("CREATE TABLE IF NOT EXISTS submissions (
        id $id, animation $str NOT NULL, replaces TEXT, kind VARCHAR(16) NOT NULL, url TEXT, file $str, mime VARCHAR(32),
        bytes INT, note TEXT, submitter $str, source VARCHAR(16) NOT NULL DEFAULT 'community', voter CHAR(64), ip_hash CHAR(64),
        status VARCHAR(16) NOT NULL DEFAULT 'pending', created_at $str NOT NULL, reviewed_at $str)$tail");
    $pdo->exec("CREATE TABLE IF NOT EXISTS replacement_queue (
        target $str NOT NULL PRIMARY KEY, animation $str NOT NULL, flagged_at $str NOT NULL, searched_at $str, result TEXT)$tail");
    $pdo->exec("CREATE TABLE IF NOT EXISTS hits (ip_hash CHAR(64) NOT NULL, action VARCHAR(16) NOT NULL, at INT NOT NULL)$tail");
    // mode: 'replace' = shown in place of the library GIF it replaces, 'add' = shown under Community GIFs
    $cols = $mysql
        ? array_column($pdo->query('SHOW COLUMNS FROM submissions')->fetchAll(), 'Field')
        : array_column($pdo->query('PRAGMA table_info(submissions)')->fetchAll(), 'name');
    if (!in_array('mode', $cols, true)) $pdo->exec("ALTER TABLE submissions ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'add'");
}

function now(): string { return gmdate('Y-m-d H:i:s'); }

function h(string $s): string { return hash_hmac('sha256', $s, cfg('secret')); }

function client_ip(): string { return $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0'; }

/** library.json, indexed by animation id */
function library(): array
{
    static $lib = null;
    if ($lib === null) {
        $d = json_decode((string) file_get_contents(APP_ROOT . '/library.json'), true);
        $lib = [];
        foreach ($d['animations'] as $a) $lib[$a['id']] = $a;
    }
    return $lib;
}

/**
 * Vote target for a library GIF: "<animation>|<local path, else media URL, else page URL>".
 * page_url alone is not unique (several Ultimate Frame Data GIFs share a character page). Community GIFs use "sub:<id>".
 */
function gif_key(string $animation, array $g): string
{
    return $animation . '|' . (($g['local'] ?? '') ?: (($g['media_url'] ?? '') ?: ($g['page_url'] ?? '')));
}

function library_gif(string $animation, string $target): ?array
{
    foreach (library()[$animation]['gifs'] ?? [] as $g) {
        if (gif_key($animation, $g) === $target) return $g;
    }
    return null;
}

/** True when the caller has made fewer than $limit $action requests in the last hour; records this one. */
function rate_ok(string $action, int $limit): bool
{
    $pdo = db();
    $ip = h(client_ip());
    $pdo->prepare('DELETE FROM hits WHERE at < ?')->execute([time() - 3600]);
    $s = $pdo->prepare('SELECT COUNT(*) FROM hits WHERE ip_hash = ? AND action = ? AND at >= ?');
    $s->execute([$ip, $action, time() - 3600]);
    if ((int) $s->fetchColumn() >= $limit) return false;
    $pdo->prepare('INSERT INTO hits (ip_hash, action, at) VALUES (?, ?, ?)')->execute([$ip, $action, time()]);
    return true;
}

/** Sniff GIF / WebP / MP4 from the first bytes; returns [mime, ext] or null. */
function sniff_media(string $head): ?array
{
    if (strncmp($head, 'GIF87a', 6) === 0 || strncmp($head, 'GIF89a', 6) === 0) return ['image/gif', 'gif'];
    if (substr($head, 0, 4) === 'RIFF' && substr($head, 8, 4) === 'WEBP') return ['image/webp', 'webp'];
    if (substr($head, 4, 4) === 'ftyp') return ['video/mp4', 'mp4'];
    return null;
}

/** True for a public IPv4/IPv6 address (blocks localhost, private, link-local and reserved ranges). */
function public_ip(string $ip): bool
{
    return (bool) filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE);
}

/**
 * Download a GIF / WebP / MP4 from a link and store it in upload_dir(), so the site never hotlinks
 * community media (a link could be swapped for something else after it was approved).
 * Accepts a direct media link or a page (Giphy, Tenor, …) whose og:video / og:image points at one.
 * Only public addresses are fetched, each redirect is re-checked, and the size is capped.
 * Returns ['file' => stored name, 'mime' => ..., 'bytes' => ...]; throws RuntimeException with a user-facing reason.
 */
function fetch_media(string $url, int $depth = 0): array
{
    if (!function_exists('curl_init')) throw new RuntimeException('this server cannot download links, upload the file instead');
    $max = (int) cfg('max_upload_bytes');
    for ($hop = 0; $hop < 5; $hop++) {
        $p = parse_url($url);
        $scheme = strtolower($p['scheme'] ?? '');
        $host = trim($p['host'] ?? '', '[]');
        if (!in_array($scheme, ['http', 'https'], true) || $host === '' || isset($p['user'])) throw new RuntimeException('that does not look like a web address');
        $port = (int) ($p['port'] ?? ($scheme === 'https' ? 443 : 80));
        if (!in_array($port, [80, 443], true)) throw new RuntimeException('that link uses an unsupported port');
        $ips = filter_var($host, FILTER_VALIDATE_IP) ? [$host] : (gethostbynamel($host) ?: []);
        if (!$ips) throw new RuntimeException('could not find that website');
        foreach ($ips as $ip) if (!public_ip($ip)) throw new RuntimeException('that address is not allowed');
        $body = '';
        $tooBig = false;
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            // Pin the checked address so DNS cannot change between the check and the request.
            CURLOPT_RESOLVE => ["$host:$port:" . (str_contains($ips[0], ':') ? '[' . $ips[0] . ']' : $ips[0])],
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_PROTOCOLS => CURLPROTO_HTTP | CURLPROTO_HTTPS,
            CURLOPT_CONNECTTIMEOUT => 8,
            CURLOPT_TIMEOUT => 25,
            CURLOPT_USERAGENT => 'Mozilla/5.0 (compatible; game-animation-library)',
            CURLOPT_HTTPHEADER => ['Accept: image/gif,image/webp,video/mp4,text/html;q=0.8,*/*;q=0.5'],
            CURLOPT_WRITEFUNCTION => function ($ch, $chunk) use (&$body, &$tooBig, $max) {
                $body .= $chunk;
                if (strlen($body) > $max) { $tooBig = true; return 0; }
                return strlen($chunk);
            },
        ]);
        curl_exec($ch);
        $code = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $location = (string) curl_getinfo($ch, CURLINFO_REDIRECT_URL);
        $err = curl_errno($ch);
        curl_close($ch);
        if ($tooBig) throw new RuntimeException('that file is too large');
        if ($code >= 300 && $code < 400 && $location !== '') { $url = $location; continue; }
        if ($err || $code >= 400 || $code === 0) throw new RuntimeException('could not download that link');
        if ($media = sniff_media(substr($body, 0, 16))) {
            $stored = bin2hex(random_bytes(16)) . '.' . $media[1] . '.upload';
            if (file_put_contents(upload_dir() . '/' . $stored, $body) === false) throw new RuntimeException('could not store file');
            return ['file' => $stored, 'mime' => $media[0], 'bytes' => strlen($body)];
        }
        // A page: follow its og:video / og:image once (Giphy and Tenor pages point at the GIF this way).
        if ($depth === 0 && preg_match_all('#<meta[^>]+(?:property|name)=["\'](og:video(?::secure_url|:url)?|og:image(?::secure_url|:url)?|twitter:image)["\'][^>]*>#i', $body, $m)) {
            $cands = [];
            foreach ($m[0] as $i => $tag) {
                if (preg_match('#content=["\']([^"\']+)#i', $tag, $c)) $cands[] = html_entity_decode($c[1]);
            }
            // Prefer animated formats over a still preview image.
            usort($cands, fn($a, $b) => (int) !preg_match('/\.(gif|webp|mp4)(\?|$)/i', $a) <=> (int) !preg_match('/\.(gif|webp|mp4)(\?|$)/i', $b));
            foreach ($cands as $c) {
                try { return fetch_media($c, 1); } catch (RuntimeException $e) {}
            }
        }
        throw new RuntimeException('no GIF, WebP or MP4 found at that link, upload the file or use a direct link');
    }
    throw new RuntimeException('that link redirects too many times');
}

function upload_dir(): string
{
    $dir = rtrim(cfg('storage_dir'), '/') . '/uploads';
    if (!is_dir($dir)) mkdir($dir, 0775, true);
    return $dir;
}

/** Flag or unflag a library GIF for a replacement search based on its current tally. */
function update_flag(string $target, string $animation): void
{
    if (strncmp($target, 'sub:', 4) === 0) return;
    $pdo = db();
    $s = $pdo->prepare('SELECT COALESCE(SUM(CASE WHEN value > 0 THEN 1 ELSE 0 END),0) up, COALESCE(SUM(CASE WHEN value < 0 THEN 1 ELSE 0 END),0) down FROM votes WHERE target = ?');
    $s->execute([$target]);
    $t = $s->fetch();
    $flag = $t['down'] >= cfg('flag_min_downvotes') && ($t['down'] - $t['up']) >= cfg('flag_net_score');
    $q = $pdo->prepare('SELECT target FROM replacement_queue WHERE target = ?');
    $q->execute([$target]);
    $queued = (bool) $q->fetch();
    if ($flag && !$queued) {
        $pdo->prepare('INSERT INTO replacement_queue (target, animation, flagged_at) VALUES (?, ?, ?)')->execute([$target, $animation, now()]);
    } elseif (!$flag && $queued) {
        $pdo->prepare('DELETE FROM replacement_queue WHERE target = ? AND searched_at IS NULL')->execute([$target]);
    }
}

function http_get_json(string $url): ?array
{
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 15, CURLOPT_USERAGENT => 'game-animation-library']);
        $body = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        if ($body === false || $code >= 400) return null;
    } else {
        $body = @file_get_contents($url, false, stream_context_create(['http' => ['timeout' => 15, 'header' => "User-Agent: game-animation-library\r\n"]]));
        if ($body === false) return null;
    }
    $j = json_decode($body, true);
    return is_array($j) ? $j : null;
}

/**
 * Search Giphy and/or Tenor for replacement candidates for one flagged GIF and store them
 * as pending submissions (source 'search') for the owner to review. Returns a short result line.
 */
function search_replacements(string $target, string $animation): string
{
    $a = library()[$animation] ?? null;
    if (!$a) return 'unknown animation';
    $game = $a['example_games'][0] ?? '';
    $query = trim($game . ' ' . $a['name']);
    $known = [];
    foreach ($a['gifs'] ?? [] as $g) array_push($known, $g['page_url'] ?? '', $g['media_url'] ?? '', $g['source_url'] ?? '');
    $pdo = db();
    $s = $pdo->prepare('SELECT url FROM submissions WHERE animation = ? AND url IS NOT NULL');
    $s->execute([$animation]);
    foreach ($s->fetchAll() as $r) $known[] = $r['url'];
    $found = [];
    $n = (int) cfg('search_candidates');
    if (cfg('giphy_api_key')) {
        $j = http_get_json('https://api.giphy.com/v1/gifs/search?' . http_build_query(['api_key' => cfg('giphy_api_key'), 'q' => $query, 'limit' => $n * 2, 'rating' => 'pg-13']));
        foreach ($j['data'] ?? [] as $g) {
            $media = $g['images']['fixed_width']['webp'] ?? $g['images']['fixed_width']['url'] ?? '';
            if ($media) $found[] = ['page' => $g['url'] ?? '', 'media' => $media, 'title' => $g['title'] ?? '', 'host' => 'Giphy'];
        }
    }
    if (cfg('tenor_api_key')) {
        $j = http_get_json('https://tenor.googleapis.com/v2/search?' . http_build_query(['key' => cfg('tenor_api_key'), 'q' => $query, 'limit' => $n * 2, 'media_filter' => 'tinygif,gif', 'contentfilter' => 'medium']));
        foreach ($j['results'] ?? [] as $g) {
            $media = $g['media_formats']['tinygif']['url'] ?? $g['media_formats']['gif']['url'] ?? '';
            if ($media) $found[] = ['page' => $g['itemurl'] ?? '', 'media' => $media, 'title' => $g['content_description'] ?? '', 'host' => 'Tenor'];
        }
    }
    $added = 0;
    $ins = $pdo->prepare("INSERT INTO submissions (animation, replaces, kind, url, file, mime, bytes, note, submitter, source, status, created_at) VALUES (?, ?, 'file', ?, ?, ?, ?, ?, ?, 'search', 'pending', ?)");
    foreach ($found as $f) {
        if ($added >= $n) break;
        if (in_array($f['media'], $known, true) || in_array($f['page'], $known, true)) continue;
        $known[] = $f['media'];
        try { $m = fetch_media($f['media']); } catch (RuntimeException $e) { continue; }
        $ins->execute([$animation, $target, $f['media'], $m['file'], $m['mime'], $m['bytes'], trim($f['title'] . ' · ' . $f['page'], ' ·'), $f['host'] . ' search: ' . $query, now()]);
        $added++;
    }
    // Without a provider the GIF stays queued, so it is searched once a key is added.
    if (!cfg('giphy_api_key') && !cfg('tenor_api_key')) return 'no search provider configured';
    $result = "$added candidates from \"$query\"";
    $pdo->prepare('UPDATE replacement_queue SET searched_at = ?, result = ? WHERE target = ?')->execute([now(), $result, $target]);
    return $result;
}

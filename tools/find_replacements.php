<?php
// Cron job: search Giphy/Tenor for replacements for every GIF flagged by downvotes that has not been searched yet.
// Candidates are stored as pending submissions (source "search") for review in admin.php.
//   php tools/find_replacements.php          # flagged GIFs not yet searched
//   php tools/find_replacements.php --all    # re-search every flagged GIF
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__ . '/../lib/bootstrap.php';

$all = in_array('--all', $argv, true);
$rows = db()->query('SELECT target, animation FROM replacement_queue' . ($all ? '' : ' WHERE searched_at IS NULL'))->fetchAll();
if (!$rows) { echo "Nothing to search.\n"; exit; }
foreach ($rows as $r) {
    echo $r['animation'], ' | ', $r['target'], ' -> ', search_replacements($r['target'], $r['animation']), "\n";
}

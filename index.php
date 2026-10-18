<?php
// Serves the atlas on a PHP host (xCloud): template.html + library.json, with community features pointed at api.php.
// Same output as build_page.py, so no build step is needed after a git pull.
declare(strict_types=1);
$dump = fn($o) => str_replace('</', '<\/', json_encode($o, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
$data = json_decode((string) file_get_contents(__DIR__ . '/library.json'), true);
$html = str_replace(
    ['__DATA__', '__CONFIG__'],
    [$dump($data), $dump(['api' => 'api.php'])],
    (string) file_get_contents(__DIR__ . '/template.html')
);
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: no-cache');
echo $html;

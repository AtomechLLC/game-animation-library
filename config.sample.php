<?php
// Copy to config.php on the server (config.php is git-ignored) and fill in.
// Anything left out uses the defaults in lib/bootstrap.php.
return [
    // Review page password. Generate the hash with:
    //   php -r "echo password_hash('your-password', PASSWORD_DEFAULT), PHP_EOL;"
    'admin_password_hash' => '',

    // Any long random string, e.g. from: php -r "echo bin2hex(random_bytes(32)), PHP_EOL;"
    'secret' => '',

    // SQLite needs no setup. To use the xCloud site database instead, switch to 'mysql' and fill in its details.
    'db_driver' => 'sqlite',
    // 'mysql_host' => '127.0.0.1',
    // 'mysql_port' => 3306,
    // 'mysql_database' => '',
    // 'mysql_user' => '',
    // 'mysql_password' => '',

    // Where uploads and the SQLite file live. Outside the web root is safest, e.g. '/var/www/example.com/library-data'.
    // 'storage_dir' => __DIR__ . '/storage',
    // 'sqlite_path' => __DIR__ . '/storage/library.sqlite',

    // Replacement search for downvoted GIFs (both optional; free keys from developers.giphy.com and Google Cloud's Tenor API).
    'giphy_api_key' => '',
    'tenor_api_key' => '',

    // A library GIF is flagged once it has this many downvotes and is this far below its upvotes.
    'flag_min_downvotes' => 3,
    'flag_net_score' => 2,

    // Let the GitHub Pages copy use this API too (it must also be built with LIBRARY_API_URL).
    // 'allowed_origins' => ['https://atomechllc.github.io'],
];

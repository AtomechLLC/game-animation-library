# Deploying to xCloud

The atlas runs on xCloud as a **Custom PHP** site cloned from this GitHub repo. PHP renders the page
(`index.php`), and `api.php` stores votes and GIF suggestions in SQLite (default) or the site's MySQL database.
GitHub Pages keeps working unchanged as a read-only copy.

Needs PHP 8.1+ with `pdo_sqlite` (or `pdo_mysql`) and `curl` (only for the replacement search). xCloud's PHP stacks include these.

## 1. Create the site

1. In xCloud, open your server, click **New Site**, choose **Custom PHP**, then **Clone a Git Repository**.
2. Connect GitHub and pick `atomechllc/game-animation-library`, branch `main`.
3. Leave the web root as the repository root. A database is optional (see step 3).
4. Turn on **Push to deploy** if you want every push to `main` to update the site.

## 2. Add the private config

SSH (or use xCloud's file manager) into the site folder and run:

```bash
cp config.sample.php config.php
php -r "echo password_hash('CHOOSE-A-PASSWORD', PASSWORD_DEFAULT), PHP_EOL;"   # paste into admin_password_hash
php -r "echo bin2hex(random_bytes(32)), PHP_EOL;"                              # paste into secret
mkdir -p ../library-data && chmod 775 ../library-data
```

Then edit `config.php`:

- `admin_password_hash` and `secret` from the two commands above.
- `storage_dir` and `sqlite_path` pointing **outside the web root**, e.g.
  `'storage_dir' => dirname(__DIR__) . '/library-data', 'sqlite_path' => dirname(__DIR__) . '/library-data/library.sqlite'`.
  That folder must be writable by the site's PHP user (it is if you created it as the site user).
- Optional: `giphy_api_key` and/or `tenor_api_key` to turn on automatic replacement search for downvoted GIFs.

`config.php` and `storage/` are git-ignored, so deploys never overwrite them.

## 3. Database (optional)

SQLite needs nothing more. To use the xCloud site database instead, set `'db_driver' => 'mysql'` and fill in
`mysql_host`, `mysql_database`, `mysql_user`, `mysql_password` from the site's **Database** tab. Tables are created automatically on first request.

## 4. Lock down private files on Nginx

`.htaccess` already protects `lib/`, `tools/`, `storage/` and `config.php` on OpenLiteSpeed/Apache stacks.
On an **Nginx** stack, add this to the site's custom Nginx config (in the site's settings in xCloud, inside the server block):

```nginx
location ~ ^/(lib|tools|storage)/ { deny all; return 404; }
location ~ ^/(config(\.sample)?\.php|.*\.(py|md|sqlite|upload)|marks\.json)$ { deny all; return 404; }
location ~ /\.git { deny all; return 404; }
```

Check afterwards: `https://YOUR-SITE/storage/.gitkeep` and `https://YOUR-SITE/config.php` should both return 404 (or 403).

## 5. Replacement search cron (optional)

When a library GIF collects at least 3 downvotes and is 2+ below its upvotes (configurable), it is flagged and queued.
Add an xCloud **Cron Job** for the site, e.g. hourly:

```bash
php /var/www/YOUR-SITE/tools/find_replacements.php
```

It searches Giphy/Tenor for each newly flagged GIF and adds up to 4 candidates to the review queue.
Without an API key, flagged GIFs stay queued and the page shows visitors Giphy/Tenor links to suggest one themselves.
You can also press **Search now** on a flagged GIF in the review page.

## 6. Review submissions

Open `https://YOUR-SITE/admin.php` and sign in. You can:

- approve or reject community suggestions and search candidates (current vs. proposed side by side),
- see GIFs flagged by downvotes, run a search, or dismiss the flag with **Keep this GIF**,
- **Export approved JSON** to fold approved GIFs into `library.json` later.

Approved GIFs appear on the entry under **Community GIFs** and can be voted on. Nothing in `library.json` is replaced automatically.

## Optional: voting on the GitHub Pages copy

Add `'allowed_origins' => ['https://atomechllc.github.io']` to `config.php`, then in GitHub set a repository
variable `LIBRARY_API_URL` = `https://YOUR-SITE/api.php` (Settings → Secrets and variables → Actions → Variables) and re-run the Pages workflow.

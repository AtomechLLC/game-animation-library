# Deploying to xCloud

The atlas runs on xCloud as a **Node.js** site deployed from this GitHub repo. `server.js` serves the page, the
community API (`/api`) and the owner review page (`/admin`). It has no npm dependencies and stores everything in one
data folder (`db.json` plus the submitted GIFs). GitHub Pages keeps working unchanged as a read-only copy.

Needs Node.js 20 or newer (set it under the server's **Node Configuration** in xCloud).

## 1. Create the site

1. In xCloud, open your server and add a new site deployed from Git: connect GitHub and pick
   `atomechllc/game-animation-library`, branch `main`.
2. **App Type: Node.js.** xCloud will say "Framework not recognised — assuming a server process". That is
   correct: this is a plain Node server with no framework, so keep the **server process** (SSR / Node process)
   serving mode, not a static build.
3. Build command: leave empty (or `npm install`, which installs nothing). Start command: `npm start`
   (same as `node server.js`). There is no build output folder.
4. Port: `3000`, or whatever xCloud fills in. Use the same number for `PORT` in `.env` (step 2). If xCloud sets
   `PORT` itself, that value wins over `.env`.
5. Turn on **Push to deploy** if you want every push to `main` to update the site.

xCloud's Nginx sits in front of the app and handles HTTPS, so the app only needs to listen on `127.0.0.1`.
If the site shows a 502 error after deploying, set `HOST=0.0.0.0` in `.env` and restart, and check that `PORT`
matches the port in xCloud's settings.

## 2. Add the private settings

SSH (or use xCloud's file manager) into the site folder and run:

```bash
cp .env.example .env
npm run hash-password      # type the review page password, paste the ADMIN_PASSWORD_HASH=... line into .env
npm run secret             # paste the SECRET=... line into .env
mkdir -p ../library-data   # where submissions are stored (DATA_DIR)
```

Then check `.env`:

- `PORT` matches the port xCloud proxies to.
- `ADMIN_PASSWORD_HASH` and `SECRET` from the two commands above.
- `DATA_DIR` points **outside the app folder** (default `../library-data`), so deploys never overwrite it.
  Include that folder in your backups: it holds every vote and submission.
- Optional: `GIPHY_API_KEY` and/or `TENOR_API_KEY` to turn on automatic replacement search for downvoted GIFs.

`.env` and `library-data/` are git-ignored. Restart the app after editing `.env`.

## 3. Upload size

Submissions can be up to `MAX_UPLOAD_MB` (8 MB by default). If xCloud lets you edit the site's Nginx config, set
`client_max_body_size 10m;` so larger uploads aren't cut off by Nginx before they reach the app.

## 4. What is public

Only the page, `/gifs/*`, `/api` and `/admin` are served. The repo's other files (`.env`, `library.json`, scripts) are
not reachable from the web, and the data folder lives outside the app. Check afterwards that
`https://YOUR-SITE/.env` returns 404.

## 5. Replacement search (optional)

When a library GIF collects at least 3 downvotes and is 2+ below its upvotes (configurable), it is flagged and queued.
With a Giphy or Tenor key set, the app searches for each newly flagged GIF every `SEARCH_EVERY_MINUTES` (60 by
default) and adds up to 4 candidates to the review queue. No cron job is needed. Without a key, flagged GIFs stay
queued and the page shows visitors Giphy/Tenor links to suggest one themselves. You can also press **Search now** on a
flagged GIF in the review page.

## 6. Review submissions

Open `https://YOUR-SITE/admin` and sign in with the password from step 2. Submissions never appear on the
public page until you approve them there. You can:

- see the current GIF and the proposed one side by side. Proposed GIFs are **blurred until you click them**
  (untick "Blur submitted GIFs until clicked" to turn that off), so nothing explicit flashes on screen,
- **Approve: replace current** puts the new GIF in place of the library GIF on the site (the original stays linked
  under it as "Replaced"), **Approve as extra GIF** adds it under **Community GIFs**, **Reject** hides it,
  **Delete** removes it and its stored file,
- on the Approved tab, **Restore original** / **Use as replacement** switch an approved GIF between the two,
- see GIFs flagged by downvotes, run a search, or dismiss the flag with **Keep this GIF**,
- **Export approved JSON** to fold approved GIFs into `library.json` later.

**Where submissions are stored.** Uploads *and* links are saved on the site: a submitted Giphy/Tenor page or direct
.gif/.webp/.mp4 link is downloaded when it is sent, so what you approve is exactly what is shown and a link can't be
swapped for something else later. Files go to `DATA_DIR/uploads` under random names and are only served through
`/api` (approved only) or `/admin` (signed in). The downloader only fetches public addresses on ports 80/443 and stops
at `MAX_UPLOAD_MB`.

The review page signs you in for 12 hours with a cookie; **Sign out** ends it early. Ten wrong passwords in an hour
from one address are locked out for the rest of that hour.

## Optional: voting on the GitHub Pages copy

Add `ALLOWED_ORIGINS=https://atomechllc.github.io` to `.env`, then in GitHub set a repository variable
`LIBRARY_API_URL` = `https://YOUR-SITE/api` (Settings → Secrets and variables → Actions → Variables) and re-run the
Pages workflow.

## Running it locally

`npm start` with no `.env` serves the atlas on http://127.0.0.1:3000 with data in `../library-data`. Set
`ADMIN_PASSWORD_HASH` to try the review page. (`serve_local.py` is the separate owner-only page for ✕ marks.)

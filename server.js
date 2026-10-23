// The atlas on xCloud (or any Node.js host): serves the page, the community API (/api) and the review page (/admin).
// No dependencies. Start with `npm start`; settings are in .env (see .env.example and DEPLOY-XCLOUD.md).
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const cfg = require('./lib/config');
const api = require('./lib/api');
const admin = require('./lib/admin');
const { searchFlagged } = require('./lib/media');
const video = require('./lib/video');
const store = require('./lib/store');
const { send } = require('./lib/http');

const TYPES = { '.webp': 'image/webp', '.gif': 'image/gif', '.png': 'image/png', '.jpg': 'image/jpeg', '.mp4': 'video/mp4' };
const FRAME_TYPES = { '.json': 'application/json; charset=utf-8', '.webp': 'image/webp', '.png': 'image/png',
  '.js': 'text/javascript; charset=utf-8', '.glb': 'model/gltf-binary', '.bin': 'application/octet-stream' };

/**
 * template.html + library.json, with community features pointed at /api. Same output as build_page.py,
 * except that GIFs on the blocklist (removed on /admin, or in gif-blocklist.json) are left out.
 */
let pageCache = null;
function renderPage() {
  const files = ['template.html', 'library.json'].map(f => path.join(cfg.ROOT, f));
  const list = store.blocklist();
  const stamp = files.map(f => fs.statSync(f).mtimeMs).join() + '|' + list.version;
  if (pageCache?.stamp !== stamp) {
    const dump = o => JSON.stringify(o).replace(/<\//g, '<\\/');
    const data = JSON.parse(fs.readFileSync(files[1], 'utf8'));
    if (list.urls.size || list.hashes.size || Object.keys(store.db().hidden).length) {
      for (const a of data.animations) if (a.gifs) a.gifs = a.gifs.filter(g => !store.isBlockedGif(a.id, g, list));
    }
    const html = fs.readFileSync(files[0], 'utf8').replace('__DATA__', () => dump(data)).replace('__CONFIG__', () => dump({ api: 'api' }));
    pageCache = { stamp, html };
  }
  return pageCache.html;
}

/** Only the GIF and frame data folders are public; everything else in the repo stays private. */
function serveFile(res, pathname, dir, types, maxAge) {
  const rel = decodeURIComponent(pathname).replace(/^\/+/, '');
  const file = path.join(cfg.ROOT, rel);
  const type = types[path.extname(file).toLowerCase()];
  if (!file.startsWith(path.join(cfg.ROOT, dir) + path.sep) || !type || !fs.existsSync(file) || !fs.statSync(file).isFile()) return send(res, 404, 'Not found');
  res.writeHead(200, { 'Content-Type': type, 'Content-Length': fs.statSync(file).size, 'Cache-Control': `public, max-age=${maxAge}`, 'X-Content-Type-Options': 'nosniff' });
  fs.createReadStream(file).pipe(res);
}
const serveGif = (res, p) => serveFile(res, p, 'gifs', TYPES, 604800);

const server = http.createServer(async (req, res) => {
  try {
    const u = new URL(req.url, 'http://x');
    const p = u.pathname;
    if (p === '/' || p === '/index.html' || p === '/index.php') {
      return send(res, 200, renderPage(), { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' });
    }
    if (p === '/api' || p === '/api.php') return await api.handle(req, res, u.searchParams); // api.php: older GitHub Pages builds
    if (p === '/admin' || p === '/admin.php') return await admin.handle(req, res, u.searchParams);
    if (p.startsWith('/gifs/')) return serveGif(res, p);
    // Frame data tab: a static page that loads frame-data/games.json and one JSON file per game
    if (p === '/frame-data' || p === '/frame-data.html') return serveFile(res, '/frame-data.html', '', { '.html': 'text/html; charset=utf-8' }, 0);
    if (p.startsWith('/frame-data/')) return serveFile(res, p, 'frame-data', FRAME_TYPES, 3600);
    if (p === '/healthz') return send(res, 200, 'ok');
    send(res, 404, 'Not found');
  } catch (e) {
    console.error(e);
    if (!res.headersSent) send(res, e.status || 500, e.status ? e.message : 'Server error');
  }
});

server.listen(cfg.port, cfg.host, () => {
  console.log(`Game Animation Library on http://${cfg.host}:${cfg.port}  (data in ${cfg.dataDir})`);
  if (!cfg.adminPasswordHash) console.log('ADMIN_PASSWORD_HASH is not set, so /admin is disabled. Run: npm run hash-password');
});

// Finds ffmpeg for video uploads (downloading it if missing) and resumes conversions a restart interrupted.
// Runs after the server is listening and never stops it: without ffmpeg, video uploads just stay off.
server.once('listening', () => setTimeout(() => video.start().catch(e => console.error('video:', e)), 2000).unref());

// Replacement search for GIFs flagged by downvotes (needs GIPHY_API_KEY and/or TENOR_API_KEY).
if (cfg.giphyApiKey || cfg.tenorApiKey) {
  const run = () => searchFlagged().catch(e => console.error('search:', e));
  setInterval(run, cfg.searchEveryMinutes * 60e3).unref();
  setTimeout(run, 30e3).unref();
}

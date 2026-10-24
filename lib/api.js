// Community API for the atlas.
//   GET  /api?action=state            vote tallies, your votes, approved community GIFs, flagged GIFs
//   GET  /api?action=blocklist        GIFs removed for good (URLs and SHA-256 of the files), for GIF-gathering scripts
//   POST /api?action=vote             JSON {animation, target, value: 1 | -1 | 0}
//   POST /api?action=submit           multipart: animation, replaces?, url | file, note?, name?
//                                     (a url is downloaded and stored like an upload; a short video is converted to a GIF
//                                     in the background, see video.js; nothing is public until approved)
//   POST /api?action=propose          multipart: name, category | new_category, description, games?, url?, file?, by?
//                                     a new animation for the library (kept private; reviewed on /admin, exported as taxonomy lines)
//   GET  /api?action=file&id=N        an approved GIF
//   POST /api?action=need             admin only: JSON {animation, gif?, on}; marks an entry or GIF "needs replacement"
//                                     (needs the /admin session cookie and its CSRF token in X-Admin-Token)
// Voters are identified by a random token the page keeps in localStorage and sends as X-Voter-Token.
'use strict';
const fs = require('fs');
const cfg = require('./config');
const store = require('./store');
const video = require('./video');
const { fetchMedia } = require('./media');
const { HttpError, UserError, readForm, clientIp, json, send } = require('./http');
const auth = require('./auth');

const fail = (status, msg) => { throw new HttpError(status, msg); };

function voter(req) {
  const t = String(req.headers['x-voter-token'] || '');
  return /^[A-Za-z0-9_-]{16,64}$/.test(t) ? store.h('voter:' + t) : null;
}

function state(req, res) {
  const db = store.db(), tally = {}, mine = {}, community = {}, v = voter(req);
  for (const [target, votes] of Object.entries(db.votes)) {
    const t = store.tally(target);
    if (t.up || t.down) tally[target] = [t.up, t.down];
    if (v && votes[v]) mine[target] = votes[v].value;
  }
  // Only approved, stored files are ever public. mode 'replace' rows take the place of the library GIF in `replaces`.
  for (const s of db.submissions) {
    if (s.status !== 'approved' || !s.file || s.converting) continue;
    (community[s.animation] ||= []).push({
      id: s.id,
      target: 'sub:' + s.id,
      replaces: s.replaces,
      mode: s.replaces && s.mode === 'replace' ? 'replace' : 'add',
      src: 'api?action=file&id=' + s.id,
      source_url: s.url,
      mime: s.mime,
      note: s.note,
      by: s.source === 'search' ? 'search' : (s.submitter || 'anonymous'),
    });
  }
  const needs = Object.values(db.needs).map(n => ({ animation: n.animation, gif: n.gif }));
  // A signed-in admin gets the token for marking entries from the atlas itself.
  const sess = auth.session(req);
  json(res, 200, { tally, mine, community, flagged: Object.keys(db.queue), needs, max_upload: cfg.maxUploadBytes, video: video.status().on ? { max_seconds: cfg.videoMaxSeconds, max_upload: cfg.videoMaxBytes } : null, admin: sess ? auth.csrfFor(sess) : null });
}

async function vote(req, res) {
  if (req.method !== 'POST') fail(405, 'POST only');
  const v = voter(req) || fail(400, 'missing voter token');
  const { fields } = await readForm(req, 10000);
  const animation = String(fields.animation || ''), target = String(fields.target || ''), value = Number(fields.value || 0);
  if (!store.library()[animation]) fail(400, 'unknown animation');
  if (![-1, 0, 1].includes(value)) fail(400, 'bad value');
  const sub = /^sub:(\d+)$/.exec(target);
  if (sub) {
    const s = store.submission(Number(sub[1]));
    if (!s || s.animation !== animation || s.status !== 'approved') fail(400, 'unknown GIF');
  } else if (!store.libraryGif(animation, target)) fail(400, 'unknown GIF');
  const ip = clientIp(req);
  if (!store.rateOk(ip, 'vote', cfg.votesPerHour)) fail(429, 'too many votes, try again later');
  const db = store.db();
  const votes = (db.votes[target] ||= {});
  if (value === 0) delete votes[v];
  else votes[v] = { value, animation, ip: store.h(ip), at: store.now() };
  store.updateFlag(target, animation);
  store.save();
  const t = store.tally(target);
  json(res, 200, { target, up: t.up, down: t.down, mine: value, flagged: !!db.queue[target] });
}

async function submit(req, res) {
  if (req.method !== 'POST') fail(405, 'POST only');
  const v = voter(req) || fail(400, 'missing voter token');
  const { fields, files } = await readForm(req, video.maxBytes() + 64 * 1024);
  if ((fields.website || '') !== '') return json(res, 200, { ok: true }); // honeypot: bots fill every field
  const animation = String(fields.animation || '');
  if (!store.library()[animation]) fail(400, 'unknown animation');
  const replaces = String(fields.replaces || '').trim();
  if (replaces && !store.libraryGif(animation, replaces)) fail(400, 'unknown GIF to replace');
  const note = String(fields.note || '').trim().slice(0, 500);
  const name = String(fields.name || '').trim().slice(0, 60);
  const url = String(fields.url || '').trim();
  const file = files.file && files.file.data.length ? files.file : null;
  if (!!file === !!url) fail(400, 'send either a URL or a file');
  const ip = clientIp(req);
  if (!store.rateOk(ip, 'submit', cfg.submissionsPerHour)) fail(429, 'too many submissions, try again later');
  const refused = 'that GIF was removed from the library and cannot be suggested again';
  if (url && store.isBlockedMedia(url)) fail(400, refused);
  let m;
  if (url) {
    if (url.length > 1000 || !/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(url)) fail(400, 'that does not look like a web address');
    // Linked GIFs are downloaded and stored here too, so what gets approved is exactly what is shown.
    try { m = await fetchMedia(url); } catch (e) { fail(400, e instanceof UserError ? e.message : 'could not download that link'); }
  } else {
    try { m = await video.acceptMedia(file.data); } catch (e) { if (e instanceof UserError) fail(400, e.message); throw e; }
    m || fail(400, video.status().on ? 'only GIF, WebP or short video files (MP4, MOV, WebM) are accepted' : 'only GIF, WebP or MP4 files are accepted');
  }
  if (store.isBlockedMedia(url, m.file)) {
    store.removeUpload(m.file);
    fail(400, refused);
  }
  video.addSubmission({ animation, replaces: replaces || null, url: url || null, ...m, note, submitter: name, source: 'community', voter: v, ip: store.h(ip) });
  json(res, 200, { ok: true });
}

/** A proposed new animation: what it is, which category, an optional reference link and an optional clip. */
async function propose(req, res) {
  if (req.method !== 'POST') fail(405, 'POST only');
  const v = voter(req) || fail(400, 'missing voter token');
  const { fields, files } = await readForm(req, video.maxBytes() + 64 * 1024);
  if ((fields.website || '') !== '') return json(res, 200, { ok: true }); // honeypot
  // '|' separates the fields of a taxonomy.txt line, which is where approved proposals end up
  const text = (k, max) => String(fields[k] || '').replace(/[|\r\n]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
  const name = text('name', 80), description = text('description', 500), games = text('games', 200);
  const category = text('category', 60), newCategory = text('new_category', 60);
  if (!name) fail(400, 'give the animation a name');
  if (description.length < 10) fail(400, 'describe the animation in a sentence or two');
  if (category && !store.categories()[category]) fail(400, 'unknown category');
  if (!category && !newCategory) fail(400, 'choose a category, or name a new one');
  const url = String(fields.url || '').trim();
  if (url && (url.length > 1000 || !/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(url))) fail(400, 'that does not look like a web address');
  const file = files.file && files.file.data.length ? files.file : null;
  const ip = clientIp(req);
  if (!store.rateOk(ip, 'propose', cfg.submissionsPerHour)) fail(429, 'too many proposals, try again later');
  let m = {};
  if (file) {
    try { m = await video.acceptMedia(file.data); } catch (e) { if (e instanceof UserError) fail(400, e.message); throw e; }
    m || fail(400, video.status().on ? 'only GIF, WebP or short video files (MP4, MOV, WebM) are accepted' : 'only GIF, WebP or MP4 files are accepted');
    if (store.isBlockedMedia(null, m.file)) { store.removeUpload(m.file); fail(400, 'that clip was removed from the library and cannot be sent again'); }
  }
  video.addProposal({ name, category, new_category: category ? '' : newCategory, games, description, url: url || null, ...m,
    submitter: text('by', 60), voter: v, ip: store.h(ip) });
  json(res, 200, { ok: true });
}

async function need(req, res) {
  if (req.method !== 'POST') fail(405, 'POST only');
  const sess = auth.session(req) || fail(403, 'sign in on the review page first');
  if (String(req.headers['x-admin-token'] || '') !== auth.csrfFor(sess)) fail(403, 'stale page, reload it');
  const { fields } = await readForm(req, 10000);
  const animation = String(fields.animation || ''), gif = String(fields.gif || '');
  if (!store.library()[animation]) fail(400, 'unknown animation');
  if (gif && !store.libraryGif(animation, gif)) fail(400, 'unknown GIF');
  store.setNeed(animation, gif, !!fields.on);
  json(res, 200, { ok: true, animation, gif, on: !!fields.on });
}

/** The blocklist in the gif-blocklist.json format (also what /admin exports). */
function blocklistJson() {
  const own = Object.entries(store.db().hidden).map(([key, h]) => ({ key, ...h }));
  let repo = [];
  try { repo = JSON.parse(fs.readFileSync(require('path').join(cfg.ROOT, 'gif-blocklist.json'), 'utf8')).blocked || []; } catch { /* none yet */ }
  const seen = new Set(own.map(b => b.key));
  return { about: 'GIFs removed from the library for good. Do not add a GIF whose page_url, media_url or source_url matches, or whose file has this sha256.', blocked: [...own, ...repo.filter(b => !seen.has(b.key))] };
}

/** Stream a stored upload with headers that stop browsers treating it as anything but media. */
function sendUpload(res, s, cache) {
  const p = store.uploadPath(s.file);
  if (!fs.existsSync(p)) fail(404, 'not found');
  res.writeHead(200, { 'Content-Type': s.mime, 'Content-Length': fs.statSync(p).size, 'Cache-Control': cache, 'Content-Security-Policy': "default-src 'none'", 'X-Content-Type-Options': 'nosniff' });
  fs.createReadStream(p).pipe(res);
}

function file(req, res, q) {
  const s = store.submission(Number(q.get('id')));
  if (!s || !s.file || s.status !== 'approved' || s.converting) fail(404, 'not found');
  sendUpload(res, s, 'public, max-age=86400');
}

async function handle(req, res, q) {
  const origin = req.headers.origin;
  const cors = origin && cfg.allowedOrigins.includes(origin) ? {
    'Access-Control-Allow-Origin': origin, Vary: 'Origin', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Voter-Token', 'Access-Control-Max-Age': '86400',
  } : {};
  for (const [k, v] of Object.entries(cors)) res.setHeader(k, v);
  if (req.method === 'OPTIONS') return send(res, 204, '');
  try {
    switch (q.get('action')) {
      case 'state': return state(req, res);
      case 'vote': return await vote(req, res);
      case 'submit': return await submit(req, res);
      case 'propose': return await propose(req, res);
      case 'file': return file(req, res, q);
      case 'blocklist': return json(res, 200, blocklistJson());
      case 'need': return await need(req, res);
      default: fail(404, 'unknown action');
    }
  } catch (e) {
    if (!(e instanceof HttpError)) console.error('api:', e);
    if (!res.headersSent) json(res, e.status || 500, { error: e instanceof HttpError ? e.message : 'server error' });
  }
}

module.exports = { handle, sendUpload, blocklistJson };

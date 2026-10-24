// Votes, submissions and the replacement queue, kept in DATA_DIR/db.json.
// One Node process owns the file: every change is applied in memory and written atomically (temp file + rename).
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const cfg = require('./config');

const DB_FILE = path.join(cfg.dataDir, 'db.json');
const UPLOADS = path.join(cfg.dataDir, 'uploads');
try {
  fs.mkdirSync(UPLOADS, { recursive: true });
} catch (e) {
  console.error(`Cannot create the data folder ${UPLOADS} (${e.code}). Set DATA_DIR in .env to a folder the site user can write, e.g. DATA_DIR=${require('os').homedir()}/library-data`);
  throw e;
}

// votes: { target: { voterHash: { value, animation, ip, at } } }
// submissions: [{ id, animation, replaces, mode, file, mime, bytes, url, note, submitter, source, voter, ip, status, created_at, reviewed_at,
//                 converting?, converted_from?, convert_error? }]
//   status pending | approved | rejected; mode 'replace' (shown in place of the library GIF in `replaces`) | 'add'
//   converting: a submitted video whose GIF is still being made (file is the video until then, see video.js)
// queue: { target: { animation, flagged_at, searched_at, result } }  library GIFs flagged by downvotes
// needs: { key: { animation, gif, marked_at } }  marked "needs replacement" by the admin; gif is a library GIF key, or '' for the whole entry
// hidden: { gifKey: { animation, title, page_url, media_url, source_url, sha256, removed_at } }  library GIFs the admin removed,
//   kept here rather than in the repo so a deploy does not bring them back. Together with gif-blocklist.json in the repo this is
//   the blocklist: a GIF matching any of these URLs or file hashes is left off the atlas and refused as a submission.
// proposals: [{ id, name, category, new_category, subcategory, tags, games, description, url, file?, mime?, bytes?, submitter, voter, ip,
//               status, created_at, reviewed_at, converting?, converted_from?, convert_error? }]
//   new animations visitors propose for the library. category is a library category id, or '' with new_category set.
//   Ids come from the same counter as submissions, so a clip is converted by video.js the same way (see mediaRow).
//   Approved ones are exported from /admin as taxonomy.txt lines; nothing here is shown publicly.
let db = { nextId: 1, votes: {}, submissions: [], queue: {}, needs: {}, hidden: {}, proposals: [] };
if (fs.existsSync(DB_FILE)) db = { ...db, ...JSON.parse(fs.readFileSync(DB_FILE, 'utf8')) };

function save() {
  const tmp = DB_FILE + '.' + process.pid + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(db));
  fs.renameSync(tmp, DB_FILE);
}

const now = () => new Date().toISOString().replace('T', ' ').slice(0, 19);
const h = s => crypto.createHmac('sha256', cfg.secret).update(s).digest('hex');

/** library.json, indexed by animation id (re-read when the file changes after a git pull) */
let lib = null, cats = null, libMtime = 0;
function library() {
  const file = path.join(cfg.ROOT, 'library.json');
  const m = fs.statSync(file).mtimeMs;
  if (!lib || m !== libMtime) {
    const data = JSON.parse(fs.readFileSync(file, 'utf8'));
    lib = {};
    for (const a of data.animations) lib[a.id] = a;
    cats = {};
    for (const c of data.categories) cats[c.id] = c;
    libMtime = m;
  }
  return lib;
}
/** library.json categories, indexed by id */
const categories = () => (library(), cats);

/**
 * Vote target for a library GIF: "<animation>|<local path, else media URL, else page URL>".
 * page_url alone is not unique (several Ultimate Frame Data GIFs share a character page). Community GIFs use "sub:<id>".
 * Same as gkey() in template.html.
 */
const gifKey = (animation, g) => animation + '|' + (g.local || g.media_url || g.page_url || '');
const libraryGif = (animation, target) => (library()[animation]?.gifs || []).find(g => gifKey(animation, g) === target) || null;

/** Per-IP hourly limits, in memory (a restart resets them). */
const hits = new Map();
function rateOk(ip, action, limit) {
  const key = action + ':' + h(ip), cutoff = Date.now() - 3600e3;
  const list = (hits.get(key) || []).filter(t => t > cutoff);
  if (list.length >= limit) { hits.set(key, list); return false; }
  list.push(Date.now());
  hits.set(key, list);
  return true;
}

function tally(target) {
  let up = 0, down = 0;
  for (const v of Object.values(db.votes[target] || {})) v.value > 0 ? up++ : down++;
  return { up, down };
}

/** Flag or unflag a library GIF for a replacement search based on its current tally. */
function updateFlag(target, animation) {
  if (target.startsWith('sub:')) return;
  const { up, down } = tally(target);
  const flag = down >= cfg.flagMinDownvotes && down - up >= cfg.flagNetScore;
  const q = db.queue[target];
  if (flag && !q) db.queue[target] = { animation, flagged_at: now(), searched_at: null, result: null };
  else if (!flag && q && !q.searched_at) delete db.queue[target];
}

/**
 * Sniff the media type from the first bytes. Returns [mime, ext] or null.
 * GIF and WebP are stored as they are; the video types are converted by video.js (MP4 is kept as-is without ffmpeg).
 */
function sniffMedia(buf) {
  const s = buf.subarray(0, 16).toString('latin1');
  if (s.startsWith('GIF87a') || s.startsWith('GIF89a')) return ['image/gif', 'gif'];
  if (s.startsWith('RIFF') && s.slice(8, 12) === 'WEBP') return ['image/webp', 'webp'];
  if (s.startsWith('RIFF') && s.slice(8, 12) === 'AVI ') return ['video/x-msvideo', 'avi'];
  if (s.slice(4, 8) === 'ftyp') return s.slice(8, 12) === 'qt  ' ? ['video/quicktime', 'mov'] : ['video/mp4', 'mp4'];
  if (s.startsWith('\x1a\x45\xdf\xa3')) return ['video/webm', 'webm']; // EBML: WebM / Matroska
  return null;
}

/** Write bytes to DATA_DIR/uploads under a random, non-executable name and return that name. */
function writeUpload(buf, ext) {
  const file = crypto.randomBytes(16).toString('hex') + '.' + ext + '.upload';
  fs.writeFileSync(path.join(UPLOADS, file), buf);
  return file;
}

/** Store media bytes as they are. Returns { file, mime, bytes } or null when the type is not recognised. */
function storeMedia(buf) {
  const media = sniffMedia(buf);
  if (!media) return null;
  return { file: writeUpload(buf, media[1]), mime: media[0], bytes: buf.length };
}

const uploadPath = file => path.join(UPLOADS, path.basename(file));

function removeUpload(file) {
  if (file) fs.rmSync(uploadPath(file), { force: true });
}

function addSubmission(row) {
  const s = { id: db.nextId++, replaces: null, mode: 'add', url: null, note: '', submitter: '', voter: null, ip: null, status: 'pending', created_at: now(), reviewed_at: null, ...row };
  db.submissions.push(s);
  save();
  return s;
}

/** Mark or unmark an entry (gif '') or one of its library GIFs as needing a replacement. */
const needKey = (animation, gif) => gif || animation;
function setNeed(animation, gif, on) {
  const k = needKey(animation, gif);
  if (on) db.needs[k] ||= { animation, gif: gif || '', marked_at: now() };
  else delete db.needs[k];
  save();
}

const sha256 = buf => crypto.createHash('sha256').update(buf).digest('hex');

/** SHA-256 of a repo file (a library GIF's `local` path), cached by mtime. null when the file is missing. */
const hashCache = new Map();
function fileHash(rel) {
  const file = path.join(cfg.ROOT, rel);
  let m;
  try { m = fs.statSync(file).mtimeMs; } catch { return null; }
  const c = hashCache.get(file);
  if (c?.m === m) return c.hash;
  const hash = sha256(fs.readFileSync(file));
  hashCache.set(file, { m, hash });
  return hash;
}

/** What identifies a library GIF for the blocklist: its URLs and the hash of its downloaded file. */
function gifIds(g) {
  return { page_url: g.page_url || '', media_url: g.media_url || '', source_url: g.source_url || '', sha256: g.local ? fileHash(g.local) || '' : '' };
}

/** gif-blocklist.json in the repo (exported from /admin and committed), re-read when it changes. */
let repoList = [], repoMtime = 0;
function repoBlocklist() {
  const file = path.join(cfg.ROOT, 'gif-blocklist.json');
  let m;
  try { m = fs.statSync(file).mtimeMs; } catch { return []; }
  if (m !== repoMtime) {
    try { repoList = JSON.parse(fs.readFileSync(file, 'utf8')).blocked || []; } catch (e) { console.error('gif-blocklist.json:', e.message); repoList = []; }
    repoMtime = m;
  }
  return repoList;
}

/**
 * Every blocked GIF, from db.json and gif-blocklist.json:
 *   urls    media / source file URLs, plus the page URL of a blocked GIF that had no file (a link-only GIF)
 *   pages   every blocked page URL (refused as a submission; not used to hide library GIFs, since several
 *           Ultimate Frame Data GIFs share one character page)
 *   hashes  SHA-256 of the blocked files
 *   keys    gifKey of a blocked GIF with nothing else to match on
 */
let blockVersion = 0;
function blocklist() {
  const urls = new Set(), pages = new Set(), hashes = new Set(), keys = new Set();
  for (const b of [...Object.values(db.hidden), ...repoBlocklist()]) {
    if (b.media_url) urls.add(b.media_url);
    if (b.source_url) urls.add(b.source_url);
    if (b.sha256) hashes.add(b.sha256);
    if (b.page_url) { pages.add(b.page_url); if (!b.media_url && !b.source_url && !b.sha256) urls.add(b.page_url); }
    if (!b.page_url && !b.media_url && !b.source_url && !b.sha256 && b.key) keys.add(b.key);
  }
  for (const [key, h] of Object.entries(db.hidden)) if (!h.page_url && !h.media_url && !h.source_url && !h.sha256) keys.add(key);
  return { urls, pages, hashes, keys, version: blockVersion + ':' + repoMtime };
}

/**
 * Is this library GIF removed? Matched by its file URLs or its file's hash rather than its key, so the same clip stays
 * hidden under a new file name, and a different clip that later gets the freed file name is not.
 */
function isBlockedGif(animation, g, list = blocklist()) {
  const ids = gifIds(g);
  return [ids.media_url, ids.source_url, ids.page_url].some(u => u && list.urls.has(u)) || (!!ids.sha256 && list.hashes.has(ids.sha256)) || list.keys.has(gifKey(animation, g));
}

/** Is a submitted link or stored upload on the blocklist? */
function isBlockedMedia(url, file) {
  const list = blocklist();
  if (url && (list.urls.has(url) || list.pages.has(url))) return true;
  if (file) { try { return list.hashes.has(sha256(fs.readFileSync(uploadPath(file)))); } catch { return false; } }
  return false;
}

/**
 * Remove a library GIF from the public atlas for good (or bring it back). Records its URLs and file hash so the same
 * clip is not shown again under another name, submitted again, or picked up by a replacement search. Also clears its mark and flag.
 */
function setHidden(animation, gif, on) {
  if (on) {
    const g = libraryGif(animation, gif);
    db.hidden[gif] = { animation, title: g?.title || '', ...(g ? gifIds(g) : {}), removed_at: now() };
    delete db.needs[gif];
    delete db.queue[gif];
  } else delete db.hidden[gif];
  blockVersion++;
  save();
}

// Removals saved before the blocklist kept URLs and hashes: fill them in once.
for (const [gif, h] of Object.entries(db.hidden)) {
  if (h.sha256 !== undefined) continue;
  const g = libraryGif(h.animation, gif);
  if (g) Object.assign(h, gifIds(g));
}

const submission = id => db.submissions.find(s => s.id === id) || null;
const proposal = id => db.proposals.find(p => p.id === id) || null;
/** A submission or a proposal: both can carry an uploaded clip that video.js converts. */
const mediaRow = id => submission(id) || proposal(id);

function addProposal(row) {
  const p = { id: db.nextId++, category: '', new_category: '', subcategory: '', tags: '', games: '', url: null, file: null, submitter: '', voter: null, ip: null, status: 'pending', created_at: now(), reviewed_at: null, ...row };
  db.proposals.push(p);
  save();
  return p;
}

module.exports = { db: () => db, save, now, h, library, categories, gifKey, libraryGif, rateOk, tally, updateFlag, sniffMedia, writeUpload, storeMedia, uploadPath, removeUpload, addSubmission, submission, proposal, mediaRow, addProposal, needKey, setNeed, setHidden, sha256, blocklist, isBlockedGif, isBlockedMedia };

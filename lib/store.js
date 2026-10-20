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
// hidden: { gifKey: { animation, title, removed_at } }  library GIFs the admin removed; kept here rather than in the repo so a deploy does not bring them back
let db = { nextId: 1, votes: {}, submissions: [], queue: {}, needs: {}, hidden: {} };
if (fs.existsSync(DB_FILE)) db = { ...db, ...JSON.parse(fs.readFileSync(DB_FILE, 'utf8')) };

function save() {
  const tmp = DB_FILE + '.' + process.pid + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(db));
  fs.renameSync(tmp, DB_FILE);
}

const now = () => new Date().toISOString().replace('T', ' ').slice(0, 19);
const h = s => crypto.createHmac('sha256', cfg.secret).update(s).digest('hex');

/** library.json, indexed by animation id (re-read when the file changes after a git pull) */
let lib = null, libMtime = 0;
function library() {
  const file = path.join(cfg.ROOT, 'library.json');
  const m = fs.statSync(file).mtimeMs;
  if (!lib || m !== libMtime) {
    lib = {};
    for (const a of JSON.parse(fs.readFileSync(file, 'utf8')).animations) lib[a.id] = a;
    libMtime = m;
  }
  return lib;
}

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

/** Remove a library GIF from the public atlas (or bring it back). Also clears its mark and downvote flag. */
function setHidden(animation, gif, on) {
  if (on) {
    db.hidden[gif] = { animation, title: libraryGif(animation, gif)?.title || '', removed_at: now() };
    delete db.needs[gif];
    delete db.queue[gif];
  } else delete db.hidden[gif];
  save();
}

const submission = id => db.submissions.find(s => s.id === id) || null;

module.exports = { db: () => db, save, now, h, library, gifKey, libraryGif, rateOk, tally, updateFlag, sniffMedia, writeUpload, storeMedia, uploadPath, removeUpload, addSubmission, submission, needKey, setNeed, setHidden };

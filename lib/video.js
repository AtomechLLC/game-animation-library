// Short video submissions (MP4, MOV, WebM, MKV, AVI) are converted to an animated WebP (or a GIF when this ffmpeg
// has no WebP encoder), so they are reviewed and shown exactly like GIF submissions.
// Needs the ffmpeg program on the server: `sudo apt install ffmpeg`, or the static build that tools/install-ffmpeg.js
// downloads in the background after the app starts, when none is found (see DEPLOY-XCLOUD.md). Without it, MP4 is
// stored and shown as a video as before and other video types are refused.
//
// The submit request only checks the length (a quick `ffmpeg -i`) and stores the video. The conversion runs
// afterwards, one at a time at low priority; the review page shows "Converting…" until it is done.
'use strict';
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');
const cfg = require('./config');
const store = require('./store');
const { UserError } = require('./http');
const installer = require('../tools/install-ffmpeg');

// The ffmpeg demuxer for each sniffed video type. Forcing it (and file-only access) keeps ffmpeg from treating an
// upload as a playlist or anything else that could make it open other files or URLs.
const DEMUXER = { 'video/mp4': 'mov', 'video/quicktime': 'mov', 'video/webm': 'matroska', 'video/x-msvideo': 'avi' };
const isVideo = mime => mime in DEMUXER;

/** Which ffmpeg to run and what it can do: { bin, ok, version, webp }. Checked at startup. */
let ffmpeg = { bin: '', ok: false, version: '', webp: false, checked: false };

/** Run ffmpeg with args. Resolves { code, stderr }; rejects if it cannot start or runs past timeoutMs. */
function run(args, timeoutMs, lowPriority = false, bin = ffmpeg.bin) {
  return new Promise((resolve, reject) => {
    let child;
    try {
      child = spawn(bin, ['-hide_banner', '-nostdin', ...args], { stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) { return reject(e); }
    if (lowPriority) try { os.setPriority(child.pid, 10); } catch { /* not allowed here, run at normal priority */ }
    let out = '', err = '';
    child.stdout.on('data', c => { if (out.length < 1e6) out += c; });
    child.stderr.on('data', c => { if (err.length < 1e6) err += c; });
    const timer = setTimeout(() => { child.kill('SIGKILL'); reject(new Error('ffmpeg took longer than ' + timeoutMs / 1000 + ' s')); }, timeoutMs);
    child.on('error', e => { clearTimeout(timer); reject(e); });
    child.on('close', code => { clearTimeout(timer); resolve({ code, stdout: out, stderr: err }); });
  });
}

/** Use FFMPEG_PATH if set, else ffmpeg on the PATH (apt), else the copy tools/install-ffmpeg.js downloaded. */
async function detect(log = true) {
  ffmpeg = { bin: '', ok: false, version: '', webp: false, checked: true };
  for (const bin of cfg.ffmpegPath ? [cfg.ffmpegPath] : ['ffmpeg', installer.BIN]) {
    try {
      const v = await run(['-version'], 10000, false, bin);
      if (v.code !== 0) continue;
      const enc = await run(['-encoders'], 10000, false, bin);
      ffmpeg = { bin, ok: true, version: (/ffmpeg version (\S+)/.exec(v.stdout) || [])[1] || '', webp: /libwebp_anim/.test(enc.stdout), checked: true };
      break;
    } catch { /* not there, try the next one */ }
  }
  if (!log) return ffmpeg;
  if (ffmpeg.ok) console.log(`Video uploads: on (ffmpeg ${ffmpeg.version} at ${ffmpeg.bin}, converted to ${ffmpeg.webp ? 'animated WebP' : 'GIF'}, up to ${cfg.videoMaxSeconds} s)`);
  else console.log(`Video uploads: OFF, ffmpeg was not found${cfg.ffmpegPath ? ' at FFMPEG_PATH=' + cfg.ffmpegPath : ''}. Run: npm run install-ffmpeg (or sudo apt install ffmpeg), then restart. MP4 files are kept as video until then.`);
  return ffmpeg;
}

/** Run tools/install-ffmpeg.js in a child process (it downloads ~150 MB) and wait for it. */
function autoInstall() {
  if (installer.failedRecently()) {
    console.log('Video uploads: the automatic ffmpeg download failed in the last day, not retrying. Run: npm run install-ffmpeg (or sudo apt install ffmpeg).');
    return Promise.resolve();
  }
  console.log('Video uploads: ffmpeg not found, downloading a static build in the background (AUTO_INSTALL_FFMPEG=0 turns this off)…');
  return new Promise(resolve => {
    let child;
    try {
      child = spawn(process.execPath, [require.resolve('../tools/install-ffmpeg')], { stdio: ['ignore', 'inherit', 'inherit'] });
    } catch (e) { console.error('install-ffmpeg:', e.message); return resolve(); }
    try { os.setPriority(child.pid, 15); } catch { /* not allowed here */ }
    const timer = setTimeout(() => child.kill('SIGKILL'), 20 * 60e3).unref();
    child.on('error', e => { clearTimeout(timer); console.error('install-ffmpeg:', e.message); resolve(); });
    child.on('close', () => { clearTimeout(timer); resolve(); });
  });
}

/** Shown to the page so the form can offer video uploads, and on the review page. */
const status = () => ffmpeg.ok
  ? { on: true, max_seconds: cfg.videoMaxSeconds, max_upload: cfg.videoMaxBytes, format: ffmpeg.webp ? 'webp' : 'gif', version: ffmpeg.version }
  : { on: false, checked: ffmpeg.checked };

/** The largest file worth downloading or reading: images up to MAX_UPLOAD_MB, videos up to VIDEO_MAX_MB. */
const maxBytes = () => Math.max(cfg.maxUploadBytes, ffmpeg.ok ? cfg.videoMaxBytes : 0);

/** Length in seconds from `ffmpeg -i` (null when unknown), and whether there is a video stream at all. */
async function probe(file, mime) {
  const r = await run(['-protocol_whitelist', 'file', '-f', DEMUXER[mime], '-i', file], 20000);
  const d = /Duration: (\d+):(\d+):(\d+(?:\.\d+)?)/.exec(r.stderr);
  return { seconds: d ? Number(d[1]) * 3600 + Number(d[2]) * 60 + Number(d[3]) : null, hasVideo: /Stream #\S+.*: Video:/.test(r.stderr) };
}

/**
 * Check and store submitted media bytes. GIF / WebP are stored as they are. A video is checked (size, length,
 * has a picture) and stored for conversion: the result has converting: true, and the row must be added with
 * addSubmission() below so the conversion is queued. Returns { file, mime, bytes, converting? } or null when the
 * bytes are not a type we accept; throws UserError with a reason the submitter can read.
 */
async function acceptMedia(buf) {
  const media = store.sniffMedia(buf);
  if (!media) return null;
  const [mime, ext] = media;
  if (!isVideo(mime)) {
    if (buf.length > cfg.maxUploadBytes) throw new UserError(`that file is too large (GIF and WebP up to ${cfg.maxUploadBytes / 1048576} MB)`);
    return store.storeMedia(buf);
  }
  if (!ffmpeg.ok) {
    // No converter: MP4 behaves as before (shown as a video), other video types can't be shown, so refuse them.
    if (mime !== 'video/mp4') throw new UserError('this site cannot convert videos right now, send a GIF, WebP or MP4 instead');
    if (buf.length > cfg.maxUploadBytes) throw new UserError('that file is too large');
    return store.storeMedia(buf);
  }
  if (buf.length > cfg.videoMaxBytes) throw new UserError(`that video is too large (up to ${cfg.videoMaxBytes / 1048576} MB)`);
  const file = store.writeUpload(buf, ext);
  let info;
  try { info = await probe(store.uploadPath(file), mime); } catch (e) { info = null; console.error('ffmpeg probe:', e.message); }
  const why = !info ? 'could not read that video, try again later'
    : !info.hasVideo ? 'could not read that video, is it a valid MP4, MOV or WebM file?'
      : info.seconds > cfg.videoMaxSeconds + 0.5 ? `that video is ${Math.round(info.seconds)} s long, please trim it to ${cfg.videoMaxSeconds} s or less`
        : '';
  if (why) { store.removeUpload(file); throw new UserError(why); }
  return { file, mime, bytes: buf.length, converting: true, converted_from: `${ext.toUpperCase()} video${info.seconds ? ', ' + info.seconds.toFixed(1) + ' s' : ''}` };
}

/** store.addSubmission, plus queueing the conversion when the row is a video still to convert. */
function addSubmission(row) {
  const s = store.addSubmission(row);
  if (s.converting) enqueue(s.id);
  return s;
}

/** The same for a proposed new animation with a clip attached. */
function addProposal(row) {
  const p = store.addProposal(row);
  if (p.converting) enqueue(p.id);
  return p;
}

// One conversion at a time, in the background, so a burst of uploads can't pin every CPU.
const queue = [];
let busy = false;
function enqueue(id) {
  queue.push(id);
  if (!busy) drain();
}

async function drain() {
  busy = true;
  while (queue.length) {
    const s = store.mediaRow(queue.shift());
    if (!s || !s.converting) continue; // deleted while waiting
    try {
      const out = await convert(s);
      if (store.mediaRow(s.id) !== s) { store.removeUpload(out.file); continue; } // deleted while converting
      store.removeUpload(s.file);
      Object.assign(s, out, { converting: false });
      delete s.convert_error;
    } catch (e) {
      console.error(`video #${s.id}:`, e.message);
      Object.assign(s, { converting: false, convert_error: e instanceof UserError ? e.message : 'conversion failed' });
    }
    if (store.mediaRow(s.id) === s) store.save();
  }
  busy = false;
}

/** Scale the long side down to `size` (never up), keep the aspect ratio, even dimensions. */
const scale = size => `scale='if(gte(iw,ih),min(${size},iw),-2)':'if(gte(iw,ih),-2,min(${size},ih))':flags=lanczos`;

function outputArgs(webp, size, fps) {
  const vf = `fps=${fps},${scale(size)}`;
  return webp
    ? ['-vf', vf, '-c:v', 'libwebp_anim', '-lossless', '0', '-q:v', '70', '-compression_level', '4', '-loop', '0', '-f', 'webp']
    : ['-vf', `${vf},split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4`, '-loop', '0', '-f', 'gif'];
}

/** Convert one stored video. Tries the configured size first, then a smaller, slower one if the result is too big. */
async function convert(s) {
  const webp = ffmpeg.webp, [mime, ext] = webp ? ['image/webp', 'webp'] : ['image/gif', 'gif'];
  const src = store.uploadPath(s.file);
  const tries = [[cfg.videoSize, cfg.videoFps], [Math.min(320, cfg.videoSize), Math.min(10, cfg.videoFps)]];
  for (const [size, fps] of tries) {
    const file = store.writeUpload(Buffer.alloc(0), ext), out = store.uploadPath(file);
    const r = await run(['-v', 'error', '-protocol_whitelist', 'file', '-f', DEMUXER[s.mime], '-t', String(cfg.videoMaxSeconds), '-i', src,
      '-an', '-sn', '-threads', '2', ...outputArgs(webp, size, fps), '-y', out], cfg.videoTimeoutSeconds * 1000, true).catch(e => ({ code: -1, stderr: e.message }));
    const bytes = fs.existsSync(out) ? fs.statSync(out).size : 0;
    if (r.code !== 0 || !bytes) {
      store.removeUpload(file);
      throw new Error(r.stderr.trim().split('\n').pop() || 'ffmpeg failed');
    }
    if (bytes <= cfg.maxUploadBytes) return { file, mime, bytes };
    store.removeUpload(file);
  }
  throw new UserError(`the converted GIF was larger than ${cfg.maxUploadBytes / 1048576} MB, try a shorter clip`);
}

/** At startup: find ffmpeg (downloading it if missing), then pick up conversions a restart interrupted. */
async function start() {
  const auto = cfg.autoInstallFfmpeg && !cfg.ffmpegPath;
  await detect(!auto);
  if (!ffmpeg.ok && auto) await autoInstall();
  if (auto) await detect();
  for (const s of [...store.db().submissions, ...store.db().proposals]) {
    if (!s.converting) continue;
    if (ffmpeg.ok) enqueue(s.id);
    else { s.converting = false; s.convert_error = 'ffmpeg is not installed on the server'; store.save(); }
  }
}

module.exports = { isVideo, status, maxBytes, acceptMedia, addSubmission, addProposal, enqueue, start, detect };

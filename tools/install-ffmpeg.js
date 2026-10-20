// Installs a static ffmpeg build for video uploads, without sudo, into ~/.cache/game-animation-library/ffmpeg
// (the site user's home, so deploys keep it). Does nothing when ffmpeg is already installed.
//   npm run install-ffmpeg           # also runs on `npm install` and, when needed, when the app starts
//   node tools/install-ffmpeg.js --force
// Downloads the newest release build for this CPU from https://github.com/BtbN/FFmpeg-Builds (Linux x64 / arm64),
// checks it against the published SHA-256, and unpacks just the ffmpeg program (needs `tar` with xz support).
// It never fails the deploy: on any problem it prints what to do instead (sudo apt install ffmpeg) and exits 0.
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');
const { Readable } = require('stream');
const { pipeline } = require('stream/promises');

const DIR = path.join(os.homedir(), '.cache', 'game-animation-library');
const BIN = path.join(DIR, 'ffmpeg');
const BASE = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/';
const ARCH = { x64: 'linux64', arm64: 'linuxarm64' }[process.arch];

const works = bin => spawnSync(bin, ['-hide_banner', '-version'], { stdio: 'ignore', timeout: 15000 }).status === 0;

async function install({ force = false } = {}) {
  if (!force && (works(process.env.FFMPEG_PATH || 'ffmpeg') || works(BIN))) return 'ffmpeg is already installed';
  if (process.platform !== 'linux' || !ARCH) return `no ffmpeg download for ${process.platform}/${process.arch}, install ffmpeg yourself`;

  // The release's checksum list also tells us the current file name (it carries the version number).
  const sums = await (await fetch(BASE + 'checksums.sha256', { signal: AbortSignal.timeout(30000) })).text();
  const builds = [...sums.matchAll(new RegExp(`^([0-9a-f]{64})\\s+(ffmpeg-n(\\d+)\\.(\\d+)-latest-${ARCH}-gpl-[\\d.]+\\.tar\\.xz)$`, 'gm'))]
    .sort((a, b) => b[3] - a[3] || b[4] - a[4]);
  if (!builds.length) throw new Error('no release build listed for ' + ARCH);
  const [, sha, name] = builds[0];

  fs.mkdirSync(DIR, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(DIR, 'download-'));
  try {
    console.log(`Downloading ${name} (about 150 MB)…`);
    const res = await fetch(BASE + name, { signal: AbortSignal.timeout(15 * 60e3) });
    if (!res.ok) throw new Error(`download failed (HTTP ${res.status})`);
    const archive = path.join(tmp, name), hash = crypto.createHash('sha256');
    const body = Readable.fromWeb(res.body);
    body.on('data', c => hash.update(c));
    await pipeline(body, fs.createWriteStream(archive));
    if (hash.digest('hex') !== sha) throw new Error('the download does not match its published checksum');
    const tar = spawnSync('tar', ['-xJf', archive, '-C', tmp, '--strip-components=2', '--wildcards', '*/bin/ffmpeg'], { encoding: 'utf8' });
    if (tar.status !== 0) throw new Error('could not unpack it: ' + (tar.stderr || tar.error?.message || '').trim());
    fs.chmodSync(path.join(tmp, 'ffmpeg'), 0o755);
    if (!works(path.join(tmp, 'ffmpeg'))) throw new Error('the downloaded ffmpeg does not run on this server');
    fs.renameSync(path.join(tmp, 'ffmpeg'), BIN);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  return 'installed ffmpeg at ' + BIN;
}

module.exports = { BIN, install };

if (require.main === module) {
  install({ force: process.argv.includes('--force') })
    .then(msg => console.log('install-ffmpeg: ' + msg))
    .catch(e => console.log(`install-ffmpeg: ${e.message}. Video uploads need ffmpeg: run "sudo apt install ffmpeg" on the server instead (see DEPLOY-XCLOUD.md).`));
}

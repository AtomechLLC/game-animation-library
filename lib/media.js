// Downloading submitted links and searching Giphy/Tenor for replacement candidates.
'use strict';
const http = require('http');
const https = require('https');
const net = require('net');
const dns = require('dns');
const cfg = require('./config');
const store = require('./store');
const video = require('./video');
const { UserError } = require('./http');

// Addresses a submitted link may never reach: localhost, private networks, link-local, reserved and documentation ranges.
const blocked = new net.BlockList();
for (const [a, p] of [['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8], ['169.254.0.0', 16], ['172.16.0.0', 12], ['192.0.0.0', 24], ['192.0.2.0', 24], ['192.168.0.0', 16], ['198.18.0.0', 15], ['198.51.100.0', 24], ['203.0.113.0', 24], ['224.0.0.0', 4], ['240.0.0.0', 4]]) blocked.addSubnet(a, p, 'ipv4');
for (const [a, p] of [['::', 127], ['fc00::', 7], ['fe80::', 10], ['ff00::', 8], ['64:ff9b::', 96], ['2001:db8::', 32]]) blocked.addSubnet(a, p, 'ipv6');

function isPublicIp(ip) {
  const mapped = ip.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/i);
  if (mapped) ip = mapped[1];
  const family = net.isIP(ip);
  return family !== 0 && !blocked.check(ip, family === 4 ? 'ipv4' : 'ipv6');
}

// Checked on every connection, so a hostname cannot be re-pointed at a private address between check and connect.
function safeLookup(hostname, options, cb) {
  dns.lookup(hostname, { all: true }, (err, addrs) => {
    if (err) return cb(new UserError('could not find that website'));
    if (!addrs.length || addrs.some(a => !module.exports.isPublicIp(a.address))) return cb(new UserError('that address is not allowed'));
    options.all ? cb(null, addrs) : cb(null, addrs[0].address, addrs[0].family);
  });
}

/** One GET with a size cap and no automatic redirects. Resolves { status, location, body }. */
function getOnce(url, max) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const host = u.hostname.replace(/^\[|\]$/g, '');
    if (net.isIP(host) && !module.exports.isPublicIp(host)) return reject(new UserError('that address is not allowed'));
    const req = (u.protocol === 'https:' ? https : http).get(u, {
      lookup: safeLookup,
      timeout: 20000,
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; game-animation-library)', Accept: 'image/gif,image/webp,video/mp4,text/html;q=0.8,*/*;q=0.5' },
    }, res => {
      if (res.statusCode >= 300 && res.statusCode < 400) { res.resume(); return resolve({ status: res.statusCode, location: res.headers.location }); }
      const chunks = [];
      let size = 0;
      res.on('data', c => {
        size += c.length;
        if (size > max) { req.destroy(); reject(new UserError('that file is too large')); } else chunks.push(c);
      });
      res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(chunks) }));
      res.on('error', reject);
    });
    req.on('timeout', () => req.destroy(new UserError('that link took too long to answer')));
    req.on('error', e => reject(e instanceof UserError ? e : new UserError('could not download that link')));
  });
}

/**
 * Download a GIF / WebP / MP4 (or another short video, converted, see video.js) from a link and store it in DATA_DIR/uploads, so the site never hotlinks
 * community media (a link could be swapped for something else after it was approved).
 * Accepts a direct media link or a page (Giphy, Tenor, …) whose og:video / og:image points at one.
 * Only public addresses on ports 80/443 are fetched, each redirect is re-checked, and the size is capped.
 * Returns { file, mime, bytes } (plus converting: true for a video still to convert); throws UserError with a reason the submitter can read.
 */
async function fetchMedia(url, depth = 0) {
  for (let hop = 0; hop < 5; hop++) {
    let u;
    try { u = new URL(url); } catch { throw new UserError('that does not look like a web address'); }
    if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password) throw new UserError('that does not look like a web address');
    if (u.port && !['80', '443'].includes(u.port)) throw new UserError('that link uses an unsupported port');
    const r = await getOnce(u.href, video.maxBytes());
    if (r.location) { url = new URL(r.location, u).href; continue; }
    if (r.status >= 400) throw new UserError('could not download that link');
    const stored = await video.acceptMedia(r.body);
    if (stored) return stored;
    // A page: follow its og:video / og:image once (Giphy and Tenor pages point at the GIF this way).
    if (depth === 0) {
      const html = r.body.toString('utf8');
      const cands = [];
      for (const tag of html.match(/<meta[^>]+(?:property|name)=["'](?:og:video(?::secure_url|:url)?|og:image(?::secure_url|:url)?|twitter:image)["'][^>]*>/gi) || []) {
        const c = tag.match(/content=["']([^"']+)/i);
        if (c) cands.push(c[1].replace(/&amp;/g, '&'));
      }
      // Prefer animated formats over a still preview image.
      const animated = s => /\.(gif|webp|mp4|webm|mov)(\?|$)/i.test(s);
      cands.sort((a, b) => animated(b) - animated(a));
      for (const c of cands) {
        try { return await fetchMedia(new URL(c, u).href, 1); } catch { /* try the next one */ }
      }
    }
    throw new UserError(video.status().on ? 'no GIF, WebP or video found at that link, upload the file or use a direct link' : 'no GIF, WebP or MP4 found at that link, upload the file or use a direct link');
  }
  throw new UserError('that link redirects too many times');
}

async function getJson(url) {
  try {
    const r = await fetch(url, { headers: { 'User-Agent': 'game-animation-library' }, signal: AbortSignal.timeout(15000) });
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

/**
 * Search Giphy and/or Tenor for replacement candidates for one flagged GIF and store them
 * as pending submissions (source 'search') for the owner to review. Returns a short result line.
 */
async function searchReplacements(target, animation) {
  const a = store.library()[animation];
  if (!a) return 'unknown animation';
  if (!cfg.giphyApiKey && !cfg.tenorApiKey) return 'no search provider configured'; // stays queued until a key is added
  const query = ((a.example_games || [])[0] || '') + ' ' + a.name;
  const known = new Set();
  for (const g of a.gifs || []) [g.page_url, g.media_url, g.source_url].forEach(x => x && known.add(x));
  for (const s of store.db().submissions) if (s.animation === animation && s.url) known.add(s.url);
  const n = cfg.searchCandidates, found = [];
  if (cfg.giphyApiKey) {
    const j = await getJson('https://api.giphy.com/v1/gifs/search?' + new URLSearchParams({ api_key: cfg.giphyApiKey, q: query.trim(), limit: n * 2, rating: 'pg-13' }));
    for (const g of j?.data || []) {
      const media = g.images?.fixed_width?.webp || g.images?.fixed_width?.url;
      if (media) found.push({ page: g.url || '', media, title: g.title || '', host: 'Giphy' });
    }
  }
  if (cfg.tenorApiKey) {
    const j = await getJson('https://tenor.googleapis.com/v2/search?' + new URLSearchParams({ key: cfg.tenorApiKey, q: query.trim(), limit: n * 2, media_filter: 'tinygif,gif', contentfilter: 'medium' }));
    for (const g of j?.results || []) {
      const media = g.media_formats?.tinygif?.url || g.media_formats?.gif?.url;
      if (media) found.push({ page: g.itemurl || '', media, title: g.content_description || '', host: 'Tenor' });
    }
  }
  let added = 0;
  for (const f of found) {
    if (added >= n) break;
    if (known.has(f.media) || known.has(f.page)) continue;
    known.add(f.media);
    let m;
    try { m = await fetchMedia(f.media); } catch { continue; }
    video.addSubmission({ animation, replaces: target, url: f.media, ...m, note: [f.title, f.page].filter(Boolean).join(' · '), submitter: f.host + ' search: ' + query.trim(), source: 'search' });
    added++;
  }
  const result = `${added} candidates from "${query.trim()}"`;
  const q = store.db().queue[target];
  if (q) { q.searched_at = store.now(); q.result = result; store.save(); }
  return result;
}

/** Search every flagged GIF that has not been searched yet (runs on a timer in server.js). */
async function searchFlagged() {
  for (const [target, q] of Object.entries(store.db().queue)) {
    if (!q.searched_at) console.log(q.animation, '|', target, '->', await searchReplacements(target, q.animation));
  }
}

module.exports = { UserError, isPublicIp, fetchMedia, searchReplacements, searchFlagged };

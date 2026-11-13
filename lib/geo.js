'use strict';
/**
 * Is a visitor in Austria? Answers /geo.json for shared/appbar.js, which hides the Previewer tab there.
 * The hosting has no CDN country header, so the visitor's IP is checked against lib/geo-at.json: the ranges RIPE NCC
 * has delegated to Austrian holders (built by tools/geo/build_at_ranges.py). Registration country is close to, not
 * the same as, where someone is: VPNs and roaming phones can land either side. An IP that can't be read counts as
 * not Austrian, so the tab shows.
 */
const fs = require('fs');
const path = require('path');

let DATA = null;
function data() {
  if (!DATA) {
    const d = JSON.parse(fs.readFileSync(path.join(__dirname, 'geo-at.json'), 'utf8'));
    DATA = { country: d.country, v4: d.ipv4, v6: d.ipv6.map(n => { const [a, len] = n.split('/'); return [v6big(a), +len] }).filter(x => x[0] != null) };
  }
  return DATA;
}

function v4int(ip) {
  const p = ip.split('.');
  if (p.length !== 4) return null;
  let n = 0;
  for (const s of p) { if (!/^\d{1,3}$/.test(s) || +s > 255) return null; n = n * 256 + +s }
  return n;
}
function v6big(ip) {
  if (!/^[0-9a-f:]+$/i.test(ip) || (ip.match(/::/g) || []).length > 1) return null;
  const [l, r] = ip.split('::'), L = l ? l.split(':') : [], R = r != null && r ? r.split(':') : [];
  const fill = r != null ? 8 - L.length - R.length : 0;
  if (fill < 0 || (r == null && L.length !== 8)) return null;
  const parts = [...L, ...Array(fill).fill('0'), ...R];
  let n = 0n;
  for (const h of parts) { if (!/^[0-9a-f]{1,4}$/i.test(h)) return null; n = (n << 16n) + BigInt(parseInt(h, 16)) }
  return n;
}

function inV4(n) {
  const r = data().v4;
  let lo = 0, hi = r.length - 1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (n < r[m][0]) hi = m - 1; else if (n > r[m][1]) lo = m + 1; else return true }
  return false;
}

/** The two-letter country for an IP when it is one we know (only 'AT'), otherwise ''. */
function countryOf(ip) {
  ip = String(ip || '').trim().replace(/^\[|\]$/g, '');
  const mapped = ip.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/i);
  if (mapped) ip = mapped[1];
  if (ip.includes('.')) { const n = v4int(ip); return n != null && inV4(n) ? data().country : '' }
  const n = v6big(ip.split('%')[0]);
  if (n == null) return '';
  return data().v6.some(([a, len]) => (n >> BigInt(128 - len)) === (a >> BigInt(128 - len))) ? data().country : '';
}

module.exports = { countryOf };

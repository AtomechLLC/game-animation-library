// Admin session cookie, shared by the review page (/admin) and the admin-only API actions on the atlas.
'use strict';
const crypto = require('crypto');
const cfg = require('./config');
const fs = require('fs');
const path = require('path');
const { cookies } = require('./http');

/**
 * Key for signing the admin session: SECRET, or without it a random key kept in DATA_DIR. The fallback SECRET
 * is derived from the hostname, which anyone could guess and use to forge a session cookie.
 */
function sessionKey() {
  if (cfg.secretSet) return cfg.secret;
  const file = path.join(cfg.dataDir, 'session-key');
  try { return fs.readFileSync(file, 'utf8').trim(); } catch { /* first start */ }
  const key = crypto.randomBytes(32).toString('hex');
  fs.writeFileSync(file, key, { mode: 0o600 });
  console.log('SECRET is not set: signing admin sessions with a random key in ' + file + ' (run `npm run secret` and add it to .env)');
  return key;
}
const KEY = sessionKey();

const sign = s => crypto.createHmac('sha256', KEY).update(s).digest('hex');

/** The signed-in admin's session cookie value, or null. */
function session(req) {
  if (!cfg.adminPasswordHash) return null;
  const c = cookies(req).libadmin || '';
  const [exp, mac] = c.split('.');
  if (!exp || !mac || Number(exp) < Date.now()) return null;
  const want = sign('admin:' + exp);
  return mac.length === want.length && crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(want)) ? c : null;
}

/** CSRF token for a session: echoed in review-page forms and in the X-Admin-Token header on the atlas. */
const csrfFor = sess => sign('csrf:' + sess);

module.exports = { sign, session, csrfFor };

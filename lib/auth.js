// Admin session cookie, shared by the review page (/admin) and the admin-only API actions on the atlas.
'use strict';
const crypto = require('crypto');
const cfg = require('./config');
const { cookies } = require('./http');

const sign = s => crypto.createHmac('sha256', cfg.secret).update(s).digest('hex');

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

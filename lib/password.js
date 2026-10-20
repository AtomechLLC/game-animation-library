// Review page password hashing (scrypt, built into Node).
'use strict';
const crypto = require('crypto');

/** "scrypt$<saltHex>$<hashHex>" from `npm run hash-password` */
function hashPassword(pw) {
  const salt = crypto.randomBytes(16);
  return 'scrypt$' + salt.toString('hex') + '$' + crypto.scryptSync(pw, salt, 32).toString('hex');
}
function verifyPassword(pw, stored) {
  const [kind, salt, hash] = String(stored).split('$');
  if (kind !== 'scrypt' || !salt || !hash) return false;
  const got = crypto.scryptSync(pw, Buffer.from(salt, 'hex'), 32);
  const want = Buffer.from(hash, 'hex');
  return want.length === got.length && crypto.timingSafeEqual(got, want);
}

module.exports = { hashPassword, verifyPassword };

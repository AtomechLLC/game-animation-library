// Prints the ADMIN_PASSWORD_HASH line for .env.
//   npm run hash-password                 # asks for the password
//   node tools/hash-password.js 'secret'  # or pass it in
'use strict';
const { hashPassword } = require('../lib/password');

function done(pw) {
  if (!pw) { console.error('Empty password.'); process.exit(1); }
  console.log('ADMIN_PASSWORD_HASH=' + hashPassword(pw));
}
if (process.argv[2]) done(process.argv[2]);
else {
  process.stdout.write('Review page password: ');
  process.stdin.once('data', d => { done(String(d).trim()); process.exit(0); });
}

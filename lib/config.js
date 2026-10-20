// Settings come from environment variables, or a .env file next to server.js (xCloud keeps it across deploys).
// See .env.example for every option.
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');

function loadDotEnv(file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (!m || process.env[m[1]] !== undefined) continue;
    process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, '$2');
  }
}
loadDotEnv(path.join(ROOT, '.env'));

const env = (k, d = '') => (process.env[k] ?? '').trim() || d;
const num = (k, d) => Number(env(k, String(d))) || d;

// Default: a folder in the site user's home (always writable, and outside the folder deploys replace).
const dataDir = path.resolve(ROOT, env('DATA_DIR', path.join(require('os').homedir(), 'library-data')));

module.exports = {
  ROOT,
  port: num('PORT', 3000),
  host: env('HOST', '127.0.0.1'),
  // Uploaded GIFs and db.json live here. Keep it outside the app folder so deploys never touch it.
  dataDir,
  // scrypt hash from `npm run hash-password`; empty disables /admin
  adminPasswordHash: env('ADMIN_PASSWORD_HASH'),
  // Long random string used to sign the admin session and hash IPs / voter tokens
  secret: env('SECRET') || 'unset-secret-' + require('os').hostname(),
  maxUploadBytes: num('MAX_UPLOAD_MB', 8) * 1024 * 1024,
  votesPerHour: num('VOTES_PER_HOUR', 300),
  submissionsPerHour: num('SUBMISSIONS_PER_HOUR', 10),
  // A library GIF is flagged for a replacement search once it has at least flagMinDownvotes
  // downvotes and (downvotes - upvotes) >= flagNetScore
  flagMinDownvotes: num('FLAG_MIN_DOWNVOTES', 3),
  flagNetScore: num('FLAG_NET_SCORE', 2),
  // Replacement search providers (optional)
  giphyApiKey: env('GIPHY_API_KEY'),
  tenorApiKey: env('TENOR_API_KEY'),
  searchCandidates: num('SEARCH_CANDIDATES', 4),
  searchEveryMinutes: num('SEARCH_EVERY_MINUTES', 60),
  // Other origins allowed to call /api (e.g. https://atomechllc.github.io), comma-separated
  allowedOrigins: env('ALLOWED_ORIGINS').split(',').map(s => s.trim()).filter(Boolean),
  // Behind xCloud's Nginx the visitor IP arrives in X-Real-IP / X-Forwarded-For
  trustProxy: env('TRUST_PROXY', '1') !== '0',
};

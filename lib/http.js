// Small request/response helpers: body reading with a size cap, multipart and urlencoded forms, cookies, client IP.
'use strict';
const cfg = require('./config');

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

/** A problem with what a visitor submitted, with a message they can read. */
class UserError extends Error {}

function readBody(req, max) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', c => {
      size += c.length;
      // Too big: stop keeping the bytes but let the upload finish, so the error response still reaches the browser.
      if (size > max) { chunks.length = 0; reject(new HttpError(413, 'file is too large')); } else chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

/** Parse multipart/form-data. Returns { fields: {name: string}, files: {name: {filename, data}} }. */
function parseMultipart(buf, contentType) {
  const m = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(contentType || '');
  if (!m) throw new HttpError(400, 'bad form');
  const sep = Buffer.from('--' + (m[1] || m[2]));
  const out = { fields: {}, files: {} };
  let pos = buf.indexOf(sep);
  while (pos !== -1) {
    let start = pos + sep.length;
    if (buf.subarray(start, start + 2).toString() === '--') break;
    start += 2; // CRLF after the boundary
    const next = buf.indexOf(sep, start);
    if (next === -1) break;
    const part = buf.subarray(start, next - 2); // drop CRLF before the next boundary
    const headEnd = part.indexOf('\r\n\r\n');
    if (headEnd !== -1) {
      const head = part.subarray(0, headEnd).toString('utf8');
      const data = part.subarray(headEnd + 4);
      const name = /name="([^"]*)"/i.exec(head)?.[1];
      const filename = /filename="([^"]*)"/i.exec(head)?.[1];
      if (name !== undefined) {
        if (filename !== undefined) out.files[name] = { filename, data };
        else out.fields[name] = data.toString('utf8');
      }
    }
    pos = next;
  }
  return out;
}

async function readForm(req, max) {
  const type = req.headers['content-type'] || '';
  const buf = await readBody(req, max);
  if (/^multipart\/form-data/i.test(type)) return parseMultipart(buf, type);
  if (/^application\/json/i.test(type)) {
    try { return { fields: JSON.parse(buf.toString('utf8')) || {}, files: {} }; } catch { throw new HttpError(400, 'bad JSON'); }
  }
  return { fields: Object.fromEntries(new URLSearchParams(buf.toString('utf8'))), files: {} };
}

function cookies(req) {
  const out = {};
  for (const c of (req.headers.cookie || '').split(';')) {
    const i = c.indexOf('=');
    if (i > 0) try { out[c.slice(0, i).trim()] = decodeURIComponent(c.slice(i + 1).trim()); } catch { /* malformed, skip it */ }
  }
  return out;
}

function clientIp(req) {
  if (cfg.trustProxy) {
    const real = req.headers['x-real-ip'];
    if (real) return String(real).trim();
    const fwd = String(req.headers['x-forwarded-for'] || '').split(',').map(s => s.trim()).filter(Boolean);
    if (fwd.length) return fwd[fwd.length - 1];
  }
  return req.socket.remoteAddress || '0.0.0.0';
}

function send(res, status, body, headers = {}) {
  res.writeHead(status, { 'X-Content-Type-Options': 'nosniff', ...headers });
  res.end(body);
}

const json = (res, status, data) => send(res, status, JSON.stringify(data), { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });

module.exports = { HttpError, UserError, readBody, readForm, cookies, clientIp, send, json };

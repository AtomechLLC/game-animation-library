// Owner review page (/admin): approve (as a replacement or an extra GIF) or reject community and search-found GIFs,
// see GIFs flagged by downvotes, run a replacement search on demand, and export approved GIFs as JSON.
'use strict';
const crypto = require('crypto');
const cfg = require('./config');
const store = require('./store');
const { fetchMedia, searchReplacements } = require('./media');
const { sendUpload } = require('./api');
const { readForm, cookies, clientIp, send } = require('./http');
const { verifyPassword } = require('./password');
const { sign, session, csrfFor } = require('./auth');

const SESSION_HOURS = 12;
const e = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function cookie(req, name, value, maxAge) {
  const secure = req.headers['x-forwarded-proto'] === 'https' || req.socket.encrypted ? '; Secure' : '';
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${maxAge}${secure}`;
}

const page = (title, body, extraHead = '') => `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>${e(title)}</title>${extraHead}</head>${body}</html>`;
const html = (res, status, body, headers = {}) => send(res, status, body, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY', ...headers });
const redirect = (res, to, headers = {}) => send(res, 303, '', { Location: to, ...headers });

function loginPage(res, csrf, error) {
  html(res, 200, page('Library review', `<style>body{font:15px system-ui;max-width:360px;margin:15vh auto;padding:0 16px}input,button{font:inherit;padding:8px;width:100%;margin-top:8px;box-sizing:border-box}.err{color:#c2412d}</style>
<body><h1>Library review</h1>${error ? `<p class="err">${e(error)}</p>` : ''}<form method="post" action="admin"><input type="hidden" name="csrf" value="${e(csrf)}"><input type="password" name="password" placeholder="Password" autofocus required><button>Sign in</button></form></body>`));
}

function media(src, mime) {
  if (mime === 'video/mp4' || /\.mp4(\?|$)/i.test(src)) return `<video src="${e(src)}" autoplay loop muted playsinline></video>`;
  return `<img src="${e(src)}" alt="" loading="lazy" referrerpolicy="no-referrer">`;
}
const form = (csrf, status, act, label, fields, cls = '') =>
  `<form method="post" action="admin?status=${e(status)}"><input type="hidden" name="csrf" value="${e(csrf)}"><input type="hidden" name="do" value="${e(act)}">` +
  Object.entries(fields).map(([k, v]) => `<input type="hidden" name="${e(k)}" value="${e(v)}">`).join('') +
  `<button class="${e(cls)}">${e(label)}</button></form>`;

/** Apply one review action. Returns the message to show. */
async function act(f) {
  const db = store.db(), id = Number(f.id || 0), s = store.submission(id);
  switch (f.do) {
    case 'approve':
    case 'setmode': {
      if (!s) return '';
      if (!s.file) {
        // Link-only rows (from older versions): store a copy first, the public page never hotlinks.
        try { Object.assign(s, await fetchMedia(String(s.url))); } catch (err) { return 'Not approved: ' + err.message; }
      }
      const mode = s.replaces && f.mode === 'replace' ? 'replace' : 'add';
      if (mode === 'replace') {
        // One replacement per library GIF: an earlier one drops back to Community GIFs.
        for (const o of db.submissions) if (o !== s && o.animation === s.animation && o.replaces === s.replaces && o.mode === 'replace') o.mode = 'add';
        delete db.queue[s.replaces];
        delete db.needs[s.replaces];
      }
      Object.assign(s, { status: 'approved', mode, reviewed_at: store.now() });
      store.save();
      if (f.do === 'setmode') return mode === 'replace' ? 'Now replacing the original GIF.' : 'Original GIF restored; this one shows under Community GIFs.';
      return mode === 'replace' ? 'Approved. It now replaces the original GIF on the site.' : 'Approved. It shows under Community GIFs.';
    }
    case 'reject':
      if (s) { Object.assign(s, { status: 'rejected', mode: 'add', reviewed_at: store.now() }); store.save(); }
      return '';
    case 'delete':
      if (s) { store.removeUpload(s.file); db.submissions.splice(db.submissions.indexOf(s), 1); store.save(); }
      return 'Deleted.';
    case 'search':
      return searchReplacements(String(f.target), String(f.animation));
    case 'need':
      if (store.library()[String(f.animation)]) store.setNeed(String(f.animation), String(f.gif || ''), f.on === '1');
      return '';
    case 'unflag':
      delete db.queue[String(f.target)];
      store.save();
      return '';
  }
  return '';
}

function reviewPage(res, csrf, status, msg) {
  const db = store.db(), lib = store.library();
  const counts = { pending: 0, approved: 0, rejected: 0 };
  for (const s of db.submissions) counts[s.status] = (counts[s.status] || 0) + 1;
  const subs = db.submissions.filter(s => s.status === status).slice(-200).reverse();
  const flagged = Object.entries(db.queue).sort((a, b) => b[1].flagged_at.localeCompare(a[1].flagged_at));
  const local = g => g?.local ? `<img src="${e(g.local)}" alt="">` : '<div class="nopreview">no copy</div>';

  const flagHtml = flagged.length ? `<h2>Flagged by downvotes (${flagged.length})</h2>
<p><small>These library GIFs crossed the downvote threshold. Search candidates land in Pending with source “search”.</small></p>
<div class="grid">${flagged.map(([target, q]) => {
    const a = lib[q.animation], g = store.libraryGif(q.animation, target), t = store.tally(target);
    return `<div class="flag"><b>${e(a?.name || q.animation)}</b>${g?.local ? `<img src="${e(g.local)}" alt="">` : ''}
  <small>▲ ${t.up} ▼ ${t.down} · flagged ${e(q.flagged_at)}${q.searched_at ? ' · searched: ' + e(q.result) : ' · not searched yet'}</small>
  <a href="${e(g?.page_url || '#')}" target="_blank" rel="noopener noreferrer">${e(g?.title || target)}</a>
  <div class="acts">${form(csrf, status, 'search', 'Search now', { target, animation: q.animation })}${form(csrf, status, 'unflag', 'Keep this GIF', { target })}</div></div>`;
  }).join('')}</div>` : '';

  const needs = Object.values(db.needs).sort((a, b) => b.marked_at.localeCompare(a.marked_at));
  const needHtml = `<h2>Marked as needing replacement (${needs.length})</h2>
<p><small>Visitors see a “Needs replacement” badge on these and are asked to suggest a better GIF. Mark entries or single GIFs from the <a href="./">atlas</a> while signed in. A GIF's mark clears itself when you approve a replacement for it.</small></p>
${needs.length ? `<div class="grid">${needs.map(n => {
    const a = lib[n.animation], g = n.gif ? store.libraryGif(n.animation, n.gif) : null;
    return `<div class="flag"><b><a href="./#${e(n.animation)}">${e(a?.name || n.animation)}</a></b>${g?.local ? `<img src="${e(g.local)}" alt="">` : ''}
  <small>${n.gif ? 'GIF: ' + e(g?.title || n.gif) : 'Whole entry'} · marked ${e(n.marked_at)}</small>
  <div class="acts">${form(csrf, status, 'need', 'Clear mark', { animation: n.animation, gif: n.gif, on: '0' })}</div></div>`;
  }).join('')}</div>` : '<p><small>Nothing marked.</small></p>'}`;

  const cards = subs.map(s => {
    const a = lib[s.animation], old = s.replaces ? store.libraryGif(s.animation, s.replaces) : null;
    const src = s.file ? 'admin?file=' + s.id : String(s.url || '');
    const acts = [];
    if (s.status !== 'approved') {
      if (old) acts.push(form(csrf, status, 'approve', 'Approve: replace current', { id: s.id, mode: 'replace' }, 'ok'));
      acts.push(form(csrf, status, 'approve', old ? 'Approve as extra GIF' : 'Approve', { id: s.id, mode: 'add' }, old ? '' : 'ok'));
    } else if (old) {
      acts.push(s.mode === 'replace'
        ? form(csrf, status, 'setmode', 'Restore original', { id: s.id, mode: 'add' })
        : form(csrf, status, 'setmode', 'Use as replacement', { id: s.id, mode: 'replace' }));
    }
    if (s.status !== 'rejected') acts.push(form(csrf, status, 'reject', 'Reject', { id: s.id }, 'no'));
    acts.push(form(csrf, status, 'delete', 'Delete', { id: s.id }));
    return `<div class="card"><b>${e(a?.name || s.animation)}</b>
  <small>${s.source === 'search' ? 'Found by search' : 'From ' + e(s.submitter || 'anonymous')} · ${e(s.created_at)}${s.bytes ? ' · ' + Math.round(s.bytes / 1024) + ' KB' : ''}</small>
  ${s.status === 'approved' ? `<small class="badge">${s.replaces && s.mode === 'replace' ? 'Live: replaces the original GIF' : 'Live: under Community GIFs'}</small>` : ''}
  ${old ? `<div class="pair"><div><small>Current</small>${local(old)}</div><div><small>Proposed</small><div class="pv">${media(src, s.mime)}</div></div></div>`
        : `<div class="pv">${media(src, s.mime)}</div><small>New GIF for this entry</small>`}
  ${s.url ? `<small>Source: <a href="${e(s.url)}" target="_blank" rel="noopener noreferrer">${e(s.url)}</a></small>` : ''}
  ${s.note ? `<small>${e(s.note)}</small>` : ''}
  <div class="acts">${acts.join('')}</div></div>`;
  }).join('');

  html(res, 200, page('Library review', `<body class="blur"><main>
<h1>Library review</h1>
${msg ? `<div class="msg">${e(msg)}</div>` : ''}
<nav>${['pending', 'approved', 'rejected'].map(st => `<a class="${st === status ? 'on' : ''}" href="admin?status=${st}">${st[0].toUpperCase() + st.slice(1)} (${counts[st]})</a>`).join('')}
<a href="admin?export=1">Export approved JSON</a> <a href="./">Open atlas (mark entries)</a>
<label><input type="checkbox" id="blur" checked> Blur submitted GIFs until clicked</label>
<form method="post" action="admin" style="margin-left:auto"><input type="hidden" name="csrf" value="${e(csrf)}"><input type="hidden" name="do" value="logout"><button>Sign out</button></form></nav>
${flagHtml}
${needHtml}
<h2>${status[0].toUpperCase() + status.slice(1)} submissions</h2>
${subs.length ? '' : '<p><small>Nothing here.</small></p>'}
<div class="grid">${cards}</div>
</main>
<script>
const b=document.getElementById('blur');let on=true;try{on=localStorage.getItem('libadmin-blur')!=='0'}catch(e){}
b.checked=on;document.body.classList.toggle('blur',on);
b.onchange=()=>{document.body.classList.toggle('blur',b.checked);try{localStorage.setItem('libadmin-blur',b.checked?'1':'0')}catch(e){}};
document.addEventListener('click',e=>{const p=e.target.closest('.pv');if(p&&document.body.classList.contains('blur'))p.classList.toggle('shown')});
</script></body>`, `<style>
body{font:14px/1.45 system-ui,sans-serif;margin:0;background:#f3f2ee;color:#1c1b19}
@media (prefers-color-scheme:dark){body{background:#17181a;color:#ecebe6}.card,.flag{background:#202125!important;border-color:#33343a!important}}
main{max-width:1100px;margin:0 auto;padding:16px}
nav{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px}nav form{margin:0}
nav a{padding:6px 12px;border:1px solid #d8d5cc;border-radius:6px;text-decoration:none;color:inherit}
nav a.on{background:#1c1b19;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.card,.flag{background:#fff;border:1px solid #d8d5cc;border-radius:6px;padding:10px;display:grid;gap:6px;align-content:start;min-width:0}
.card img,.card video,.flag img{width:100%;border-radius:4px;background:#e9e7e1}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:6px}.pair small{display:block;color:#6b6860}
.nopreview{padding:24px 8px;text-align:center;color:#6b6860;border:1px dashed #d8d5cc;border-radius:4px}
.acts{display:flex;gap:6px;flex-wrap:wrap}.acts form{margin:0}
button{font:inherit;padding:5px 10px;border-radius:4px;border:1px solid #d8d5cc;background:#efece5;cursor:pointer}
button.ok{background:#2f7a6b;color:#fff;border-color:#2f7a6b}button.no{background:#c2412d;color:#fff;border-color:#c2412d}
a{overflow-wrap:anywhere}small{color:#6b6860}.msg{padding:8px 12px;background:#ffb02033;border-radius:6px;margin-bottom:12px}
h2{margin:24px 0 8px}
.badge{font-weight:600;color:#2f7a6b}
/* Submitted media stays blurred until you click it (or turn blurring off), so nothing explicit flashes on screen. */
.card .pv{position:relative;overflow:hidden;border-radius:4px;cursor:pointer}
.card .pv>*{display:block}
body.blur .card .pv:not(.shown)>*{filter:blur(22px) saturate(.4)}
body.blur .card .pv:not(.shown)::after{content:"Click to view";position:absolute;inset:0;display:grid;place-items:center;font-weight:600;color:#fff;text-shadow:0 1px 3px #000}
</style>`));
}

// Flash messages survive the redirect after a POST in a short-lived cookie.
async function handle(req, res, q) {
  if (!cfg.adminPasswordHash) return html(res, 503, 'Review page is disabled. Set ADMIN_PASSWORD_HASH in .env (see DEPLOY-XCLOUD.md).');
  const c = cookies(req), sess = session(req);
  const status = ['pending', 'approved', 'rejected'].includes(q.get('status')) ? q.get('status') : 'pending';

  if (!sess) {
    // Before sign-in, CSRF is a random cookie echoed in the form (double submit).
    let token = /^[0-9a-f]{32}$/.test(c.libcsrf || '') ? c.libcsrf : crypto.randomBytes(16).toString('hex');
    const setCsrf = { 'Set-Cookie': cookie(req, 'libcsrf', token, 3600) };
    if (req.method === 'POST') {
      const { fields } = await readForm(req, 10000);
      if (fields.csrf !== token) return redirect(res, 'admin', setCsrf);
      if (!store.rateOk(clientIp(req), 'login', 10)) return html(res, 429, 'Too many attempts, try again later.');
      if (fields.password && verifyPassword(String(fields.password), cfg.adminPasswordHash)) {
        const exp = Date.now() + SESSION_HOURS * 3600e3;
        return redirect(res, 'admin', { 'Set-Cookie': cookie(req, 'libadmin', exp + '.' + sign('admin:' + exp), SESSION_HOURS * 3600) });
      }
      res.setHeader('Set-Cookie', setCsrf['Set-Cookie']);
      return loginPage(res, token, 'Wrong password.');
    }
    res.setHeader('Set-Cookie', setCsrf['Set-Cookie']);
    return loginPage(res, token);
  }

  const csrf = csrfFor(sess);
  if (req.method === 'POST') {
    const { fields } = await readForm(req, 10000);
    if (fields.csrf !== csrf) return html(res, 400, 'Stale form, reload the page.');
    if (fields.do === 'logout') return redirect(res, 'admin', { 'Set-Cookie': cookie(req, 'libadmin', '', 0) });
    const msg = await act(fields);
    return redirect(res, 'admin?status=' + status, msg ? { 'Set-Cookie': cookie(req, 'libmsg', msg, 60) } : {});
  }

  // Stored file preview (any status) for the signed-in owner
  if (q.has('file')) {
    const s = store.submission(Number(q.get('file')));
    if (!s || !s.file) return send(res, 404, '');
    return sendUpload(res, s, 'private, no-store');
  }
  if (q.has('export')) {
    const rows = store.db().submissions.filter(s => s.status === 'approved').map(({ voter, ip, ...s }) => ({ ...s, download: s.file ? 'api?action=file&id=' + s.id : null }));
    return send(res, 200, JSON.stringify(rows, null, 2), { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="approved-gifs.json"' });
  }
  if (c.libmsg) res.setHeader('Set-Cookie', cookie(req, 'libmsg', '', 0));
  reviewPage(res, csrf, status, c.libmsg || '');
}

module.exports = { handle };

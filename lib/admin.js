// Owner review page (/admin): approve (as a replacement or an extra GIF) or reject community and search-found GIFs,
// review proposed new animations (exported as taxonomy.txt lines), see GIFs flagged by downvotes, run a replacement search on demand, and export approved GIFs as JSON.
'use strict';
const crypto = require('crypto');
const cfg = require('./config');
const store = require('./store');
const video = require('./video');
const { fetchMedia, searchReplacements } = require('./media');
const { sendUpload, blocklistJson } = require('./api');
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
  html(res, 200, page('Library review · Game Animation Library', `<style>body{font:15px system-ui;max-width:360px;margin:15vh auto;padding:0 16px}input,button{font:inherit;padding:8px;width:100%;margin-top:8px;box-sizing:border-box}.err{color:#c2412d}</style>
<body><h1>Library review</h1>${error ? `<p class="err">${e(error)}</p>` : ''}<form method="post" action="admin"><input type="hidden" name="csrf" value="${e(csrf)}"><input type="password" name="password" placeholder="Password" autofocus required><button>Sign in</button></form></body>`));
}

function media(src, mime) {
  if (String(mime).startsWith('video/') || /\.mp4(\?|$)/i.test(src)) return `<video src="${e(src)}" autoplay loop muted playsinline></video>`;
  return `<img src="${e(src)}" alt="" loading="lazy" referrerpolicy="no-referrer">`;
}
// confirmText: ask before submitting (see the submit listener in reviewPage)
const form = (csrf, status, act, label, fields, cls = '', confirmText = '') =>
  `<form method="post" action="admin?status=${e(status)}"${confirmText ? ` data-confirm="${e(confirmText)}"` : ''}><input type="hidden" name="csrf" value="${e(csrf)}"><input type="hidden" name="do" value="${e(act)}">` +
  Object.entries(fields).map(([k, v]) => `<input type="hidden" name="${e(k)}" value="${e(v)}">`).join('') +
  `<button class="${e(cls)}">${e(label)}</button></form>`;

/** Taxonomy text field: '|' and line breaks would break taxonomy.txt. */
const tx = (v, max) => String(v ?? '').replace(/[|\r\n]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
const list = (v, sep) => String(v || '').split(/[,;]/).map(x => x.trim()).filter(Boolean).join(sep);
const slug = v => String(v).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/** A proposal as a taxonomy.txt line: Name | Subcategory | tags | Game;Game | Description */
const taxLine = p => [p.name, p.subcategory || 'General', list(p.tags, ',') || slug(p.name), list(p.games, ';'), p.description].join(' | ');

/** Every approved proposal as taxonomy.txt lines, grouped under the category they go in (new categories get a header). */
function proposalExport() {
  const cats = store.categories(), groups = new Map();
  for (const p of store.db().proposals.filter(p => p.status === 'approved')) {
    const head = p.category && cats[p.category] ? `# CAT ${p.category} | ${cats[p.category].name} | (existing category: add these lines under its header)`
      : `# CAT ${slug(p.new_category || 'new')} | ${p.new_category || 'New category'} | (describe the new category)`;
    if (!groups.has(head)) groups.set(head, []);
    groups.get(head).push(taxLine(p));
  }
  return `Approved animation proposals, as taxonomy.txt lines. Paste each line under its category header in taxonomy.txt\n(the header lines below only say where; existing headers are already in the file), then run build_index.py and merge.py (see README).\n\n`
    + [...groups].map(([head, lines]) => head + '\n' + lines.join('\n')).join('\n\n') + '\n';
}

/** Apply one action on a proposed new animation (fields are prefixed p_ so they never mix with GIF submissions). */
function actProposal(f) {
  const db = store.db(), p = store.proposal(Number(f.pid || 0));
  if (!p) return '';
  if (f.do === 'pdelete') { store.removeUpload(p.file); db.proposals.splice(db.proposals.indexOf(p), 1); store.save(); return 'Proposal deleted.'; }
  if (f.do === 'preject') { Object.assign(p, { status: 'rejected', reviewed_at: store.now() }); store.save(); return ''; }
  // psave / papprove: keep the reviewer's edits first
  const cat = String(f.p_category || '');
  Object.assign(p, {
    name: tx(f.p_name, 80) || p.name, description: tx(f.p_description, 500) || p.description,
    category: store.categories()[cat] ? cat : '', new_category: store.categories()[cat] ? '' : tx(f.p_new_category, 60) || p.new_category,
    subcategory: tx(f.p_subcategory, 60), tags: tx(f.p_tags, 200), games: tx(f.p_games, 200),
  });
  if (f.do === 'papprove') {
    if (!p.category && !p.new_category) { store.save(); return 'Not approved: choose a category or name a new one.'; }
    if (!list(p.games, ';')) { store.save(); return 'Not approved: add at least one example game, so the entry can be compared across games.'; }
    const id = `${p.category || slug(p.new_category)}.${slug(p.name)}`;
    if (store.library()[id]) { store.save(); return `Not approved: the library already has ${id}. Rename it or reject it as a duplicate.`; }
    Object.assign(p, { status: 'approved', reviewed_at: store.now() });
    store.save();
    return `Approved “${p.name}”. Export the approved proposals to add it to taxonomy.txt.`;
  }
  store.save();
  return 'Proposal saved.';
}

/** Apply one review action. Returns the message to show. */
async function act(f) {
  if (/^p(save|approve|reject|delete)$/.test(f.do)) return actProposal(f);
  const db = store.db(), id = Number(f.id || 0), s = store.submission(id);
  switch (f.do) {
    case 'approve':
    case 'setmode': {
      if (!s) return '';
      if (!s.file) {
        // Link-only rows (from older versions): store a copy first, the public page never hotlinks.
        try { Object.assign(s, await fetchMedia(String(s.url))); } catch (err) { return 'Not approved: ' + err.message; }
        if (s.converting) { store.save(); video.enqueue(s.id); }
      }
      if (s.converting) return 'Not approved yet: the video is still being converted to a GIF. Reload in a moment.';
      if (s.convert_error) return 'Not approved: the video could not be converted (' + s.convert_error + ').';
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
    case 'hide':
    case 'unhide': {
      const animation = String(f.animation || ''), gif = String(f.gif || '');
      if (!gif || (f.do === 'hide' && !store.libraryGif(animation, gif))) return 'Unknown GIF.';
      store.setHidden(animation, gif, f.do === 'hide');
      return f.do === 'hide' ? 'GIF removed and blocklisted. You can restore it under “Removed GIFs”.' : 'GIF restored to the library page.';
    }
    case 'note':
      if (s) { s.note = String(f.note || '').trim().slice(0, 500); store.save(); }
      return s ? 'Note saved.' : '';
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
  const pcounts = { pending: 0, approved: 0, rejected: 0 };
  for (const p of db.proposals) pcounts[p.status] = (pcounts[p.status] || 0) + 1;
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

  // Remove a library GIF for good (it goes on the blocklist; Restore under Removed GIFs undoes it).
  const removeForm = (animation, a, g, label = 'Remove GIF') => form(csrf, status, 'hide', label, { animation, gif: store.gifKey(animation, g) }, 'no',
    `Remove “${g.title || 'this GIF'}” from ${a?.name || animation}? It disappears from the library page and goes on the blocklist, so it is not shown, suggested or fetched again. You can restore it later.`);
  // A whole-entry mark: each of the entry's GIFs that is still shown, with its own Remove button.
  const entryGifs = (animation, a) => {
    const list = store.blocklist(), gifs = (a?.gifs || []).filter(g => !store.isBlockedGif(animation, g, list));
    return gifs.length ? `<div class="egifs">${gifs.map(g => `<div>${g.local ? `<img src="${e(g.local)}" alt="">` : '<div class="nopreview">no copy</div>'}<small>${e(g.title || g.page_url)}</small>${removeForm(animation, a, g, 'Remove')}</div>`).join('')}</div>` : '<small>No GIFs left on this entry.</small>';
  };

  const needs = Object.values(db.needs).sort((a, b) => b.marked_at.localeCompare(a.marked_at));
  const needHtml = `<h2>Marked as needing replacement (${needs.length})</h2>
<p><small>Visitors see a “Needs replacement” badge on these and are asked to suggest a better GIF. Mark entries or single GIFs from the <a href="action-atlas">library page</a> while signed in. A GIF's mark clears itself when you approve a replacement for it.</small></p>
${needs.length ? `<div class="grid">${needs.map(n => {
    const a = lib[n.animation], g = n.gif ? store.libraryGif(n.animation, n.gif) : null;
    return `<div class="flag"><b><a href="./#${e(n.animation)}">${e(a?.name || n.animation)}</a></b>${g?.local ? `<img src="${e(g.local)}" alt="">` : ''}
  <small>${n.gif ? 'GIF: ' + e(g?.title || n.gif) : 'Whole entry'} · marked ${e(n.marked_at)}</small>
  <div class="acts">${form(csrf, status, 'need', 'Clear mark', { animation: n.animation, gif: n.gif, on: '0' })}${n.gif && g ? removeForm(n.animation, a, g) : ''}</div>
  ${n.gif ? '' : entryGifs(n.animation, a)}</div>`;
  }).join('')}</div>` : '<p><small>Nothing marked.</small></p>'}`;

  const hidden = Object.entries(db.hidden).sort((a, b) => b[1].removed_at.localeCompare(a[1].removed_at));
  const hiddenHtml = hidden.length ? `<h2>Removed GIFs (${hidden.length})</h2>
<p><small>Library GIFs you removed. They are on the blocklist: left off the library page across deploys (also under a new file name), refused as suggestions and skipped by replacement searches. The files in the repo are untouched. To keep GIF-gathering scripts from fetching them again, <a href="admin?blocklist=1">export the blocklist</a> and commit it as <code>gif-blocklist.json</code> (see README).</small></p>
<div class="grid">${hidden.map(([gif, h]) => {
    const a = lib[h.animation], g = store.libraryGif(h.animation, gif);
    return `<div class="flag"><b><a href="./#${e(h.animation)}">${e(a?.name || h.animation)}</a></b>${g?.local ? `<img src="${e(g.local)}" alt="">` : ''}
  <small>GIF: ${e(g?.title || h.title || gif)} · removed ${e(h.removed_at)}</small>
  <div class="acts">${form(csrf, status, 'unhide', 'Restore', { animation: h.animation, gif })}</div></div>`;
  }).join('')}</div>` : '';

  // Proposed new animations: editable, since the reviewer usually tidies the name and fills in subcategory and tags.
  const cats = Object.values(store.categories());
  const props = db.proposals.filter(p => p.status === status).slice(-200).reverse();
  const propHtml = `<h2>${status[0].toUpperCase() + status.slice(1)} animation proposals (${props.length})</h2>
<p><small>New animations visitors asked the library to add. Edit the fields, then approve or reject. Approved proposals are not added to the page by themselves: <a href="admin?proposals=1">export them as taxonomy.txt lines</a>, paste them into taxonomy.txt and rebuild (see README).</small></p>
${props.length ? `<div class="grid">${props.map(p => {
    const field = (k, label, v, max) => `<label><small>${label}</small><input name="p_${k}" value="${e(v)}" maxlength="${max}"></label>`;
    return `<div class="card prop"><b>${e(p.name)}</b>
  <small>From ${e(p.submitter || 'anonymous')} · ${e(p.created_at)}${p.bytes ? ' · clip ' + Math.round(p.bytes / 1024) + ' KB' : ''}</small>
  ${p.status === 'approved' ? `<small class="badge">Approved: in the taxonomy export</small><code class="tax">${e(taxLine(p))}</code>` : ''}
  ${p.file ? `<div class="pv">${media('admin?file=' + p.id, p.mime)}</div>` : ''}
  ${p.converting ? '<small class="badge">Converting video to GIF… reload in a moment.</small>' : ''}
  ${p.convert_error ? `<small class="err">Video could not be converted: ${e(p.convert_error)}</small>` : ''}
  ${p.url ? `<small>Example: <a href="${e(p.url)}" target="_blank" rel="noopener noreferrer">${e(p.url)}</a></small>` : ''}
  <form method="post" action="admin?status=${e(status)}" class="note"><input type="hidden" name="csrf" value="${e(csrf)}"><input type="hidden" name="pid" value="${e(p.id)}">
    ${field('name', 'Name', p.name, 80)}
    <label><small>Category</small><select name="p_category">${cats.map(c => `<option value="${e(c.id)}"${c.id === p.category ? ' selected' : ''}>${e(c.name)}</option>`).join('')}<option value=""${p.category ? '' : ' selected'}>New category…</option></select></label>
    ${field('new_category', 'New category name (used when Category is “New category…”)', p.new_category, 60)}
    ${field('subcategory', 'Subcategory', p.subcategory, 60)}
    ${field('tags', 'Tags (comma-separated)', p.tags, 200)}
    ${field('games', 'Example games (comma-separated)', p.games, 200)}
    <label><small>Description</small><textarea name="p_description" rows="3" maxlength="500">${e(p.description)}</textarea></label>
    <div class="acts">${p.status !== 'approved' ? '<button class="ok" name="do" value="papprove">Approve</button>' : ''}<button name="do" value="psave">Save edits</button>${p.status !== 'rejected' ? '<button class="no" name="do" value="preject">Reject</button>' : ''}<button name="do" value="pdelete" data-confirm-btn="Delete this proposal and its clip for good?">Delete</button></div>
  </form></div>`;
  }).join('')}</div>` : '<p><small>Nothing here.</small></p>'}`;

  const cards = subs.map(s => {
    const a = lib[s.animation], old = s.replaces ? store.libraryGif(s.animation, s.replaces) : null;
    const src = s.file ? 'admin?file=' + s.id : String(s.url || '');
    const acts = [];
    if (s.converting || s.convert_error) {
      // Nothing to approve until the GIF exists.
    } else if (s.status !== 'approved') {
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
  ${s.converting ? '<small class="badge">Converting video to GIF… reload in a moment.</small>' : ''}
  ${s.convert_error ? `<small class="err">Video could not be converted: ${e(s.convert_error)}</small>` : ''}
  ${s.converted_from && !s.converting ? `<small>Converted from ${e(s.converted_from)}</small>` : ''}
  ${s.url ? `<small>Source: <a href="${e(s.url)}" target="_blank" rel="noopener noreferrer">${e(s.url)}</a></small>` : ''}
  <form method="post" action="admin?status=${e(status)}" class="note"><input type="hidden" name="csrf" value="${e(csrf)}"><input type="hidden" name="do" value="note"><input type="hidden" name="id" value="${e(s.id)}">
    <label><small>Submitter's note (shown publicly with the GIF once approved)</small><textarea name="note" rows="2" maxlength="500">${e(s.note)}</textarea></label><button>Save note</button></form>
  <div class="acts">${acts.join('')}</div></div>`;
  }).join('');

  html(res, 200, page('Library review · Game Animation Library', `<body class="blur"><main>
<h1>Library review</h1>
${msg ? `<div class="msg">${e(msg)}</div>` : ''}
<nav>${['pending', 'approved', 'rejected'].map(st => `<a class="${st === status ? 'on' : ''}" href="admin?status=${st}">${st[0].toUpperCase() + st.slice(1)} (${counts[st]}${pcounts[st] ? ` + ${pcounts[st]} proposed` : ''})</a>`).join('')}
<a href="admin?export=1">Export approved JSON</a> <a href="admin?proposals=1">Export approved proposals</a> <a href="admin?blocklist=1">Export blocklist</a> <a href="action-atlas">Open library (mark entries)</a>
<small>${(v => v.on ? `Video uploads: on (up to ${v.max_seconds} s, converted to ${v.format === 'webp' ? 'animated WebP' : 'GIF'})` : v.checked ? 'Video uploads: off, ffmpeg is not installed (see DEPLOY-XCLOUD.md)' : '')(video.status())}</small>
<label><input type="checkbox" id="blur" checked> Blur submitted GIFs until clicked</label>
<form method="post" action="admin" style="margin-left:auto"><input type="hidden" name="csrf" value="${e(csrf)}"><input type="hidden" name="do" value="logout"><button>Sign out</button></form></nav>
${flagHtml}
${needHtml}
${hiddenHtml}
${propHtml}
<h2>${status[0].toUpperCase() + status.slice(1)} submissions</h2>
${subs.length ? '' : '<p><small>Nothing here.</small></p>'}
<div class="grid">${cards}</div>
</main>
<script>
const b=document.getElementById('blur');let on=true;try{on=localStorage.getItem('libadmin-blur')!=='0'}catch(e){}
b.checked=on;document.body.classList.toggle('blur',on);
b.onchange=()=>{document.body.classList.toggle('blur',b.checked);try{localStorage.setItem('libadmin-blur',b.checked?'1':'0')}catch(e){}};
document.addEventListener('submit',e=>{const m=e.target.dataset.confirm||e.submitter?.dataset.confirmBtn;if(m&&!confirm(m))e.preventDefault()});
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
.egifs{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:6px}.egifs>div{display:grid;gap:4px;align-content:start}.egifs img{width:100%;border-radius:4px}.egifs form{margin:0}
.note{display:grid;gap:4px;margin:0}.note textarea{font:inherit;width:100%;box-sizing:border-box;padding:4px 6px;border:1px solid #d8d5cc;border-radius:4px;background:transparent;color:inherit}.note button{justify-self:start}
button{font:inherit;padding:5px 10px;border-radius:4px;border:1px solid #d8d5cc;background:#efece5;cursor:pointer}
button.ok{background:#2f7a6b;color:#fff;border-color:#2f7a6b}button.no{background:#c2412d;color:#fff;border-color:#c2412d}
a{overflow-wrap:anywhere}small{color:#6b6860}.msg{padding:8px 12px;background:#ffb02033;border-radius:6px;margin-bottom:12px}
h2{margin:24px 0 8px}
.badge{font-weight:600;color:#2f7a6b}
.prop label{display:grid;gap:2px}.prop input,.prop select{font:inherit;width:100%;box-sizing:border-box;padding:4px 6px;border:1px solid #d8d5cc;border-radius:4px;background:transparent;color:inherit}
.tax{font-size:12px;overflow-wrap:anywhere;background:#0001;padding:4px 6px;border-radius:4px}.err{font-weight:600;color:#c2412d}
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
      // Per visitor, and for everyone together, so a guesser cannot get round the limit by changing address.
      if (!store.rateOk(clientIp(req), 'login', 10) || !store.rateOk('all', 'login', 60)) return html(res, 429, 'Too many attempts, try again later.');
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
    const s = store.mediaRow(Number(q.get('file')));
    if (!s || !s.file) return send(res, 404, '');
    return sendUpload(res, s, 'private, no-store');
  }
  if (q.has('blocklist')) {
    return send(res, 200, JSON.stringify(blocklistJson(), null, 1), { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="gif-blocklist.json"' });
  }
  if (q.has('proposals')) {
    return send(res, 200, proposalExport(), { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename="proposed-animations.txt"' });
  }
  if (q.has('export')) {
    const rows = store.db().submissions.filter(s => s.status === 'approved').map(({ voter, ip, ...s }) => ({ ...s, download: s.file ? 'api?action=file&id=' + s.id : null }));
    return send(res, 200, JSON.stringify(rows, null, 2), { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="approved-gifs.json"' });
  }
  if (c.libmsg) res.setHeader('Set-Cookie', cookie(req, 'libmsg', '', 0));
  reviewPage(res, csrf, status, c.libmsg || '');
}

module.exports = { handle };

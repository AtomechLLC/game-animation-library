// 2D preview for the Frame Data tab: plays a move frame by frame from sprite sheets and draws its boxes on each
// frame, like Baston's hitbox viewer. Everything it loads is written by tools/frame_data/export_baston_sprites.py
// (format in frame-data/README.md, "2D preview"). It has the same interface as viewer3d.js, so the page docks either.
// Frames here are the tab's frames: 1-based, at the game's frame rate (sprites.json fps).
const cache = new Map();
const once = (key, fn) => { if (!cache.has(key)) cache.set(key, fn().catch(e => { cache.delete(key); throw e })); return cache.get(key) };
const json = url => fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json() });
const image = url => new Promise((ok, fail) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => fail(new Error(url)); i.src = url });

export const manifest = base => once(base + 'sprites.json', () => json(base + 'sprites.json'));
// A character's moves: per move id its sheet, cell size, columns and boxes per frame. `frames` becomes the frame
// count the page expects (as in models' moves), the boxes move to `boxes`.
export const classData = async (base, cls) => {
  const m = await manifest(base), c = m.classes[cls];
  return c ? once(base + c.file, () => json(base + c.file).then(d => {
    for (const mv of Object.values(d.moves)) if (Array.isArray(mv.frames)) { mv.boxes = mv.frames; mv.frames = mv.boxes.length }
    return d;
  })) : null;
};

// Box colours, Baston's convention: blue to be hit, red to hit, yellow to throw. A box is [kind, x1, y1, x2, y2]
// (inclusive cell pixels) or [kind, [x, y, ...]] for a polygon collider (Hollow Knight); sprites.json "smooth"
// draws painted art with smoothing instead of whole-pixel pixel-art scaling.
const COLORS = {p: '#2f6bff', v: '#22a7f0', a: '#e5242b', t: '#e0b400', ta: '#8a63d2', pu: '#7d8790'};
const ON = {p: true, v: true, a: true, t: true, ta: false, pu: false};

export async function createViewer(el, base) {
  const man = await manifest(base);
  el.innerHTML = `<div class="v3d-stage"><canvas></canvas><div class="v3d-msg" hidden></div>
    <div class="v3d-hud"><b class="v3d-f">1</b><span class="v3d-state"></span></div></div>
    <div class="v3d-bar">
      <button class="v3d-play" aria-label="Pause">❚❚</button>
      <button class="v3d-prev" aria-label="Back one frame" title="Back one frame (,)">−1 f</button>
      <button class="v3d-next" aria-label="Forward one frame" title="Forward one frame (.)">+1 f</button>
      <div class="v3d-scrub"><div class="v3d-strip"></div><input type="range" min="1" max="1" step="1" value="1" aria-label="Frame"></div>
      <select class="v3d-speed" aria-label="Playback speed"><option value="1">1×</option><option value="0.5">½×</option><option value="0.25">¼×</option><option value="0.1">0.1×</option></select>
    </div>
    <div class="v3d-opts">${Object.entries(man.kinds).map(([k, l]) => `<label title="${l}"><input type="checkbox" data-k="${k}"${ON[k] ? ' checked' : ''}><i style="display:inline-block;width:10px;height:10px;border:1px solid ${COLORS[k]};background:${COLORS[k]}55"></i>${l}</label>`).join('')}
      <span class="v3d-who">Sprites and boxes: <a href="${man.source.url}" target="_blank" rel="noopener">${man.source.name}</a></span></div>`;
  const $ = s => el.querySelector(s);
  const canvas = $('canvas'), stage = $('.v3d-stage'), ctx = canvas.getContext('2d');
  const FPS = man.fps || 60;
  let disposed = false, raf = 0, mv = null, img = null, opts = {}, N = 1, f = 1, token = 0;
  let playing = !matchMedia('(prefers-reduced-motion: reduce)').matches, speed = 1, acc = 0, last = performance.now();
  const on = () => Object.fromEntries([...el.querySelectorAll('.v3d-opts input')].map(i => [i.dataset.k, i.checked]));

  const resize = () => { const r = devicePixelRatio || 1; canvas.width = Math.round(stage.clientWidth * r); canvas.height = Math.round(stage.clientHeight * r); draw() };
  const ro = new ResizeObserver(resize); ro.observe(stage);

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!mv || !img) return;
    // fill the stage; a whole-pixel scale once it is big enough that the lost space doesn't matter (pixel art)
    const pad = 12 * (devicePixelRatio || 1), sw = (canvas.width - 2 * pad) / mv.w, sh = (canvas.height - 2 * pad - 30 * (devicePixelRatio || 1)) / mv.h;
    const fit = Math.min(sw, sh), s = fit >= 4 && !man.smooth ? Math.floor(fit) : fit;
    const ox = Math.round((canvas.width - mv.w * s) / 2), oy = Math.round(canvas.height - pad - mv.h * s);
    const i = f - 1, cx = (i % mv.cols) * mv.w, cy = Math.floor(i / mv.cols) * mv.h;
    ctx.imageSmoothingEnabled = !!man.smooth;
    ctx.drawImage(img, cx, cy, mv.w, mv.h, ox, oy, mv.w * s, mv.h * s);
    const show = on();
    ctx.lineWidth = Math.max(1, Math.round(s / 2));
    for (const [k, x1, y1, x2, y2] of mv.boxes[i] || []) {
      if (!show[k]) continue;
      if (Array.isArray(x1)) {   // polygon: [kind, [x, y, x, y, ...]] in cell pixels
        ctx.fillStyle = COLORS[k] + '40'; ctx.strokeStyle = COLORS[k];
        ctx.beginPath();
        for (let j = 0; j < x1.length; j += 2) ctx[j ? 'lineTo' : 'moveTo'](ox + x1[j] * s, oy + x1[j + 1] * s);
        ctx.closePath(); ctx.fill(); ctx.stroke();
        continue;
      }
      const x = Math.round(ox + x1 * s), y = Math.round(oy + y1 * s), w = Math.round((x2 - x1 + 1) * s), h = Math.round((y2 - y1 + 1) * s);
      ctx.fillStyle = COLORS[k] + '40'; ctx.strokeStyle = COLORS[k];
      ctx.fillRect(x, y, w, h); ctx.strokeRect(x + .5, y + .5, w - 1, h - 1);
    }
  }
  function go(frame) {
    if (!mv) return;
    f = ((frame - 1 + N) % N) + 1;
    $('.v3d-f').textContent = f;
    $('.v3d-state').textContent = opts.state ? opts.state(f) : '';
    $('.v3d-scrub input').value = f;
    el.style.setProperty('--v3d-at', ((f - 1) / Math.max(N - 1, 1) * 100) + '%');
    draw();
  }
  const setPlaying = p => { playing = p; $('.v3d-play').textContent = p ? '❚❚' : '▶'; $('.v3d-play').setAttribute('aria-label', p ? 'Pause' : 'Play') };
  $('.v3d-play').onclick = () => setPlaying(!playing);
  $('.v3d-prev').onclick = () => { setPlaying(false); go(f - 1) };
  $('.v3d-next').onclick = () => { setPlaying(false); go(f + 1) };
  $('.v3d-scrub input').oninput = e => { setPlaying(false); go(+e.target.value) };
  $('.v3d-speed').onchange = e => { speed = +e.target.value };
  el.querySelectorAll('.v3d-opts input').forEach(i => i.onchange = draw);
  const onKey = e => {
    if (e.target.closest('input,select,textarea') && e.target.type !== 'range') return;
    if (e.key === ',') { setPlaying(false); go(f - 1) }
    else if (e.key === '.') { setPlaying(false); go(f + 1) }
  };
  document.addEventListener('keydown', onKey);
  setPlaying(playing);
  resize();

  const loadSheet = (m, c) => { const u = base + c.moves[m.id].sheet; return once(u, () => image(u)) };
  async function show(m, o = {}) {
    const my = ++token, c = await classData(base, m.class), x = c && c.moves[m.id];
    if (!x || my !== token) return false;
    $('.v3d-msg').hidden = false; $('.v3d-msg').textContent = 'Loading frames…';
    const i = await loadSheet(m, c);
    if (my !== token || disposed) return false;
    $('.v3d-msg').hidden = true;
    mv = x; img = i; opts = o; N = x.frames;
    $('.v3d-strip').innerHTML = o.strip || '';
    $('.v3d-scrub input').max = N;
    acc = 0; go(1);
    return true;
  }
  const tick = now => {
    if (disposed) return;
    raf = requestAnimationFrame(tick);
    const dt = Math.min(now - last, 100); last = now;
    if (playing && mv) { acc += dt * speed * FPS / 1000; if (acc >= 1) { const n = Math.floor(acc); acc -= n; go(f + n) } }
  };
  raf = requestAnimationFrame(tick);
  return {
    show,
    async prefetch(m) { const c = await classData(base, m.class).catch(() => null); if (c && c.moves[m.id]) loadSheet(m, c).catch(() => {}) },
    dispose() { disposed = true; cancelAnimationFrame(raf); ro.disconnect(); document.removeEventListener('keydown', onKey) },
  };
}

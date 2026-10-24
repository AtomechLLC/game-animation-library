// Hitbox clip preview for games without 3D models (games.json "clips"): plays a move's own capture, one image frame
// per game frame, with the same controls as viewer3d.js. Moves list their clips as {file, frames, label, source};
// files are animated WebPs under the game's clips folder. Frames are decoded once with ImageDecoder so the clip can
// be stepped and scrubbed; browsers without it get the WebP playing on its own.
import {speedHtml, bindSpeed} from './speed.js?v=1';

const FPS = 60;

export function createViewer(el, base) {
  el.innerHTML = `<div class="v3d-stage clip-stage"><canvas></canvas><img alt="" hidden><div class="v3d-msg">Loading clip…</div>
    <div class="v3d-hud"><b class="v3d-f">1</b><span class="v3d-state"></span></div></div>
    <div class="v3d-bar">
      <button class="v3d-play" aria-label="Pause">❚❚</button>
      <button class="v3d-prev" aria-label="Back one frame" title="Back one frame (,)">−1 f</button>
      <button class="v3d-next" aria-label="Forward one frame" title="Forward one frame (.)">+1 f</button>
      <div class="v3d-scrub"><div class="v3d-strip"></div><input type="range" min="1" max="1" step="1" value="1" aria-label="Frame"></div>
      ${speedHtml(0.25)}
    </div>
    <div class="v3d-opts"><span class="clip-alts" role="group" aria-label="Clip"></span><a class="v3d-who" target="_blank" rel="noopener"></a></div>`;
  const $ = s => el.querySelector(s);
  const canvas = $('canvas'), ctx = canvas.getContext('2d'), img = $('img'), msg = $('.v3d-msg');
  const cache = new Map(), warm = new Set();   // file -> Promise<ImageBitmap[]>; files fetched ahead
  let frames = [], N = 1, f = 1, m = null, clip = null, opts = {}, token = 0, disposed = false;
  let playing = !matchMedia('(prefers-reduced-motion: reduce)').matches, speed = 0.25, acc = 0, last = performance.now(), raf = 0;

  async function decode(file) {
    const r = await fetch(base + file);
    if (!r.ok) throw new Error(`${file}: ${r.status}`);
    const dec = new ImageDecoder({data: await r.arrayBuffer(), type: 'image/webp'});
    await dec.tracks.ready;
    const n = dec.tracks.selectedTrack.frameCount, out = [];
    for (let i = 0; i < n; i++) {
      const {image} = await dec.decode({frameIndex: i});
      out.push(await createImageBitmap(image)); image.close();
    }
    dec.close();
    return out;
  }
  // decoded frames are big (a 440x280 frame is ~0.5 MB), so keep only the last few clips
  const load = file => {
    if (cache.has(file)) { const p = cache.get(file); cache.delete(file); cache.set(file, p); return p }
    cache.set(file, decode(file).catch(e => { cache.delete(file); throw e }));
    for (const [k, p] of cache) {
      if (cache.size <= 6) break;
      if (k === clip?.file) continue;
      cache.delete(k); p.then(fr => fr.forEach(b => b.close())).catch(() => {});
    }
    return cache.get(file);
  };

  function draw() {
    const b = frames[f - 1];
    if (!b) return;
    if (canvas.width !== b.width || canvas.height !== b.height) { canvas.width = b.width; canvas.height = b.height }
    ctx.drawImage(b, 0, 0);
  }
  function go(frame) {
    f = ((frame - 1 + N) % N) + 1;
    draw();
    $('.v3d-f').textContent = f;
    $('.v3d-state').textContent = opts.state ? opts.state(f) : '';
    $('.v3d-scrub input').value = f;
    el.style.setProperty('--v3d-at', ((f - 1) / Math.max(N - 1, 1) * 100) + '%');
  }
  const setPlaying = p => { playing = p; $('.v3d-play').textContent = p ? '❚❚' : '▶'; $('.v3d-play').setAttribute('aria-label', p ? 'Pause' : 'Play') };
  $('.v3d-play').onclick = () => setPlaying(!playing);
  $('.v3d-prev').onclick = () => { setPlaying(false); go(f - 1) };
  $('.v3d-next').onclick = () => { setPlaying(false); go(f + 1) };
  $('.v3d-scrub input').oninput = e => { setPlaying(false); go(+e.target.value) };
  speed = bindSpeed($('.v3d-speed'), speed, v => { speed = v });
  const onKey = e => {
    if (e.target.closest('input,select,textarea') && e.target.type !== 'range') return;
    if (e.key === ',') { setPlaying(false); go(f - 1) }
    else if (e.key === '.') { setPlaying(false); go(f + 1) }
  };
  document.addEventListener('keydown', onKey);
  setPlaying(playing);

  async function pick(i) {
    const t = ++token;
    clip = m.clips[i];
    el.querySelectorAll('.clip-alts button').forEach((b, k) => b.setAttribute('aria-pressed', k === i));
    const who = $('.v3d-who');
    who.href = clip.source; who.textContent = 'Hitbox clip: Ultimate Frame Data ↗';
    N = clip.frames; $('.v3d-scrub input').max = N; $('.v3d-strip').innerHTML = opts.strip ? opts.strip(N) : '';
    if (!('ImageDecoder' in window)) {
      // no frame stepping: let the image play by itself
      canvas.hidden = true; img.hidden = false; img.src = base + clip.file; msg.hidden = true;
      el.querySelectorAll('.v3d-bar button,.v3d-bar select,.v3d-scrub input').forEach(x => x.disabled = true);
      $('.v3d-state').textContent = 'Frame stepping needs a browser with ImageDecoder (Chrome, Edge, Firefox)';
      return;
    }
    msg.hidden = false; msg.textContent = 'Loading clip…';
    try {
      const fr = await load(clip.file);
      if (t !== token || disposed) return;
      frames = fr; N = fr.length; $('.v3d-scrub input').max = N; msg.hidden = true; acc = 0; go(1);
    } catch (e) { if (t === token) msg.textContent = `Could not load the clip (${e.message}).` }
  }

  const tick = now => {
    if (disposed) return;
    raf = requestAnimationFrame(tick);
    const dt = Math.min(now - last, 100); last = now;
    if (playing && frames.length) { acc += dt * speed * FPS / 1000; if (acc >= 1) { const n = Math.floor(acc); acc -= n; go(f + n) } }
  };
  raf = requestAnimationFrame(tick);

  return {
    // opts.strip(frames) is the frame strip html under the scrubber, opts.state(frame) the label by the frame number
    show(move, o = {}) {
      m = move; opts = o; frames = [];
      const alts = $('.clip-alts');
      alts.innerHTML = m.clips.length > 1 ? m.clips.map((c, i) => `<button class="chip" data-clip="${i}">${c.label.replace(/[&<>"']/g, ch => '&#' + ch.charCodeAt(0) + ';')}</button>`).join('') : '';
      alts.querySelectorAll('button').forEach(b => b.onclick = e => { e.stopPropagation(); pick(+b.dataset.clip) });
      return pick(0);
    },
    // warm the HTTP cache only: decoding every hovered row would push the clips on show out of the frame cache
    prefetch(move) { const c = move.clips?.[0]; if (c && !warm.has(c.file)) { warm.add(c.file); fetch(base + c.file).catch(() => {}) } },
    dispose() {
      disposed = true; cancelAnimationFrame(raf); document.removeEventListener('keydown', onKey);
      cache.forEach(p => p.then(fr => fr.forEach(b => b.close())).catch(() => {}));
    },
  };
}

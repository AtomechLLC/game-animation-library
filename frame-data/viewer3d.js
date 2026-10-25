// 3D preview for Move Explorer: plays a move on the game's own character, armor and weapon models and draws its
// hitboxes on the frames they are out. Everything it loads is written by tools/frame_data/export_er_models.py or
// the other export_*_models.py (format in frame-data/README.md, "3D preview"). Frames here are the tab's frames: 1-based, at
// the game's frame rate (models.json fps, 30 for Elden Ring).
import {speedHtml, bindSpeed} from './speed.js?v=1';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {createBlenderNavigation} from './navigation3d.js?v=10';
import {createRenderStats} from './renderstats.js?v=1';

const loader = new GLTFLoader();
const cache = new Map();
const once = (key, fn) => { if (!cache.has(key)) cache.set(key, fn().catch(e => { cache.delete(key); throw e })); return cache.get(key) };
const json = url => fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json() });
const glb = url => new Promise((ok, fail) => loader.load(url, ok, undefined, fail));
const bin = url => fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.arrayBuffer() });

export const manifest = base => once(base + 'models.json', () => json(base + 'models.json'));
// A class's moves (frames, preview weapon, hits) and hitbox shapes per behavior variation
export const classData = async (base, cls) => { const m = await manifest(base), c = m.classes[cls]; return c ? once(base + c.file, () => json(base + c.file)) : null };

// anim/<id>.bin: one pose per tab frame (layout in export_er_models.py, "baked animation"). Each bone gets a
// Float32Array of quaternions and one of translations, either one per frame or a single value for the whole move.
// The header's spare byte is a step (No Rest for the Wicked: 2): per-frame tracks then hold a pose every step frames.
function decodeAnim(buf, names) {
  const dv = new DataView(buf), B = dv.getUint16(4, true), N = dv.getUint16(6, true), hasRoot = dv.getUint8(8);
  const step = dv.getUint8(9) || 1, M = Math.ceil(N / step);
  let o = 10;
  const ids = [], flags = [];
  for (let k = 0; k < B; k++, o += 2) ids.push(dv.getUint16(o, true));
  for (let k = 0; k < B; k++, o++) flags.push(dv.getUint8(o));
  const S = Math.SQRT1_2, bones = [];
  for (let k = 0; k < B; k++) {
    const nr = flags[k] & 1 ? M : 1, np = flags[k] & 2 ? M : 1, rot = new Float32Array(nr * 4), pos = new Float32Array(np * 3);
    for (let i = 0; i < nr; i++, o += 4) {
      // smallest three: the top 2 bits name the dropped (largest, positive) component, then three 10-bit values
      const v = dv.getUint32(o, true), big = v >>> 30;
      let j = 0, ss = 0;
      for (let c = 0; c < 4; c++) { if (c === big) continue; const x = ((v >>> (20 - 10 * j++)) & 1023) / 1023 * 2 * S - S; rot[i * 4 + c] = x; ss += x * x }
      rot[i * 4 + big] = Math.sqrt(Math.max(0, 1 - ss));
    }
    for (let i = 0; i < np * 3; i++, o += 2) pos[i] = dv.getInt16(o, true) / 1000;
    bones.push({name: names[ids[k]], rot, pos, nr, np});
  }
  let root = null;
  if (hasRoot) { root = new Float32Array(N * 3); for (let i = 0; i < N * 3; i++, o += 4) root[i] = dv.getFloat32(o, true) }
  return {frames: N, step, bones, root};
}

// Numpad 1 and 3: the camera azimuths (navigation3d.js) that face the character's front and right side
const VIEWS = {front: Math.PI, right: Math.PI / 2};

// The Help panel's shortcut list (ported from the centerpiece viewer's HelpPanel); the first section follows the input mode
const kbd = (...keys) => keys.map(k => `<kbd>${k}</kbd>`).join('<span aria-hidden="true">/</span>');
const row = (keys, action) => `<li><span>${keys}</span><b>${action}</b></li>`;
const helpHTML = mode => `<p class="v3d-help-title" id="v3d-help-title">Help</p>
  <p class="v3d-help-note">Click the 3D view first so keys go to it (outlined). Close Help: ${kbd('/', '?')}</p>
  <p class="v3d-help-title">${mode === 'trackpad' ? 'Trackpad' : 'Mouse'}</p>
  <ul>${mode === 'trackpad'
    ? row('Two-finger drag', 'Orbit') + row('Shift + two-finger drag', 'Pan') + row('Pinch / Ctrl + scroll', 'Zoom') + row('Click and drag', 'Orbit') + row('Right drag / Shift + click and drag', 'Pan')
    : row('Left or middle drag', 'Orbit') + row('Right drag / Shift + drag', 'Pan') + row('Scroll wheel', 'Zoom') + row('Ctrl + scroll', 'Zoom, faster')}</ul>
  <p class="v3d-help-title">View</p>
  <ul>${row(kbd('F', 'Home', 'Numpad .'), 'Fit to view') + row(kbd('D', 'Numpad 0'), 'Default camera') + row(kbd('Z'), 'Floor grid')
    + row(kbd('B'), 'Bounds box (current pose)') + row(kbd('Tab', 'Shift + Tab'), 'Mouse / Trackpad') + row(kbd('`'), 'Render stats')
    + row(kbd('/', '?'), 'Help')}</ul>
  <p class="v3d-help-title">Playback</p>
  <ul>${row(kbd('Space'), 'Play / pause') + row(kbd(',', '.', '←', '→'), 'Previous / next frame') + row(kbd('Ctrl + ←', 'Ctrl + →'), 'Back / forward 1 second')
    + row(kbd('Shift + ←', 'Shift + →'), 'First / last frame')}</ul>
  <p class="v3d-help-title">Numpad</p>
  <ul>${row('2 / 4 / 6 / 8', 'Orbit') + row('1 / 3 / 7', 'Front / Right / Top') + row('Ctrl + 7', 'Bottom') + row('9', 'Opposite view') + row('+ / −', 'Zoom in / out')}</ul>`;

const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || '#c2412d';

// A persistent preview in `el`: the models load once, then show(move) swaps the animation, weapon and hitboxes in
// place. Moves are frame-data/1 moves; opts.strip is the frame strip html under the scrubber, opts.state(frame) the
// label next to the frame number.
export async function createViewer(el, base) {
  const man = await manifest(base);
  el.innerHTML = `<div class="v3d-stage" tabindex="0" aria-label="3D view. Drag with the left or middle button to orbit, add Shift or use the right button to pan, wheel to zoom or orbit. Numpad 1, 3 and 7 for front, right and top. F fits the move to the view, D restores the default camera, Z shows or hides the floor grid, B shows or hides the bounds box, Tab switches between mouse and trackpad, left and right arrows step a frame, slash opens Help."><canvas></canvas><div class="v3d-msg">Loading models…</div>
    <div class="v3d-corner"><fieldset class="v3d-mode" aria-label="Viewport input device"><button type="button" data-mode="mouse" aria-label="Mouse" title="Mouse (Tab switches)"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6.5" y="3" width="11" height="18" rx="5.5"/><path d="M12 7v3"/></svg></button><button type="button" data-mode="trackpad" aria-label="Trackpad" title="Trackpad (Tab switches)"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 15h18M12 15v4"/></svg></button></fieldset></div>
    <div class="v3d-side"><div class="v3d-tools">
      <button type="button" class="v3d-help-toggle" aria-pressed="false" aria-label="Toggle Help panel (shortcut / or ?)">? ${kbd('/')}</button></div>
      <section class="v3d-help" aria-labelledby="v3d-help-title" hidden></section></div>
    <div class="v3d-hud"><b class="v3d-f">1</b><span class="v3d-state"></span></div></div>
    <div class="v3d-bar">
      <button class="v3d-play" aria-label="Pause">❚❚</button>
      <button class="v3d-prev" aria-label="Back one frame" title="Back one frame (,)">−1 f</button>
      <button class="v3d-next" aria-label="Forward one frame" title="Forward one frame (.)">+1 f</button>
      <div class="v3d-scrub"><div class="v3d-strip"></div><input type="range" min="1" max="1" step="1" value="1" aria-label="Frame"></div>
      ${speedHtml(0.5)}
    </div>
    <p class="v3d-keys"><span><kbd>Space</kbd> Play / pause</span><span><kbd>,</kbd> <kbd>.</kbd> or <kbd>←</kbd> <kbd>→</kbd> Previous / next frame</span><span><kbd>Ctrl</kbd> + <kbd>←</kbd> <kbd>→</kbd> Back / forward 1 second</span><span><kbd>Shift</kbd> + <kbd>←</kbd> <kbd>→</kbd> First / last frame</span></p>
    <div class="v3d-opts"><label><input type="checkbox" class="v3d-hb" checked> Hitboxes</label>
      <label><input type="checkbox" class="v3d-ghost"> Show hitboxes on every frame</label>
      <label><input type="checkbox" class="v3d-rm" checked> Root motion</label>
      <span class="v3d-who"></span></div>`;
  const $ = s => el.querySelector(s);
  const canvas = $('canvas'), stage = $('.v3d-stage');
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true});
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.05, 100);
  // the opening angle, a three-quarter view from the character's front right (it faces -Z, its right is +X)
  const DEFAULT_DIR = new THREE.Vector3(2.9, 0.5, -2.3).normalize();
  const fitMove = () => { fit(); go(f) }, defaultCamera = () => { fit(DEFAULT_DIR); go(f) };
  const help = $('.v3d-help'), helpToggle = $('.v3d-help-toggle');
  const toggleHelp = () => { help.hidden = !help.hidden; helpToggle.setAttribute('aria-pressed', !help.hidden) };
  const syncMode = m => { for (const b of el.querySelectorAll('.v3d-mode button')) b.setAttribute('aria-pressed', b.dataset.mode === m); help.innerHTML = helpHTML(m) };
  // The view renders only when its picture changes (a frame, the camera, an overlay, the size) and runs its animation
  // loop only while a move plays on screen, so a paused, folded, hidden or scrolled-away view costs nothing.
  // requestRender marks the picture stale and wakes the loop for one render; it waits for `ready` (the models loaded)
  let disposed = false, raf = 0, dirty = true, onScreen = true, ready = false;
  function requestRender() { dirty = true; if (ready && !raf && !disposed && onScreen) { last = performance.now(); raf = requestAnimationFrame(tick) } }
  const nav = createBlenderNavigation({camera, dom: stage, views: VIEWS, onFit: fitMove, onDefault: defaultCamera, onHelp: toggleHelp, onMode: syncMode, onChange: requestRender});
  syncMode(nav.mode);
  // the overlay buttons hand the keyboard to the stage; presses and wheel turns on the overlays don't navigate
  for (const b of el.querySelectorAll('.v3d-stage button')) b.addEventListener('mousedown', e => { e.preventDefault(); stage.focus({preventScroll: true}) });
  helpToggle.onclick = toggleHelp;
  for (const b of el.querySelectorAll('.v3d-mode button')) b.onclick = () => nav.setMode(b.dataset.mode);
  for (const t of ['pointerdown', 'wheel']) for (const o of [$('.v3d-mode'), help]) o.addEventListener(t, e => e.stopPropagation());
  nav.fitTo(new THREE.Vector3(0, 1, 0), DEFAULT_DIR, 3.7, 2);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x5a5a62, 2.4));
  const sun = new THREE.DirectionalLight(0xffffff, 2.6); sun.position.set(3, 5, -3); scene.add(sun);
  const grid = new THREE.GridHelper(8, 16, 0x888888, 0x555555); grid.material.transparent = true; grid.material.opacity = .35; scene.add(grid);
  // The view is a previewer, so its tools are keys only (listed under ?): D, F, and Z (as in the centerpiece viewer)
  // hides the floor, e.g. for a clean view in class
  const toggleGrid = () => { grid.visible = !grid.visible; requestRender() };
  // B (as in the centerpiece viewer) shows a box around the pose on show: the body, the weapons and
  // the hitboxes out on this frame. Off by default; measured only while it shows
  // drawn in the collider green of engine gizmos (Unity's collider outline), apart from the red hitboxes; the page's
  // --v3d-bounds gives a deeper green on the light theme, read on each measure so a theme switch follows
  const bbox = new THREE.Box3(), bounds = new THREE.Box3Helper(bbox, new THREE.Color(0x91f48b));
  Object.assign(bounds.material, {transparent: true, opacity: .9, depthWrite: false, toneMapped: false});
  bounds.visible = false; scene.add(bounds);
  const toggleBounds = () => { bounds.visible = !bounds.visible; go(f) };
  stage.addEventListener('keydown', e => {
    if (e.shiftKey || e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === 'z') { e.preventDefault(); toggleGrid() }
    else if (k === 'b') { e.preventDefault(); toggleBounds() }
  });

  const resize = () => { const w = stage.clientWidth, h = stage.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); requestRender() };
  const ro = new ResizeObserver(resize); ro.observe(stage); resize();
  // off screen covers scrolled away, folded (Hide) and hidden (no move matches): the loop stops; back on screen it renders
  // the current picture and a playing move carries on
  const io = new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; if (onScreen) requestRender() }); io.observe(stage);

  const FPS = man.fps || 30, sk = man.skeleton;
  const armorG = await glb(base + man.armor.file);
  $('.v3d-msg').hidden = true;
  // Game files are left-handed: mirror X once at the top so everything below stays in game space (models.json
  // "mirror": false for games whose files are already right-handed, Ninja Gaiden Black)
  const mirror = new THREE.Group(); mirror.scale.x = man.mirror === false ? 1 : -1; scene.add(mirror);
  const motion = new THREE.Group(); mirror.add(motion);
  const body = armorG.scene; motion.add(body);
  body.traverse(o => { if (o.isMesh) o.frustumCulled = false });
  const bone = n => body.getObjectByName(n);
  // the weapon in each hand: powerstance moves hold the same weapon in both, bows and off-hand attacks the left only
  const hands = {R: {bone: bone(man.skeleton.weaponBone)}, L: {bone: bone(man.skeleton.leftWeaponBone)}};
  const rest = [];
  body.traverse(o => rest.push([o, o.position.clone(), o.quaternion.clone()]));

  // Hitbox meshes; capsules are a cylinder plus two spheres
  const hitColor = new THREE.Color(css('--f-active'));
  const mat = new THREE.MeshBasicMaterial({color: hitColor, transparent: true, opacity: .32, depthWrite: false});
  const ghostMat = new THREE.MeshBasicMaterial({color: hitColor, transparent: true, opacity: .12, depthWrite: false, wireframe: true});
  const sphereG = new THREE.SphereGeometry(1, 20, 12), cylG = new THREE.CylinderGeometry(1, 1, 1, 20, 1, true);
  const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
  const pelvis = bone(sk.follow || 'Pelvis') || body, follow = new THREE.Vector3();
  // Weapon boxes (No Rest for the Wicked): the weapon's collider box in its hand socket's space
  const boxG = new THREE.BoxGeometry(2, 2, 2), qtmp = [0, 0, 0, 1];

  // The move on show
  let info = null, anim = null, defHand = 'R', tracks = [], shapes = [], boxes = [], opts = {}, N = 1;
  let fitting = false;  // fit() poses every frame; the bounds box waits for the frame it lands on
  let f = 1, playing = !matchMedia('(prefers-reduced-motion: reduce)').matches, speed = 0.5, acc = 0, last = performance.now(), token = 0;
  // ` (backquote) shows the render stats overlay (renderstats.js)
  const stats = createRenderStats(stage, renderer, () => ({playing, frame: f, frames: N}));
  stage.addEventListener('keydown', e => { if (e.key === '`' && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); stats.toggle() } });

  function point(id, hand, out) {
    let src = 'any', k = id;
    if (id >= 10000) { const g = Math.floor(id / 1000); k = id % 1000; src = g >= 10 && g < 20 ? 'weapon' : 'none' }
    const h = hands[hand].obj ? hands[hand] : hands[defHand];
    const w = src !== 'none' && h.obj && h.dummies && h.dummies[k];
    if (w) return out.set(w[0], w[1], w[2]).applyMatrix4(h.root.matrixWorld);
    const d = src === 'any' && man.body[k];
    if (d) { const b = bone(d[0]); if (b) return out.set(d[1], d[2], d[3]).applyMatrix4(b.matrixWorld) }
    return null;
  }

  // f is the tab's 1-based frame; the animation holds one pose per frame
  function pose(frame) {
    const i = Math.min(Math.max(frame - 1, 0), anim.frames - 1);
    const u = i / anim.step, k0 = Math.floor(u), t = u - k0;
    anim.bones.forEach((a, k) => {
      const b = tracks[k]; if (!b) return;
      if (a.nr > 1) {
        const k1 = Math.min(k0 + 1, a.nr - 1);
        if (t) { THREE.Quaternion.slerpFlat(qtmp, 0, a.rot, k0 * 4, a.rot, k1 * 4, t); b.quaternion.fromArray(qtmp) }
        else b.quaternion.fromArray(a.rot, k0 * 4);
      } else b.quaternion.fromArray(a.rot, 0);
      if (a.np > 1) {
        const k1 = Math.min(k0 + 1, a.np - 1);
        b.position.fromArray(a.pos, k0 * 3);
        if (t) b.position.lerp(v2.fromArray(a.pos, k1 * 3), t);
      } else b.position.fromArray(a.pos, 0);
    });
    if (anim.root && $('.v3d-rm').checked) motion.position.fromArray(anim.root, i * 3);
    else motion.position.set(0, 0, 0);
    scene.updateMatrixWorld(true);
    // keep the character in view: the camera rides along with root motion, the grid shows the distance covered
    pelvis.getWorldPosition(v1); v1.y = 0;
    nav.shift(v2.subVectors(v1, follow)); follow.copy(v1);
    const showAll = $('.v3d-ghost').checked, on = $('.v3d-hb').checked;
    for (const x of boxes) {
      const active = frame >= x.h.start && frame <= x.h.end;
      x.m.visible = on && (active || showAll);
      x.m.material = active ? mat : ghostMat;
    }
    for (const x of shapes) {
      const active = frame >= x.h.start && frame <= x.h.end;
      x.g.visible = on && (active || showAll);
      if (!x.g.visible) continue;
      x.a.material = x.b.material = x.c.material = active ? mat : ghostMat;
      const pa = point(x.s.a, x.hand, v1), pb = x.s.b != null ? point(x.s.b, x.hand, v2) : null;
      if (!pa) { x.g.visible = false; continue }
      const r = x.s.r;
      x.a.position.copy(pa); x.a.scale.setScalar(r);
      x.b.visible = x.c.visible = !!pb;
      if (pb) {
        x.b.position.copy(pb); x.b.scale.setScalar(r);
        x.c.position.copy(pa).add(pb).multiplyScalar(.5); x.c.scale.set(r, pa.distanceTo(pb), r);
        x.c.quaternion.setFromUnitVectors(up, v2.clone().sub(pa).normalize());
      }
    }
    // skill-buffed hits fire projectiles whose shapes the export doesn't read yet
    const missing = info.hits.some(h => frame >= h.start && frame <= h.end && !shapes.some(x => x.h === h) && !boxes.some(x => x.h === h));
    if (bounds.visible && !fitting) measure();
    $('.v3d-f').textContent = frame;
    $('.v3d-state').textContent = (opts.state ? opts.state(frame) : '') + (missing ? ' · hitbox shape not in data' : '');
    $('.v3d-scrub input').value = frame;
    el.style.setProperty('--v3d-at', ((frame - 1) / Math.max(N - 1, 1) * 100) + '%');
  }
  // every posed vertex (skinned, in world space) of the visible meshes: the character, its weapons and the hitboxes
  function measure() {
    bbox.makeEmpty();
    bounds.material.color.set(getComputedStyle(document.documentElement).getPropertyValue('--v3d-bounds').trim() || 0x91f48b);
    const add = o => { if (!o.isMesh) return; const p = o.geometry.attributes.position; for (let i = 0; i < p.count; i++) bbox.expandByPoint(o.getVertexPosition(i, v1).applyMatrix4(o.matrixWorld)) };
    motion.traverseVisible(add);
    for (const x of shapes) if (x.g.visible) x.g.traverseVisible(add);
  }
  const setPlaying = p => { playing = p; $('.v3d-play').textContent = p ? '❚❚' : '▶'; $('.v3d-play').setAttribute('aria-label', p ? 'Pause' : 'Play'); if (p) requestRender() };
  const go = frame => { if (!anim) return; f = ((frame - 1 + N) % N) + 1; pose(f); requestRender() };
  $('.v3d-play').onclick = () => setPlaying(!playing);
  $('.v3d-prev').onclick = () => { setPlaying(false); go(f - 1) };
  $('.v3d-next').onclick = () => { setPlaying(false); go(f + 1) };
  $('.v3d-scrub input').oninput = e => { setPlaying(false); go(+e.target.value) };
  speed = bindSpeed($('.v3d-speed'), speed, v => { speed = v });
  el.querySelectorAll('.v3d-opts input').forEach(i => i.onchange = () => go(f));
  const onKey = e => {
    if (e.target.closest('input,select,textarea') && e.target.type !== 'range') return;
    if (e.code === 'NumpadDecimal') return;  // Numpad . fits the move to the view (navigation3d.js), as in Blender
    if (e.code === 'Space' && !e.repeat && !e.target.closest('button')) { e.preventDefault(); setPlaying(!playing) }
    else if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && e.ctrlKey !== e.shiftKey && !e.altKey && !e.metaKey) {
      // Ctrl jumps one second of the animation (clamped at the ends), Shift goes to the first or last frame
      e.preventDefault(); setPlaying(false);
      const d = e.key === 'ArrowLeft' ? -1 : 1;
      go(e.shiftKey ? (d < 0 ? 1 : N) : Math.min(N, Math.max(1, f + d * FPS)));
    }
    // with focus in the viewer (the 3D stage or a control), plain arrows step a frame, like , and .; elsewhere on the page
    // they step the weapon type
    else if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && !e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey
      && el.contains(e.target) && e.target.type !== 'range') { e.preventDefault(); setPlaying(false); go(f + (e.key === 'ArrowLeft' ? -1 : 1)) }
    else if (e.key === ',') { setPlaying(false); go(f - 1) }
    else if (e.key === '.') { setPlaying(false); go(f + 1) }
  };
  document.addEventListener('keydown', onKey);
  setPlaying(playing);

  // Fit the whole move to the view (every weapon point and the body over all frames, relative to the pelvis the camera
  // follows), keeping the angle the viewer has orbited to unless `dir` (target to camera) is given
  function fit(dir = camera.position.clone().sub(nav.target).normalize()) {
    if (!anim) return;
    fitting = true;
    const box = new THREE.Box3(), o = new THREE.Vector3(), held = Object.values(hands).filter(h => h.obj);
    for (let k = 1; k <= N; k++) {
      pose(k);
      o.set(follow.x, 0, follow.z);
      for (const h of held) for (const d of [...Object.values(h.dummies || {}), [0, 0.25, 0]]) box.expandByPoint(v1.set(d[0], d[1], d[2]).applyMatrix4((h.root || h.obj).matrixWorld).sub(o));
      for (const n of sk.fit || ['Head', 'L_Toe0', 'R_Toe0', 'L_Hand', 'R_Hand']) { const b = bone(n); if (b) box.expandByPoint(b.getWorldPosition(v1).sub(o)) }
      for (const x of boxes) if (x.m.visible) box.expandByPoint(x.m.getWorldPosition(v1).sub(o));
    }
    box.expandByScalar(Math.max(0, ...shapes.map(x => x.s.r), ...boxes.map(x => Math.max(...x.b.e))));
    // the nearest camera distance along `dir` that keeps every corner of the box inside both fields of view
    const c = box.getCenter(new THREE.Vector3()), tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)), tanH = tanV * camera.aspect;
    const right = new THREE.Vector3().crossVectors(up, dir).normalize(), upv = new THREE.Vector3().crossVectors(dir, right);
    let dist = 0;
    for (let i = 0; i < 8; i++) {
      v1.set(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z).sub(c);
      dist = Math.max(dist, Math.max(Math.abs(v1.dot(right)) / tanH, Math.abs(v1.dot(upv)) / tanV) + v1.dot(dir));
    }
    dist *= 1.05;
    follow.set(0, 0, 0);
    const size = Math.max(box.getSize(v1).length(), 0.5);
    nav.fitTo(c, dir, dist, size);
    camera.far = Math.max(dist * 10, size * 25); camera.updateProjectionMatrix();
    fitting = false;
  }

  const loadWeapon = name => { const f = base + man.weapons[name].file; return once(f, () => glb(f)) };
  const loadAnim = id => once(base + 'anim/' + id, () => bin(base + 'anim/' + id + '.bin').then(b => decodeAnim(b, sk.bones)));
  // the weapon on show: the one picked (the page only lists a picked weapon's own moves), else the class's preview
  // weapon for this move
  const weaponFor = (mv, pick) => pick && man.weapons[pick] ? pick : mv.weapon;
  const handsFor = m => {
    const def = m.grip === 'Offhand' || man.classes[m.class].hand === 'L' ? 'L' : 'R';
    return [def, m.grip === 'Paired' ? ['R', 'L'] : [def]];
  };

  function hold(hand, name, g) {
    const h = hands[hand];
    if (h.name === name) return;
    if (h.obj) h.bone.remove(h.obj);
    for (const w of h.worn || []) w.parent?.remove(w);
    h.name = name; h.obj = null; h.root = null; h.dummies = null; h.worn = [];
    if (!name) return;
    // Worn weapons (Devil May Cry 3's Beowulf): pieces whose extras name the body bone they sit on
    const pieces = []; g.scene.traverse(x => { if (x.userData.bone && bone(x.userData.bone)) pieces.push(x) });
    if (pieces.length) {
      if (hand !== defHand) return;
      for (const x of pieces) { const c = x.clone(); c.position.set(0, 0, 0); bone(x.userData.bone).add(c); h.worn.push(c) }
      return;
    }
    // Weapon models point down -Y. R_Weapon's +Y points out of the fist (the models' own Ctrl_Sword node carries the
    // same half turn about Z); L_Weapon mirrors R_Weapon, so the left hand takes the model as it is
    // Dual weapons (No Rest for the Wicked) carry one root per hand, named R and L
    const part = g.scene.getObjectByName(hand) && g.scene.getObjectByName('L') ? g.scene.getObjectByName(hand) : g.scene;
    h.obj = part.clone(); if (hand === 'R' && man.weaponTurn !== false) h.obj.rotation.z = Math.PI;
    if (part !== g.scene) h.obj.position.set(0, 0, 0);
    h.obj.traverse(x => { if (x.userData.dummies) { h.root = x; h.dummies = x.userData.dummies } });
    h.bone.add(h.obj);
  }

  async function show(m, o = {}) {
    const my = ++token, c = await classData(base, m.class), mv = c && c.moves[m.id];
    if (!mv || my !== token) return false;
    const name = weaponFor(mv, o.weapon), [def, held] = handsFor(m);
    const [weaponG, a] = await Promise.all([loadWeapon(name), loadAnim(mv.anim || m.id)]);
    if (my !== token || disposed) return false;
    info = mv; anim = a; opts = o; N = a.frames; defHand = def;
    for (const [obj, p, q] of rest) { obj.position.copy(p); obj.quaternion.copy(q) }
    const dual = !!weaponG.scene.getObjectByName('L');
    for (const hand of ['R', 'L']) hold(hand, held.includes(hand) || dual ? name : null, weaponG);
    tracks = anim.bones.map(b => bone(b.name));
    for (const x of shapes) scene.remove(x.g);
    for (const x of boxes) x.m.parent?.remove(x.m);
    shapes = []; boxes = [];
    const own = (c.boxes || {})[name] || {};
    for (const h of info.hits) if (own[h.collider]) {
      const b = own[h.collider], m = new THREE.Mesh(boxG, mat), sock = hands[b.hand || def].bone;
      m.position.set(b.o[0], b.o[1], b.o[2]); m.quaternion.set(b.r[0], b.r[1], b.r[2], b.r[3]);
      m.scale.set(b.e[0], b.e[1], b.e[2]); sock.add(m); boxes.push({h, b, m});
    }
    const atk = (c.attacks || {})[man.weapons[name].variation] || {};
    for (const h of info.hits) for (const s of atk[h.judge] || []) {
      const g = new THREE.Group(), sa = new THREE.Mesh(sphereG, mat), sb = new THREE.Mesh(sphereG, mat), cy = new THREE.Mesh(cylG, mat);
      g.add(sa, sb, cy); scene.add(g); shapes.push({h, s, g, hand: h.hand || def, a: sa, b: sb, c: cy});
    }
    $('.v3d-strip').innerHTML = o.strip || '';
    $('.v3d-scrub input').max = N;
    $('.v3d-who').textContent = `${man.armor.name} · ${name}`;
    fit(); acc = 0; go(1);
    return true;
  }

  // The view a link can carry (frame, speed, overlay toggles), as changes from this viewer's defaults so links stay short
  const sel = $('.v3d-speed'), defSpeed = ([...sel.options].find(o => o.defaultSelected) || sel.options[0]).value;
  const toggles = () => [...el.querySelectorAll('.v3d-opts input[type=checkbox]')], tkey = i => i.dataset.k || i.className.replace('v3d-', '');
  const view = () => ({frame: f, speed: sel.value === defSpeed ? null : sel.value,
    show: toggles().filter(i => i.checked && !i.defaultChecked).map(tkey), hide: toggles().filter(i => !i.checked && i.defaultChecked).map(tkey)});
  function setView(v) {
    setPlaying(false);
    if (v.speed && [...sel.options].some(o => o.value === v.speed)) { sel.value = v.speed; speed = +v.speed }
    for (const i of toggles()) { const k = tkey(i); if (v.show?.includes(k)) i.checked = true; if (v.hide?.includes(k)) i.checked = false }
    go(Math.min(Math.max(1, v.frame || 1), N));
  }

  // raf stays set while a tick runs, so requestRender calls from inside it (go, the camera following root motion) only
  // mark the picture stale
  const tick = now => {
    if (disposed) return;
    stats.tick();
    const dt = Math.max(0, Math.min(now - last, 100)); last = now;
    if (playing && anim) { acc += dt * speed * FPS / 1000; if (acc >= 1) { const n = Math.floor(acc); acc -= n; go(f + n) } }
    if (dirty) { dirty = false; stats.render(() => renderer.render(scene, camera)) }
    raf = playing && anim && onScreen ? requestAnimationFrame(tick) : 0;
  };
  ready = true; requestRender();
  return {
    show, view, setView,
    // for code that changes the scene from outside (tools/er_gifs/render.html): draw it on the next animation frame
    requestRender,
    debug: {THREE, scene, camera, nav, body, motion, bone, go: f => go(f), boxes: () => boxes, hands, stats: stats.snapshot},
    // warm the cache for the row under the pointer, so the swap on click is instant
    async prefetch(m, pick) {
      const c = await classData(base, m.class).catch(() => null), mv = c && c.moves[m.id];
      if (mv) { loadAnim(mv.anim || m.id).catch(() => {}); loadWeapon(weaponFor(mv, pick)).catch(() => {}) }
    },
    dispose() {
      disposed = true; cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); document.removeEventListener('keydown', onKey); stats.dispose();
      nav.dispose(); renderer.dispose(); sphereG.dispose(); cylG.dispose(); boxG.dispose(); mat.dispose(); ghostMat.dispose(); bounds.geometry.dispose(); bounds.material.dispose();
    },
  };
}

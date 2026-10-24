// 3D preview for the Frame Data tab: plays a move on the game's own character, armor and weapon models and draws its
// hitboxes on the frames they are out. Everything it loads is written by tools/frame_data/export_er_models.py or
// the other export_*_models.py (format in frame-data/README.md, "3D preview"). Frames here are the tab's frames: 1-based, at
// the game's frame rate (models.json fps, 30 for Elden Ring).
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

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

const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || '#c2412d';

// A persistent preview in `el`: the models load once, then show(move) swaps the animation, weapon and hitboxes in
// place. Moves are frame-data/1 moves; opts.strip is the frame strip html under the scrubber, opts.state(frame) the
// label next to the frame number.
export async function createViewer(el, base) {
  const man = await manifest(base);
  el.innerHTML = `<div class="v3d-stage"><canvas></canvas><div class="v3d-msg">Loading models…</div>
    <div class="v3d-hud"><b class="v3d-f">1</b><span class="v3d-state"></span></div></div>
    <div class="v3d-bar">
      <button class="v3d-play" aria-label="Pause">❚❚</button>
      <button class="v3d-prev" aria-label="Back one frame" title="Back one frame (,)">−1 f</button>
      <button class="v3d-next" aria-label="Forward one frame" title="Forward one frame (.)">+1 f</button>
      <div class="v3d-scrub"><div class="v3d-strip"></div><input type="range" min="1" max="1" step="1" value="1" aria-label="Frame"></div>
      <select class="v3d-speed" aria-label="Playback speed"><option value="1">1×</option><option value="0.5">½×</option><option value="0.25">¼×</option><option value="0.1">0.1×</option></select>
    </div>
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
  camera.position.set(2.9, 1.5, -2.3);
  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 1.0, 0); controls.enableDamping = true; controls.update();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x5a5a62, 2.4));
  const sun = new THREE.DirectionalLight(0xffffff, 2.6); sun.position.set(3, 5, -3); scene.add(sun);
  const grid = new THREE.GridHelper(8, 16, 0x888888, 0x555555); grid.material.transparent = true; grid.material.opacity = .35; scene.add(grid);

  let disposed = false, raf = 0;
  const resize = () => { const w = stage.clientWidth, h = stage.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix() };
  const ro = new ResizeObserver(resize); ro.observe(stage); resize();

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
  let f = 1, playing = !matchMedia('(prefers-reduced-motion: reduce)').matches, speed = 1, acc = 0, last = performance.now(), token = 0;

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
    // keep the character framed: the camera rides along with root motion, the grid shows the distance covered
    pelvis.getWorldPosition(v1); v1.y = 0;
    camera.position.add(v2.subVectors(v1, follow)); controls.target.add(v2); follow.copy(v1);
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
    $('.v3d-f').textContent = frame;
    $('.v3d-state').textContent = (opts.state ? opts.state(frame) : '') + (missing ? ' · hitbox shape not in data' : '');
    $('.v3d-scrub input').value = frame;
    el.style.setProperty('--v3d-at', ((frame - 1) / Math.max(N - 1, 1) * 100) + '%');
  }
  const setPlaying = p => { playing = p; $('.v3d-play').textContent = p ? '❚❚' : '▶'; $('.v3d-play').setAttribute('aria-label', p ? 'Pause' : 'Play') };
  const go = frame => { if (!anim) return; f = ((frame - 1 + N) % N) + 1; pose(f) };
  $('.v3d-play').onclick = () => setPlaying(!playing);
  $('.v3d-prev').onclick = () => { setPlaying(false); go(f - 1) };
  $('.v3d-next').onclick = () => { setPlaying(false); go(f + 1) };
  $('.v3d-scrub input').oninput = e => { setPlaying(false); go(+e.target.value) };
  $('.v3d-speed').onchange = e => { speed = +e.target.value };
  el.querySelectorAll('.v3d-opts input').forEach(i => i.onchange = () => go(f));
  const onKey = e => {
    if (e.target.closest('input,select,textarea') && e.target.type !== 'range') return;
    if (e.key === ',') { setPlaying(false); go(f - 1) }
    else if (e.key === '.') { setPlaying(false); go(f + 1) }
  };
  document.addEventListener('keydown', onKey);
  setPlaying(playing);

  // Frame the whole move (every weapon point and the body over all frames, relative to the pelvis the camera
  // follows), keeping the angle the viewer has orbited to
  function fit() {
    const dir = camera.position.clone().sub(controls.target).normalize();
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
    controls.target.copy(c); camera.position.copy(c).addScaledVector(dir, dist);
    camera.far = dist * 10; camera.updateProjectionMatrix(); controls.update();
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

  const tick = now => {
    if (disposed) return;
    raf = requestAnimationFrame(tick);
    const dt = Math.min(now - last, 100); last = now;
    if (playing && anim) { acc += dt * speed * FPS / 1000; if (acc >= 1) { const n = Math.floor(acc); acc -= n; go(f + n) } }
    controls.update(); renderer.render(scene, camera);
  };
  raf = requestAnimationFrame(tick);
  return {
    show,
    debug: {THREE, scene, camera, controls, body, motion, bone, go: f => go(f), boxes: () => boxes, hands},
    // warm the cache for the row under the pointer, so the swap on click is instant
    async prefetch(m, pick) {
      const c = await classData(base, m.class).catch(() => null), mv = c && c.moves[m.id];
      if (mv) { loadAnim(mv.anim || m.id).catch(() => {}); loadWeapon(weaponFor(mv, pick)).catch(() => {}) }
    },
    dispose() {
      disposed = true; cancelAnimationFrame(raf); ro.disconnect(); document.removeEventListener('keydown', onKey);
      controls.dispose(); renderer.dispose(); sphereG.dispose(); cylG.dispose(); boxG.dispose(); mat.dispose(); ghostMat.dispose();
    },
  };
}

// 3D preview for the Frame Data tab: plays a move on the game's own character, armor and weapon models and draws its
// hitboxes on the frames they are out. Everything it loads is written by tools/frame_data/export_er_models.py
// (format in frame-data/README.md, "3D preview"). Frames here are the tab's frames: 1-based, 30 fps real time.
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

const loader = new GLTFLoader();
const cache = new Map();
const once = (key, fn) => { if (!cache.has(key)) cache.set(key, fn().catch(e => { cache.delete(key); throw e })); return cache.get(key) };
const json = url => fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json() });
const glb = url => new Promise((ok, fail) => loader.load(url, ok, undefined, fail));
const b64 = (s, T) => { const b = atob(s), u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return new T(u.buffer) };

export const manifest = base => once(base + 'models.json', () => json(base + 'models.json'));

function decodeAnim(a) {
  const rot = b64(a.rot, Int16Array), pos = {}, root = a.root ? b64(a.root, Float32Array) : null;
  for (const [k, v] of Object.entries(a.pos)) pos[k] = b64(v, Float32Array);
  return {...a, rot, pos, root};
}

const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || '#c2412d';

// Mounts the preview into `el` for move `m` (a frame-data/1 move) of class `cls`; returns {dispose}.
export async function mount(el, base, m, opts = {}) {
  const man = await manifest(base);
  const info = man.moves[m.class + '|' + m.id];
  if (!info) throw new Error('No 3D data for this move');
  const wname = info.weapon;
  el.innerHTML = `<div class="v3d-stage"><canvas></canvas><div class="v3d-msg">Loading models…</div>
    <div class="v3d-hud"><b class="v3d-f">1</b><span class="v3d-state"></span></div></div>
    <div class="v3d-bar">
      <button class="v3d-play" aria-label="Pause">❚❚</button>
      <button class="v3d-prev" aria-label="Previous frame">◀︎</button>
      <button class="v3d-next" aria-label="Next frame">▶︎</button>
      <div class="v3d-scrub">${opts.strip || ''}<input type="range" min="1" max="${info.frames}" step="1" value="1" aria-label="Frame"></div>
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
  const resize = () => { const w = stage.clientWidth, h = stage.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix() };
  const ro = new ResizeObserver(resize); ro.observe(stage); resize();

  const weapon = man.weapons[wname];
  const [armorG, weaponG, anim] = await Promise.all([
    glb(base + man.armor.file), once(base + weapon.file, () => glb(base + weapon.file)),
    once(base + 'anim/' + m.id, () => json(base + 'anim/' + m.id + '.json').then(decodeAnim))]);
  if (disposed) return {dispose() {}};
  $('.v3d-msg').hidden = true;
  $('.v3d-who').textContent = `${man.armor.name} · ${wname}`;

  // Game files are left-handed: mirror X once at the top so everything below stays in game space
  const mirror = new THREE.Group(); mirror.scale.x = -1; scene.add(mirror);
  const motion = new THREE.Group(); mirror.add(motion);
  const body = armorG.scene; motion.add(body);
  body.traverse(o => { if (o.isMesh) { o.frustumCulled = false } });
  const bone = n => body.getObjectByName(n);
  // Weapon models point down -Y while R_Weapon's +Y points out of the fist; the models' own Ctrl_Sword node carries
  // the same half turn about Z
  const wpn = weaponG.scene.clone(); wpn.rotation.z = Math.PI;
  const hand = bone(man.skeleton.weaponBone); hand.add(wpn);
  const rest = new Map();
  body.traverse(o => rest.set(o.name, {p: o.position.clone(), q: o.quaternion.clone()}));
  const tracks = anim.bones.map(n => bone(n));

  // Hitbox meshes, one per shape; capsules are a cylinder plus two spheres
  const hitColor = new THREE.Color(css('--f-active'));
  const mat = new THREE.MeshBasicMaterial({color: hitColor, transparent: true, opacity: .32, depthWrite: false});
  const ghostMat = new THREE.MeshBasicMaterial({color: hitColor, transparent: true, opacity: .12, depthWrite: false, wireframe: true});
  const sphereG = new THREE.SphereGeometry(1, 20, 12), cylG = new THREE.CylinderGeometry(1, 1, 1, 20, 1, true);
  const shapes = [];
  for (const h of info.hits) for (const s of h.shapes) {
    const g = new THREE.Group();
    const a = new THREE.Mesh(sphereG, mat), b = new THREE.Mesh(sphereG, mat), c = new THREE.Mesh(cylG, mat);
    g.add(a, b, c); scene.add(g); shapes.push({h, s, g, a, b, c});
  }
  const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
  const pelvis = bone('Pelvis') || body, follow = new THREE.Vector3();
  const wdum = id => weapon.dummies[id];
  function point(id, out) {
    let src = 'any', k = id;
    if (id >= 10000) { const g = Math.floor(id / 1000); k = id % 1000; src = g >= 10 && g < 20 ? 'weapon' : 'none' }
    const w = src !== 'none' && wdum(k);
    if (w) return out.set(w[0], w[1], w[2]).applyMatrix4(wpn.matrixWorld);
    const d = src === 'any' && man.body[k];
    if (d) { const b = bone(d[0]); if (b) return out.set(d[1], d[2], d[3]).applyMatrix4(b.matrixWorld) }
    return null;
  }

  // Playback: f is the tab's 1-based frame; the pose at frame f is the animation at time[f-1]
  const N = info.frames;
  let f = 1, playing = !matchMedia('(prefers-reduced-motion: reduce)').matches, speed = 1, acc = 0, last = performance.now();
  const q0 = new THREE.Quaternion(), q1 = new THREE.Quaternion();
  function pose(frame) {
    const t = anim.time[Math.min(Math.max(frame - 1, 0), anim.time.length - 1)] * anim.fps;
    const i0 = Math.min(Math.floor(t), anim.frames - 1), i1 = Math.min(i0 + 1, anim.frames - 1), u = Math.min(Math.max(t - i0, 0), 1);
    const B = anim.bones.length, R = anim.rot;
    tracks.forEach((b, k) => {
      if (!b) return;
      let o = (i0 * B + k) * 4; q0.set(R[o] / 32767, R[o + 1] / 32767, R[o + 2] / 32767, R[o + 3] / 32767);
      o = (i1 * B + k) * 4; q1.set(R[o] / 32767, R[o + 1] / 32767, R[o + 2] / 32767, R[o + 3] / 32767);
      b.quaternion.slerpQuaternions(q0.normalize(), q1.normalize(), u);
      const p = anim.pos[anim.bones[k]];
      if (p) b.position.set(p[i0 * 3] + (p[i1 * 3] - p[i0 * 3]) * u, p[i0 * 3 + 1] + (p[i1 * 3 + 1] - p[i0 * 3 + 1]) * u, p[i0 * 3 + 2] + (p[i1 * 3 + 2] - p[i0 * 3 + 2]) * u);
      else if (anim.rest[anim.bones[k]]) b.position.fromArray(anim.rest[anim.bones[k]]);
    });
    if (anim.root && $('.v3d-rm').checked) {
      const n = anim.root.length / 4, rt = Math.min(t / Math.max(anim.frames - 1, 1) * (n - 1), n - 1), r0 = Math.floor(rt), r1 = Math.min(r0 + 1, n - 1), ru = rt - r0;
      const R4 = anim.root; motion.position.set(...[0, 1, 2].map(j => R4[r0 * 4 + j] + (R4[r1 * 4 + j] - R4[r0 * 4 + j]) * ru));
    } else motion.position.set(0, 0, 0);
    scene.updateMatrixWorld(true);
    // keep the character framed: the camera rides along with root motion, the grid shows the distance covered
    pelvis.getWorldPosition(v1); v1.y = 0;
    camera.position.add(v2.subVectors(v1, follow)); controls.target.add(v2); follow.copy(v1);
    const showAll = $('.v3d-ghost').checked, on = $('.v3d-hb').checked;
    for (const x of shapes) {
      const active = frame >= x.h.start && frame <= x.h.end;
      x.g.visible = on && (active || showAll);
      if (!x.g.visible) continue;
      const m2 = active ? mat : ghostMat; x.a.material = x.b.material = x.c.material = m2;
      const pa = point(x.s.a, v1), pb = x.s.b != null ? point(x.s.b, v2) : null;
      if (!pa) { x.g.visible = false; continue }
      const r = x.s.r;
      x.a.position.copy(pa); x.a.scale.setScalar(r);
      x.b.visible = x.c.visible = !!pb;
      if (pb) {
        x.b.position.copy(pb); x.b.scale.setScalar(r);
        const len = pa.distanceTo(pb);
        x.c.position.copy(pa).add(pb).multiplyScalar(.5); x.c.scale.set(r, len, r);
        x.c.quaternion.setFromUnitVectors(up, v2.clone().sub(pa).normalize());
      }
    }
    // skill-buffed hits fire projectiles whose shapes the export doesn't read yet
    const missing = info.hits.some(h => frame >= h.start && frame <= h.end && !h.shapes.length);
    const st = (opts.state ? opts.state(frame) : '') + (missing ? ' · hitbox shape not in data' : '');
    $('.v3d-f').textContent = frame; $('.v3d-state').textContent = st;
    $('.v3d-scrub input').value = frame;
    el.style.setProperty('--v3d-at', ((frame - 1) / Math.max(N - 1, 1) * 100) + '%');
  }
  const setPlaying = p => { playing = p; $('.v3d-play').textContent = p ? '❚❚' : '▶'; $('.v3d-play').setAttribute('aria-label', p ? 'Pause' : 'Play') };
  const go = frame => { f = ((frame - 1 + N) % N) + 1; pose(f) };
  $('.v3d-play').onclick = () => setPlaying(!playing);
  $('.v3d-prev').onclick = () => { setPlaying(false); go(f - 1) };
  $('.v3d-next').onclick = () => { setPlaying(false); go(f + 1) };
  $('.v3d-scrub input').oninput = e => { setPlaying(false); go(+e.target.value) };
  $('.v3d-speed').onchange = e => { speed = +e.target.value };
  el.querySelectorAll('.v3d-opts input').forEach(i => i.onchange = () => pose(f));
  const onKey = e => {
    if (e.target.closest('input,select,textarea') && e.target.type !== 'range') return;
    if (e.key === ' ') { e.preventDefault(); setPlaying(!playing) }
    else if (e.key === ',' || e.key === 'ArrowLeft' && e.target === document.body) { setPlaying(false); go(f - 1) }
    else if (e.key === '.' || e.key === 'ArrowRight' && e.target === document.body) { setPlaying(false); go(f + 1) }
  };
  document.addEventListener('keydown', onKey);
  setPlaying(playing);
  go(1);
  const tick = now => {
    if (disposed) return;
    raf = requestAnimationFrame(tick);
    const dt = Math.min(now - last, 100); last = now;
    if (playing) { acc += dt * speed * 30 / 1000; if (acc >= 1) { const n = Math.floor(acc); acc -= n; go(f + n) } }
    controls.update(); renderer.render(scene, camera);
  };
  raf = requestAnimationFrame(tick);
  return {
    dispose() {
      disposed = true; cancelAnimationFrame(raf); ro.disconnect(); document.removeEventListener('keydown', onKey);
      controls.dispose(); renderer.dispose(); sphereG.dispose(); cylG.dispose(); mat.dispose(); ghostMat.dispose();
    },
  };
}

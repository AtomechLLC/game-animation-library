// Blender-style viewport navigation for the 3D preview, ported from the centerpiece splat viewer in
// wia-seasonal-ui-asset-generator (useCenterpieceOrbitNavigation.ts). The camera turns on a sphere around `target`:
//   middle drag: orbit (turntable)       Shift + middle drag: pan
//   left drag and Shift + left drag: the same as the middle button (not in the source; Blender has no left-drag orbit)
//   right drag: pan, and no context menu over the stage
//   wheel, Mouse mode: zoom              wheel, Trackpad mode: orbit (crosses the poles); Shift + wheel: pan
//   Ctrl + wheel or pinch: zoom
//   Numpad 8/2/4/6: orbit 15°  Numpad 9: opposite side  Numpad 1/3/7: front/right/top  Ctrl + Numpad 7: bottom
//   Numpad +/−: zoom  F, Home, Numpad .: frame the move  D, Numpad 0: default camera  Tab: Mouse/Trackpad
// The source world is −Y up; this one is +Y up, so elevation and azimuth signs are flipped to keep every gesture
// moving the view the same way on screen. Keys work while the stage has focus; a click on it gives it focus.
import * as THREE from 'three';

const ORBIT_SENSITIVITY = 0.005, TRACKPAD_ORBIT_SENSITIVITY = 0.005, ZOOM_SENSITIVITY = 0.001, PINCH_ZOOM_SENSITIVITY = 0.005;
const MIN_ELEVATION = -Math.PI / 2 + 0.001, MAX_ELEVATION = Math.PI / 2 - 0.001, ORBIT_STEP = Math.PI / 12, ZOOM_STEP = 0.2;
const MODE_KEY = 'moveExplorerViewportInputMode:v1';
const clampEl = el => Math.max(MIN_ELEVATION, Math.min(MAX_ELEVATION, el));

// cumulative elevation past ±90° comes out the far side: the azimuth turns half way and the view is upside down
export function poleOrbitAngles(cumEl, azBase) {
  const pastPole = Math.cos(cumEl) < 0;
  return {elevation: Math.asin(Math.sin(cumEl)), azimuth: azBase + (pastPole ? Math.PI : 0), pastPole};
}

// The camera's azimuth and elevation around `target` for a target-to-camera direction
export const anglesOf = dir => ({azimuth: Math.atan2(dir.x, dir.z), elevation: Math.atan2(dir.y, Math.hypot(dir.x, dir.z))});

// views: {front, right} azimuths of the character's front and right side. onFrame / onDefault: F and D.
export function createBlenderNavigation({camera, dom, views, onFrame, onDefault, onMode}) {
  const target = new THREE.Vector3();
  let distance = 1, azimuth = 0, elevation = 0, pole = null, limits = {min: 0.01, max: 100}, drag = null;
  let mode = 'trackpad';
  try { const m = localStorage.getItem(MODE_KEY); if (m === 'mouse' || m === 'trackpad') mode = m } catch {}

  function place(pastPole = false) {
    camera.position.set(
      target.x + distance * Math.cos(elevation) * Math.sin(azimuth),
      target.y + distance * Math.sin(elevation),
      target.z + distance * Math.cos(elevation) * Math.cos(azimuth));
    camera.up.set(0, pastPole ? -1 : 1, 0);
    camera.lookAt(target);
    camera.updateMatrixWorld(true);
  }
  const zoom = d => { distance = Math.max(limits.min, Math.min(limits.max, d)); place(pole ? Math.cos(pole.cumEl) < 0 : false) };
  const panScale = () => 2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / (dom.clientHeight || 600);
  const axes = () => { camera.updateMatrixWorld(true); const e = camera.matrixWorld.elements; return [new THREE.Vector3(e[0], e[1], e[2]), new THREE.Vector3(e[4], e[5], e[6])] };

  function onWheel(e) {
    e.preventDefault();
    if (e.ctrlKey) zoom(distance * (1 + e.deltaY * PINCH_ZOOM_SENSITIVITY));
    else if (mode === 'trackpad' && e.shiftKey && e.deltaMode === 0) {
      const s = panScale(), [right, upv] = axes(), d = right.multiplyScalar(e.deltaX * s).addScaledVector(upv, -e.deltaY * s);
      shift(d);
    } else if (mode === 'trackpad') {
      const p = pole || {cumEl: elevation, azBase: azimuth};
      pole = {cumEl: p.cumEl - e.deltaY * TRACKPAD_ORBIT_SENSITIVITY, azBase: p.azBase + e.deltaX * TRACKPAD_ORBIT_SENSITIVITY};
      const a = poleOrbitAngles(pole.cumEl, pole.azBase); azimuth = a.azimuth; elevation = a.elevation; place(a.pastPole);
    } else zoom(distance * (1 + e.deltaY * ZOOM_SENSITIVITY));
  }

  function onPointerDown(e) {
    dom.focus({preventScroll: true});
    if (e.target.closest('button,input,textarea,select')) return;
    // left drags like the middle button; the right button always pans (its menu is blocked)
    if (e.button !== 0 && e.button !== 1 && e.button !== 2) return;
    e.preventDefault();
    dom.setPointerCapture(e.pointerId);
    if (e.shiftKey || e.button === 2) {
      const [right, upv] = axes();
      drag = {mode: 'pan', id: e.pointerId, x: e.clientX, y: e.clientY, cam: camera.position.clone(), target: target.clone(), right, upv, s: panScale()};
    } else drag = {mode: 'orbit', id: e.pointerId, x: e.clientX, y: e.clientY, azimuth, elevation};
  }
  function onPointerMove(e) {
    if (!drag || drag.id !== e.pointerId) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (drag.mode === 'pan') {
      const d = drag.right.clone().multiplyScalar(dx * drag.s).addScaledVector(drag.upv, -dy * drag.s);
      camera.position.copy(drag.cam).add(d); target.copy(drag.target).add(d);
      camera.up.set(0, 1, 0); camera.lookAt(target);
    } else {
      azimuth = drag.azimuth - dx * ORBIT_SENSITIVITY;
      elevation = clampEl(drag.elevation + dy * ORBIT_SENSITIVITY);
      pole = {cumEl: elevation, azBase: azimuth};
      place();
    }
  }
  function onPointerUp(e) {
    if (!drag || drag.id !== e.pointerId) return;
    try { dom.releasePointerCapture(e.pointerId) } catch {}
    drag = null;
  }
  // a middle press must not start the browser's auto-scroll
  const noAutoScroll = e => { if (e.button === 1) e.preventDefault() };
  const noMenu = e => e.preventDefault();

  function setMode(m) {
    mode = m;
    try { localStorage.setItem(MODE_KEY, m) } catch {}
    onMode?.(m);
  }

  function onKey(e) {
    const a = document.activeElement;
    if (a && (a.matches('textarea,select,button') || (a.matches('input') && a.type !== 'range'))) return;
    const k = e.key.toLowerCase(), c = e.code;
    if (e.key === 'Tab' && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); setMode(mode === 'mouse' ? 'trackpad' : 'mouse'); return }
    if ((k === 'd' && !e.shiftKey && !e.ctrlKey && !e.metaKey) || c === 'Numpad0') { e.preventDefault(); onDefault?.(); return }
    if ((e.key === 'Home' && !e.shiftKey) || (k === 'f' && !e.ctrlKey && !e.metaKey && !e.shiftKey) || c === 'NumpadDecimal') { e.preventDefault(); onFrame?.(); return }
    if (!/^Numpad[1-46-9]$|^NumpadAdd$|^NumpadSubtract$/.test(c)) return;
    e.preventDefault();
    if (/^Numpad[24689]$/.test(c)) {
      let {cumEl, azBase} = pole || {cumEl: elevation, azBase: azimuth};
      if (c === 'Numpad8') cumEl += ORBIT_STEP;
      else if (c === 'Numpad2') cumEl -= ORBIT_STEP;
      else if (c === 'Numpad4') azBase += ORBIT_STEP;
      else if (c === 'Numpad6') azBase -= ORBIT_STEP;
      else { cumEl = -cumEl; azBase += Math.PI }
      ({elevation, azimuth} = poleOrbitAngles(cumEl, azBase));
      pole = {cumEl, azBase};
    } else if (c === 'NumpadAdd') distance = Math.max(limits.min, distance * (1 - ZOOM_STEP));
    else if (c === 'NumpadSubtract') distance = Math.min(limits.max, distance * (1 + ZOOM_STEP));
    else if (c === 'Numpad1') { azimuth = views.front; elevation = 0; pole = {cumEl: 0, azBase: azimuth} }
    else if (c === 'Numpad3') { azimuth = views.right; elevation = 0; pole = {cumEl: 0, azBase: azimuth} }
    else if (c === 'Numpad7') { azimuth = views.front; elevation = e.ctrlKey ? MIN_ELEVATION : MAX_ELEVATION; pole = {cumEl: elevation, azBase: azimuth} }
    place(Math.cos(pole?.cumEl ?? elevation) < 0);
  }

  dom.addEventListener('wheel', onWheel, {passive: false});
  dom.addEventListener('pointerdown', onPointerDown);
  dom.addEventListener('pointermove', onPointerMove);
  dom.addEventListener('pointerup', onPointerUp);
  dom.addEventListener('pointercancel', onPointerUp);
  dom.addEventListener('mousedown', noAutoScroll);
  dom.addEventListener('auxclick', noAutoScroll);
  dom.addEventListener('contextmenu', noMenu);
  dom.addEventListener('keydown', onKey);

  // move the camera and target together (pan, or riding along with root motion)
  function shift(d) { camera.position.add(d); target.add(d); camera.updateMatrixWorld(true) }

  return {
    target,
    get mode() { return mode }, setMode,
    get state() { return {target: target.clone(), distance, azimuth, elevation, pole: pole && {...pole}, limits: {...limits}} },
    // look at `center` from direction `dir` (target to camera) at `dist`; `size` sets the zoom limits
    frameTo(center, dir, dist, size) {
      target.copy(center); distance = dist; ({azimuth, elevation} = anglesOf(dir)); pole = null;
      limits = {min: size / 10, max: size * 20};
      place();
    },
    // snap to an angle at the current distance (orientation gizmo)
    setAngles(az, el) { azimuth = az; elevation = clampEl(el); pole = {cumEl: elevation, azBase: azimuth}; place() },
    shift,
    dispose() {
      dom.removeEventListener('wheel', onWheel); dom.removeEventListener('pointerdown', onPointerDown);
      dom.removeEventListener('pointermove', onPointerMove); dom.removeEventListener('pointerup', onPointerUp);
      dom.removeEventListener('pointercancel', onPointerUp); dom.removeEventListener('mousedown', noAutoScroll);
      dom.removeEventListener('auxclick', noAutoScroll); dom.removeEventListener('contextmenu', noMenu);
      dom.removeEventListener('keydown', onKey);
    },
  };
}

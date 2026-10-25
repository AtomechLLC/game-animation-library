// Render stats for the 3D preview, a developer overlay toggled with ` (backquote) while the view has focus. It shows
// what the viewer costs over a 1 s window: animation-frame loop ticks, renders, draw calls and triangles per render,
// render CPU time, GPU memory, the playback state, whether the view is on screen, and time since the last input.
// "Copy JSON" copies the same snapshot debug.stats() returns, for performance notes (WP-15,
// docs/tasks/performance-2026-10/). Off, it costs one boolean check per call: no timer, observer or clock reads.
// Modelled on the centerpiece viewport's debug metrics in wia-seasonal-ui-asset-generator.

let on = false;  // kept for the page's lifetime, so the overlay survives game switches (a new viewer per game)

const fmt = n => n >= 100 ? Math.round(n).toLocaleString('en') : n >= 10 ? n.toFixed(1) : n.toFixed(2);
const secs = ms => ms < 60000 ? (ms / 1000).toFixed(1) + ' s' : Math.floor(ms / 60000) + ' min ' + Math.round(ms % 60000 / 1000) + ' s';

// stage: the view's element; renderer: its THREE.WebGLRenderer; state() → {playing, frame, frames}
export function createRenderStats(stage, renderer, state) {
  const zero = () => ({ticks: 0, renders: 0, drawCalls: 0, triangles: 0, renderMs: 0});
  let totals = zero(), last = zero(), rates = zero(), lastCalls = 0, lastTriangles = 0, maxMs = 0, windowMax = 0;
  let started = 0, sampledAt = 0, inputAt = 0, visible = true;
  let panel = null, timer = 0, io = null;

  const input = () => { inputAt = performance.now() };
  const inputs = ['pointerdown', 'wheel', 'keydown'];

  function sample() {
    const now = performance.now(), dt = (now - sampledAt) / 1000;
    if (dt <= 0) return;
    for (const k in totals) rates[k] = (totals[k] - last[k]) / dt;
    last = {...totals}; sampledAt = now; windowMax = maxMs; maxMs = 0;
  }

  function snapshot() {
    const now = performance.now(), s = state(), m = renderer.info.memory;
    return {
      at: new Date().toISOString(), on, sessionMs: on ? Math.round(now - started) : 0, idleSinceInputMs: on ? Math.round(now - inputAt) : 0,
      state: {playing: s.playing, frame: s.frame, frames: s.frames, visible, pageVisible: document.visibilityState === 'visible'},
      totals: {...totals, renderMs: +totals.renderMs.toFixed(1)},
      rates: {ticksPerSec: +rates.ticks.toFixed(1), rendersPerSec: +rates.renders.toFixed(1), drawCallsPerSec: Math.round(rates.drawCalls),
        renderCpuMsPerSec: +rates.renderMs.toFixed(2)},
      perRender: {drawCalls: lastCalls, triangles: lastTriangles, renderCpuMsAvg: rates.renders ? +(rates.renderMs / rates.renders).toFixed(3) : 0,
        renderCpuMsMax: +windowMax.toFixed(3)},
      memory: {geometries: m.geometries, textures: m.textures, jsHeapMB: performance.memory ? +(performance.memory.usedJSHeapSize / 2 ** 20).toFixed(1) : null},
    };
  }

  function paint() {
    sample();
    const x = snapshot(), r = x.rates, p = x.perRender, st = x.state, idle = x.idleSinceInputMs;
    const rows = [
      ['loop', `${fmt(r.ticksPerSec)}/s`],
      ['renders', `${fmt(r.rendersPerSec)}/s · total ${totals.renders.toLocaleString('en')}`],
      ['draw calls', `${p.drawCalls}/render · ${r.drawCallsPerSec.toLocaleString('en')}/s`],
      ['triangles', `${p.triangles.toLocaleString('en')}/render`],
      ['render cpu', `${p.renderCpuMsAvg.toFixed(2)} ms avg · ${p.renderCpuMsMax.toFixed(2)} max`],
      ['gpu memory', `${x.memory.geometries} geometries · ${x.memory.textures} textures`],
      ...(x.memory.jsHeapMB != null ? [['js heap', `${x.memory.jsHeapMB} MB`]] : []),
      ['state', `${st.playing ? 'playing' : 'paused'} · frame ${st.frame}/${st.frames} · ${st.visible ? 'on screen' : 'off screen'}`],
      ['idle input', secs(idle) + (idle >= 10000 ? ' (≥10 s benchmark)' : idle >= 5000 ? ' (≥5 s benchmark)' : '')],
    ];
    panel.querySelector('dl').innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
  }

  function start() {
    totals = zero(); last = zero(); rates = zero(); maxMs = windowMax = 0;
    started = sampledAt = inputAt = performance.now();
    panel = document.createElement('div');
    panel.className = 'v3d-stats';
    panel.innerHTML = '<p>render stats (1 s)</p><dl></dl><button type="button">Copy JSON</button>';
    const copy = panel.querySelector('button');
    // like the view's other overlay buttons: keep focus (and the keys) on the stage, don't orbit or zoom
    copy.addEventListener('mousedown', e => { e.preventDefault(); stage.focus({preventScroll: true}) });
    for (const t of ['pointerdown', 'wheel']) panel.addEventListener(t, e => e.stopPropagation());
    copy.onclick = async () => {
      try { await navigator.clipboard.writeText(JSON.stringify(snapshot(), null, 2)); copy.textContent = 'Copied' } catch (e) { copy.textContent = 'Copy failed' }
      setTimeout(() => { if (panel) copy.textContent = 'Copy JSON' }, 1500);
    };
    stage.append(panel);
    for (const t of inputs) stage.addEventListener(t, input, true);
    io = new IntersectionObserver(([e]) => { visible = e.isIntersecting }); io.observe(stage);
    timer = setInterval(paint, 1000); paint();
  }

  function stop() {
    clearInterval(timer); timer = 0; io?.disconnect(); io = null;
    for (const t of inputs) stage.removeEventListener(t, input, true);
    panel?.remove(); panel = null;
    totals = zero(); last = zero(); rates = zero(); lastCalls = lastTriangles = maxMs = windowMax = 0;
  }

  if (on) start();
  return {
    // one pass through the viewer's animation-frame loop
    tick() { if (on) totals.ticks++ },
    // draw() is the viewer's renderer.render call, timed and counted while the overlay shows
    render(draw) {
      if (!on) return draw();
      const t = performance.now(); draw(); const ms = performance.now() - t;
      const i = renderer.info.render;
      totals.renders++; totals.renderMs += ms; totals.drawCalls += i.calls; totals.triangles += i.triangles;
      lastCalls = i.calls; lastTriangles = i.triangles; if (ms > maxMs) maxMs = ms;
    },
    toggle() { on = !on; on ? start() : stop() },
    snapshot,
    dispose: stop,
  };
}

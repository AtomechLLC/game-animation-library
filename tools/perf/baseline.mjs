// Performance baseline for the three apps (WP-12, docs/tasks/performance-2026-10/wp-12-performance-baseline.md).
// Drives an installed Chrome over the DevTools protocol (Node 22+, no dependencies) and writes one JSON file of
// measurements; docs/reports/performance-2026-10/ explains them.
//
//   node tools/perf/baseline.mjs [--base URL] [--out FILE] [--only load,scroll,interact,idle,hover,memory,hosting]
//
// --base defaults to the live GitHub Pages site. CHROME overrides the browser path. Each scenario runs in a fresh
// browser profile, so nothing is cached unless the scenario says so.
import {spawn, execFileSync} from 'node:child_process';
import {mkdtempSync, rmSync, writeFileSync, mkdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d };
const BASE = arg('base', 'https://atomechllc.github.io/game-animation-library/').replace(/\/?$/, '/');
const OUT = arg('out', `docs/reports/performance-2026-10/baseline-${new Date().toISOString().slice(0, 10)}.json`);
const ONLY = arg('only', 'load,scroll,interact,idle,hover,memory,hosting').split(',');
const CHROME = process.env.CHROME || {
  win32: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  darwin: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
}[process.platform] || 'google-chrome';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = (...a) => console.error('[perf]', ...a);

// Lighthouse's default mobile throttling ("slow 4G" and a 4x slower CPU), standing in for a student laptop on
// school Wi-Fi; the unthrottled runs are this machine on its own connection
const THROTTLED = {latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 750e3 / 8, cpu: 4};

// ---------- DevTools protocol client ----------

async function launch() {
  const dir = mkdtempSync(path.join(tmpdir(), 'perf-chrome-'));
  const proc = spawn(CHROME, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${dir}`, '--no-first-run',
    '--no-default-browser-check', '--window-size=1440,900', '--enable-precise-memory-info', 'about:blank'], {stdio: ['ignore', 'ignore', 'pipe']});
  const url = await new Promise((ok, fail) => {
    let buf = '';
    proc.stderr.on('data', d => { buf += d; const m = buf.match(/DevTools listening on (ws:\S+)/); if (m) ok(m[1]) });
    proc.on('exit', c => fail(new Error('Chrome exited ' + c)));
    setTimeout(() => fail(new Error('Chrome did not start')), 20000);
  });
  const ws = new WebSocket(url);
  await new Promise((ok, fail) => { ws.onopen = ok; ws.onerror = fail });
  let id = 0;
  const waiting = new Map(), listeners = new Set();
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && waiting.has(m.id)) { const [ok, fail] = waiting.get(m.id); waiting.delete(m.id); m.error ? fail(new Error(m.error.message)) : ok(m.result) }
    else for (const l of listeners) l(m);
  };
  const send = (method, params = {}, sessionId) => new Promise((ok, fail) => {
    const n = ++id; waiting.set(n, [ok, fail]); ws.send(JSON.stringify({id: n, method, params, sessionId}));
  });
  return {
    send, listeners,
    async close() { try { await send('Browser.close') } catch {} ws.close(); await sleep(500); try { proc.kill() } catch {} try { rmSync(dir, {recursive: true, force: true}) } catch {} },
  };
}

// In-page instrumentation, installed before any page script runs. It records long tasks, paint timings, event
// timings, WebGL draw calls (and how many animation frames contained at least one), decoded ImageBitmap bytes,
// history.replaceState calls and WebGL contexts created, and can wrap page functions to time them.
const INSTRUMENT = `(() => {
  const P = window.__perf = {longtasks: [], lcp: 0, fcp: 0, events: [], firstDraw: 0, draws: 0, drawFrames: 0, frames: 0,
    draws2d: 0, drawFrames2d: 0, bitmaps: 0, bitmapBytes: 0, replaceState: 0, webgl: 0, calls: {}, keyAt: 0, showFrameAt: 0};
  const obs = (type, fn, o = {}) => { try { new PerformanceObserver(l => l.getEntries().forEach(fn)).observe({type, buffered: true, ...o}) } catch {} };
  obs('longtask', e => P.longtasks.push([e.startTime, e.duration]));
  obs('largest-contentful-paint', e => { P.lcp = e.startTime });
  obs('paint', e => { if (e.name === 'first-contentful-paint') P.fcp = e.startTime });
  obs('event', e => P.events.push([e.name, e.duration]), {durationThreshold: 16});
  for (const C of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) if (C) for (const k of ['drawElements', 'drawArrays']) {
    const f = C.prototype[k];
    C.prototype[k] = function (...a) { if (!P.firstDraw) P.firstDraw = performance.now(); P.draws++; P.drew = true; return f.apply(this, a) };
  }
  const d2 = CanvasRenderingContext2D.prototype.drawImage;
  CanvasRenderingContext2D.prototype.drawImage = function (...a) { P.draws2d++; P.drew2d = true; return d2.apply(this, a) };
  const loop = () => { P.frames++; if (P.drew) { P.drawFrames++; P.drew = false } if (P.drew2d) { P.drawFrames2d++; P.drew2d = false } requestAnimationFrame(loop) };
  requestAnimationFrame(loop);
  const cib = window.createImageBitmap;
  window.createImageBitmap = (...a) => cib(...a).then(b => { P.bitmaps++; P.bitmapBytes += b.width * b.height * 4; return b });
  const rs = history.replaceState;
  history.replaceState = function (...a) { P.replaceState++; return rs.apply(this, a) };
  const gc = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (t, ...a) { const c = gc.call(this, t, ...a); if (c && /webgl/.test(t) && !this.__perfGl) { this.__perfGl = 1; P.webgl++ } return c };
  addEventListener('keydown', () => { P.keyAt = performance.now() }, true);
  const rec = (name, ms) => { const c = P.calls[name] ||= {n: 0, ms: 0, max: 0}; c.n++; c.ms += ms; c.max = Math.max(c.max, ms) };
  P.wrap = (obj, names, label = '') => { for (const k of names) { const f = obj[k]; if (typeof f !== 'function' || f.__perf) continue;
    const w = function (...a) { const t = performance.now(), r = f.apply(this, a); rec(label + k, performance.now() - t);
      if (r && r.then) r.then(() => { rec(label + k + ' (settled)', performance.now() - t); if (k === 'show') requestAnimationFrame(() => { P.showFrameAt = performance.now() }) }, () => {});
      return r };
    w.__perf = 1; obj[k] = w } };
  P.reset = () => { P.longtasks = []; P.events = []; P.calls = {}; P.draws = 0; P.drawFrames = 0; P.draws2d = 0; P.drawFrames2d = 0; P.frames = 0; P.replaceState = 0 };
})()`;

async function openPage(b, {throttle = false, cache = false} = {}) {
  const {targetId} = await b.send('Target.createTarget', {url: 'about:blank'});
  const {sessionId} = await b.send('Target.attachToTarget', {targetId, flatten: true});
  const s = (m, p) => b.send(m, p, sessionId);
  const net = {requests: 0, bytes: 0, byType: {}, inflight: new Map(), last: Date.now(), types: new Map(), status: {}}, consoleMsgs = [];
  const loaded = {at: 0};
  const on = m => {
    if (m.sessionId !== sessionId) return;
    const p = m.params;
    if (m.method === 'Network.requestWillBeSent') { net.requests++; net.inflight.set(p.requestId, 1); net.last = Date.now() }
    if (m.method === 'Network.responseReceived') { net.types.set(p.requestId, p.type); net.status[p.response.status] = (net.status[p.response.status] || 0) + 1 }
    if (m.method === 'Network.loadingFinished' || m.method === 'Network.loadingFailed') {
      net.inflight.delete(p.requestId); net.last = Date.now();
      if (p.encodedDataLength) { net.bytes += p.encodedDataLength; const t = net.types.get(p.requestId) || 'Other'; net.byType[t] = (net.byType[t] || 0) + p.encodedDataLength }
    }
    if (m.method === 'Page.loadEventFired') loaded.at = Date.now();
    if (m.method === 'Runtime.consoleAPICalled' && /warn|error/.test(p.type)) consoleMsgs.push(p.args.map(a => a.value ?? a.description).join(' ').slice(0, 200));
    if (m.method === 'Log.entryAdded' && /warning|error/.test(p.entry.level)) consoleMsgs.push(p.entry.text.slice(0, 200));
  };
  b.listeners.add(on);
  for (const d of ['Page', 'Network', 'Runtime', 'Performance', 'Log']) await s(d + '.enable');
  await s('Network.setCacheDisabled', {cacheDisabled: !cache});
  if (throttle) {
    await s('Network.emulateNetworkConditions', {offline: false, ...THROTTLED, cpu: undefined});
    await s('Emulation.setCPUThrottlingRate', {rate: THROTTLED.cpu});
  }
  await s('Emulation.setDeviceMetricsOverride', {width: 1440, height: 900, deviceScaleFactor: 1, mobile: false});
  await s('Page.addScriptToEvaluateOnNewDocument', {source: INSTRUMENT});
  const ev = async expr => {
    const r = await s('Runtime.evaluate', {expression: expr, awaitPromise: true, returnByValue: true});
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  const page = {
    s, ev, net, consoleMsgs,
    resetNet() { net.requests = 0; net.bytes = 0; net.byType = {}; net.status = {} },
    // a change of hash only is a same-document navigation: no load event follows
    async goto(url) { loaded.at = 0; const r = await s('Page.navigate', {url}); if (!r.loaderId) return; const t = Date.now(); while (!loaded.at && Date.now() - t < 180000) await sleep(100) },
    // network quiet: nothing in flight (or only long-lived requests) for `ms`
    async quiet(ms = 2000, max = 180000) { const t = Date.now(); while (Date.now() - t < max) { if (net.inflight.size === 0 && Date.now() - net.last > ms) return true; await sleep(100) } return false },
    async until(expr, max = 60000) { const t = Date.now(); while (Date.now() - t < max) { if (await ev(expr)) return true; await sleep(100) } return false },
    async metrics() { const {metrics} = await s('Performance.getMetrics'); return Object.fromEntries(metrics.map(m => [m.name, m.value])) },
    async heap() { await s('HeapProfiler.collectGarbage'); return (await s('Runtime.getHeapUsage')).usedSize },
    async key(key, code, vk, {repeat = false, type = 'keyDown'} = {}) { await s('Input.dispatchKeyEvent', {type, key, code, windowsVirtualKeyCode: vk, autoRepeat: repeat}) },
    async click(sel) {
      const r = await ev(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null; e.scrollIntoView({block: 'center'}); const b = e.getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2] })()`);
      if (!r) throw new Error('not found: ' + sel);
      await sleep(150);
      for (const type of ['mousePressed', 'mouseReleased']) await s('Input.dispatchMouseEvent', {type, x: r[0], y: r[1], button: 'left', clickCount: 1});
    },
    close() { b.listeners.delete(on) },
  };
  return page;
}

// what one window of activity cost on the main thread: long tasks, Total Blocking Time, the slowest event
// (a stand-in for Interaction to Next Paint) and the timed page functions
const activity = p => p.ev(`(() => { const P = __perf, lt = P.longtasks.map(x => x[1]);
  return {longTasks: lt.length, longTaskMs: Math.round(lt.reduce((a, b) => a + b, 0)), longestTaskMs: Math.round(Math.max(0, ...lt)),
    blockingMs: Math.round(lt.reduce((a, b) => a + Math.max(0, b - 50), 0)), slowestEventMs: Math.max(0, ...P.events.map(e => e[1])),
    events: P.events.length, replaceState: P.replaceState,
    calls: Object.fromEntries(Object.entries(P.calls).map(([k, c]) => [k, {n: c.n, totalMs: Math.round(c.ms), maxMs: Math.round(c.max)}]))} })()`);

const kb = n => Math.round(n / 1024);

// process memory (MB) by Chrome process type, from the operating system
async function processMemory(b) {
  const {processInfo} = await b.send('SystemInfo.getProcessInfo');
  const out = {};
  for (const p of processInfo) {
    let mb = null;
    try {
      mb = process.platform === 'win32'
        ? Number(execFileSync('powershell', ['-NoProfile', '-Command', `(Get-Process -Id ${p.id}).PrivateMemorySize64`], {stdio: ['ignore', 'pipe', 'ignore']}).toString().trim()) / 2 ** 20
        : Number(execFileSync('ps', ['-o', 'rss=', '-p', String(p.id)]).toString().trim()) / 1024;
    } catch {}
    if (mb != null) out[p.type] = Math.round((out[p.type] || 0) + mb);
  }
  return out;
}

async function cpuByType(b) {
  const {processInfo} = await b.send('SystemInfo.getProcessInfo');
  const out = {}; for (const p of processInfo) out[p.type] = (out[p.type] || 0) + p.cpuTime; return out;
}

const PAGES = {atlas: '', moveExplorer: 'frame-data.html', trends: 'trends.html'};
const ME = BASE + 'frame-data.html';
const glRenderer = p => p.ev(`(() => { const g = document.createElement('canvas').getContext('webgl'), x = g && g.getExtension('WEBGL_debug_renderer_info'); return x ? g.getParameter(x.UNMASKED_RENDERER_WEBGL) : null })()`);

// ---------- scenarios ----------

const results = {base: BASE, startedAt: new Date().toISOString(), chrome: null, throttled: THROTTLED};

async function withBrowser(fn) {
  const b = await launch();
  try { results.chrome ||= (await b.send('Browser.getVersion')).product; return await fn(b) } finally { await b.close() }
}

async function loadOnce(b, name, {throttle, cache = false, page} = {}) {
  const p = page || await openPage(b, {throttle, cache});
  p.resetNet();
  const t0 = Date.now();
  await p.goto(BASE + PAGES[name]);
  const loadMs = Date.now() - t0;
  if (name === 'moveExplorer') await p.until('__perf.firstDraw > 0', throttle ? 180000 : 60000);
  await p.quiet(throttle ? 3000 : 2000);
  const r = await p.ev(`(() => { const P = __perf, nav = performance.getEntriesByType('navigation')[0], lt = P.longtasks.map(x => x[1]);
    return {fcpMs: Math.round(P.fcp), lcpMs: Math.round(P.lcp), domContentLoadedMs: Math.round(nav.domContentLoadedEventEnd), loadEventMs: Math.round(nav.loadEventEnd),
      firstWebglDrawMs: P.firstDraw ? Math.round(P.firstDraw) : null, blockingMs: Math.round(lt.filter((_, i) => P.longtasks[i][0] > P.fcp).reduce((a, b) => a + Math.max(0, b - 50), 0)),
      longTasks: lt.length, longestTaskMs: Math.round(Math.max(0, ...lt)), domNodes: document.getElementsByTagName('*').length} })()`);
  return {...r, wallLoadMs: loadMs, requests: p.net.requests, transferredKB: kb(p.net.bytes),
    byTypeKB: Object.fromEntries(Object.entries(p.net.byType).map(([k, v]) => [k, kb(v)])), status: {...p.net.status}, page: p};
}

async function scenarioLoad() {
  results.load = {};
  for (const name of Object.keys(PAGES)) {
    for (const throttle of [false, true]) {
      const key = `${name}.${throttle ? 'throttled' : 'unthrottled'}`;
      log('load', key);
      results.load[key] = await withBrowser(async b => {
        const cold = await loadOnce(b, name, {throttle, cache: true});
        const page = cold.page; delete cold.page;
        if (name === 'moveExplorer') cold.webglRenderer = await glRenderer(page);
        // a return visit within Pages' 10-minute cache lifetime: navigate away and back with the cache kept
        await page.goto('about:blank');
        const warm = await loadOnce(b, name, {throttle, page}); delete warm.page;
        return {cold, repeat: warm};
      });
    }
  }
}

async function scenarioScroll() {
  log('scroll atlas');
  results.atlasScroll = await withBrowser(async b => {
    const p = await openPage(b);
    await p.goto(BASE); await p.quiet(2000);
    const first = {requests: p.net.requests, transferredKB: kb(p.net.bytes)};
    p.resetNet();
    const t0 = Date.now();
    await p.ev('__perf.reset()');
    for (let i = 0; i < 400; i++) {
      const done = await p.ev('(() => { scrollBy(0, 700); return innerHeight + scrollY >= document.documentElement.scrollHeight - 2 })()');
      await sleep(250);
      if (done) break;
    }
    await p.quiet(3000);
    const idle = await idleWindow(b, p, 5000);
    return {firstScreen: first, fullScroll: {requests: p.net.requests, transferredKB: kb(p.net.bytes), seconds: Math.round((Date.now() - t0) / 1000),
      images: await p.ev(`document.querySelectorAll('img').length`), main: await activity(p)}, idleAtBottom: idle};
  });
}

// main-thread busy time and animation frames over `ms` of doing nothing
async function idleWindow(b, p, ms) {
  await p.ev('__perf.reset()');
  const m0 = await p.metrics(), c0 = await cpuByType(b);
  await sleep(ms);
  const m1 = await p.metrics(), c1 = await cpuByType(b), P = await p.ev('({draws: __perf.draws, drawFrames: __perf.drawFrames, draws2d: __perf.draws2d, drawFrames2d: __perf.drawFrames2d})');
  const s = ms / 1000;
  return {seconds: s, webglFramesPerSecond: +(P.drawFrames / s).toFixed(1), drawCallsPerSecond: Math.round(P.draws / s),
    canvas2dFramesPerSecond: +(P.drawFrames2d / s).toFixed(1),
    mainThreadBusyMsPerSecond: Math.round((m1.TaskDuration - m0.TaskDuration) * 1000 / s),
    cpuMsPerSecondByProcess: Object.fromEntries(Object.keys(c1).map(k => [k, Math.round(((c1[k] - (c0[k] || 0)) * 1000) / s)]))};
}

async function wrapMoveExplorer(p) {
  await p.ev(`(() => { __perf.wrap(window, ['renderAll', 'renderTable', 'preview', 'stepMove', 'dock']);
    return DOCK.view && DOCK.view.then(v => __perf.wrap(v, ['show', 'setView'], 'viewer.')) })()`);
}

async function scenarioInteract() {
  results.interact = {};
  for (const throttle of [false, true]) {
    const tag = throttle ? 'cpu4x' : 'cpu1x', out = results.interact[tag] = {};
    await withBrowser(async b => {
      const p = await openPage(b, {cache: true});
      if (throttle) await p.s('Emulation.setCPUThrottlingRate', {rate: THROTTLED.cpu});

      log(tag, 'atlas search');
      await p.goto(BASE); await p.quiet(2000);
      await p.ev(`__perf.wrap(window, ['render'])`);
      await p.ev(`document.querySelector('#q').focus()`);
      await p.ev('__perf.reset()'); p.resetNet();
      for (const ch of 'heavy atta') { await p.s('Input.dispatchKeyEvent', {type: 'keyDown', key: ch, text: ch}); await p.s('Input.dispatchKeyEvent', {type: 'keyUp', key: ch}); await sleep(120) }
      await sleep(1500);
      out.atlasSearchTenCharacters = {...await activity(p), transferredKB: kb(p.net.bytes)};

      log(tag, 'move explorer: slider');
      await p.goto(ME); await p.until('__perf.firstDraw > 0'); await p.quiet(2000);
      await wrapMoveExplorer(p);
      const r = await p.ev(`(() => { const e = document.querySelector('#maxStart'); e.scrollIntoView({block: 'center'}); const b = e.getBoundingClientRect(); return [b.left, b.right, b.y + b.height / 2] })()`);
      await sleep(200); await p.ev('__perf.reset()');
      await p.s('Input.dispatchMouseEvent', {type: 'mousePressed', x: r[1] - 3, y: r[2], button: 'left', clickCount: 1});
      for (let i = 0; i <= 60; i++) { await p.s('Input.dispatchMouseEvent', {type: 'mouseMoved', x: r[1] - 3 - (r[1] - r[0] - 6) * i / 60, y: r[2], button: 'left', buttons: 1}); await sleep(33) }
      await p.s('Input.dispatchMouseEvent', {type: 'mouseReleased', x: r[0] + 3, y: r[2], button: 'left', clickCount: 1});
      await sleep(1000);
      out.startupSliderTwoSecondDrag = await activity(p);

      log(tag, 'move explorer: class pick');
      await p.goto(ME); await p.until('__perf.firstDraw > 0'); await p.quiet(2000);
      await wrapMoveExplorer(p); await p.ev('__perf.reset()');
      await p.click('#index .tile[data-cls="Greatsword"]');
      await p.quiet(1500); await sleep(500);
      out.pickEldenRingClass = {...await activity(p), domNodes: await p.ev(`document.getElementsByTagName('*').length`),
        hiddenTableRows: await p.ev(`document.querySelectorAll('#table tr').length`), movesetRows: await p.ev(`document.querySelectorAll('#mlist tr[data-m]').length`)};

      log(tag, 'move explorer: single steps');
      await wrapMoveExplorer(p);
      await p.ev(`document.activeElement && document.activeElement.blur()`);
      const steps = [];
      for (let i = 0; i < 6; i++) {
        // a frame from the previous move can still arrive late, so only a frame after this key counts
        await p.ev('__perf.showFrameAt = 0; __perf.keyAt = 0');
        await p.key('ArrowDown', 'ArrowDown', 40); await p.key('ArrowDown', 'ArrowDown', 40, {type: 'keyUp'});
        await p.until('__perf.keyAt > 0 && __perf.showFrameAt > __perf.keyAt', 30000);
        steps.push(Math.round(await p.ev('__perf.showFrameAt - __perf.keyAt')));
        await p.quiet(800);
      }
      out.singleDownStepToFirstFrameMs = steps;

      log(tag, 'move explorer: hold Down');
      await p.ev('__perf.reset()');
      const before = await p.ev('DOCK.key');
      await p.key('ArrowDown', 'ArrowDown', 40);
      for (let i = 0; i < 60; i++) { await sleep(33); await p.key('ArrowDown', 'ArrowDown', 40, {repeat: true}) }
      await p.key('ArrowDown', 'ArrowDown', 40, {type: 'keyUp'});
      await p.quiet(1500);
      out.holdDownTwoSeconds = {...await activity(p), keyEvents: 61, from: before, to: await p.ev('DOCK.key'),
        consoleWarnings: p.consoleMsgs.filter(m => /replaceState|history|throttl/i.test(m)).length};
    });
  }
}

// The viewer's cost in each state it can sit in: playing, paused, folded ("Hide"), hidden (a search that matches no
// move hides the dock) and, before a class is picked, scrolled off screen. One game per viewer kind: Elden Ring (3D),
// Street Fighter III (sprite sheets), Super Smash Bros. Ultimate (clips; it has no example viewer before a class)
const IDLE_GAMES = [
  {key: 'eldenRing3d', game: 'elden-ring', cls: 'Greatsword', example: true},
  {key: 'streetFighterSprites', game: 'street-fighter-3-third-strike', cls: 'ryu', example: true},
  {key: 'smashClips', game: 'super-smash-bros-ultimate', cls: 'kazuya', example: false},
];
async function scenarioIdle() {
  results.idle = {};
  for (const g of IDLE_GAMES) {
    log('idle viewer', g.key);
    results.idle[g.key] = await withBrowser(async b => {
      const p = await openPage(b, {cache: true}), out = {}, ready = `!document.querySelector('#dock').hidden && !!DOCK.key`;
      await p.goto(`${ME}#g=${g.game}&c=${g.cls}`); await p.until(ready); await p.quiet(2000); await sleep(1500);
      if (g.key === 'eldenRing3d') out.webglRenderer = await glRenderer(p);
      out.playing = await idleWindow(b, p, 5000);
      await p.ev(`DOCK.view.then(v => v.setView({frame: 10}))`); await sleep(300);
      out.paused = await idleWindow(b, p, 5000);
      await p.ev(`pickMin(true)`); await sleep(300);
      out.foldedPaused = await idleWindow(b, p, 5000);
      await p.ev(`pickMin(false)`); await sleep(300);
      await p.ev(`(() => { const q = document.querySelector('#q'); q.value = 'zzzzzz'; q.dispatchEvent(new Event('input', {bubbles: true})) })()`);
      await sleep(800);
      out.hiddenByEmptySearch = {dockHidden: await p.ev(`document.querySelector('#dock').hidden`), ...await idleWindow(b, p, 5000)};
      if (g.example) {
        await p.goto(`${ME}#g=${g.game}`); await p.ev('location.reload()'); await sleep(500);
        await p.until(ready); await p.quiet(2000); await sleep(1500);
        await p.ev(`DOCK.view.then(v => v.setView({frame: 10}))`);
        await p.ev(`scrollTo(0, document.documentElement.scrollHeight)`); await sleep(500);
        out.exampleOffScreenPaused = {dockInView: await p.ev(`document.querySelector('#dock').getBoundingClientRect().bottom > 0`), ...await idleWindow(b, p, 5000)};
      }
      return out;
    });
  }
}

// Hover prefetch: sweep the pointer down rows of the move table (Elden Ring, no class picked) and the Moveset
// Inspector (Super Smash Bros. Ultimate, Kazuya), 60 ms per row, and count what downloads without a click
async function scenarioHover() {
  results.hover = {};
  for (const [key, hash, sel] of [['eldenRingAllClassesTable', '', '#table tr[data-m]'], ['smashMovesetInspector', '#g=super-smash-bros-ultimate&c=kazuya', '#mlist tr[data-m]']]) {
    log('hover', key);
    results.hover[key] = await withBrowser(async b => {
      const p = await openPage(b, {cache: true});
      await p.goto(ME + hash); await p.until(`!document.querySelector('#dock').hidden && !!DOCK.key`); await p.quiet(2000); await sleep(1000);
      p.resetNet(); await p.ev('__perf.reset()');
      const n = Math.min(50, await p.ev(`document.querySelectorAll(${JSON.stringify(sel)}).length`));
      for (let i = 0; i < n; i++) {
        const r = await p.ev(`(() => { const e = document.querySelectorAll(${JSON.stringify(sel)})[${i}]; e.scrollIntoView({block: 'nearest'}); const b = e.getBoundingClientRect(); return [b.x + 40, b.y + b.height / 2] })()`);
        await p.s('Input.dispatchMouseEvent', {type: 'mouseMoved', x: r[0], y: r[1]});
        await sleep(60);
      }
      await p.quiet(2000);
      return {rowsSwept: n, requests: p.net.requests, transferredKB: kb(p.net.bytes), byTypeKB: Object.fromEntries(Object.entries(p.net.byType).map(([k, v]) => [k, kb(v)])),
        main: await activity(p)};
    });
  }
}

async function memorySnapshot(b, p) {
  return {jsHeapMB: +((await p.heap()) / 2 ** 20).toFixed(1), processMB: await processMemory(b),
    decodedBitmapsMB: +((await p.ev('__perf.bitmapBytes')) / 2 ** 20).toFixed(1), webglContextsCreated: await p.ev('__perf.webgl')};
}

async function scenarioMemory() {
  results.memory = {};

  log('memory: 20 Elden Ring weapons');
  results.memory.eldenRingTwentyWeapons = await withBrowser(async b => {
    const p = await openPage(b, {cache: true});
    await p.goto(ME + '#c=Greatsword'); await p.until('__perf.firstDraw > 0'); await p.quiet(2000);
    const start = await memorySnapshot(b, p);
    const shown = new Set();
    for (let i = 0; i < 20; i++) { await p.ev(`document.querySelector('#weapons .tile[data-w="${i}"]').click()`); await p.quiet(800); shown.add(await p.ev(`document.querySelector('.v3d-who')?.textContent`)) }
    await sleep(1000);
    return {start, after: await memorySnapshot(b, p), distinctViewerLabels: shown.size,
      modelFilesLoaded: await p.ev(`performance.getEntriesByType('resource').filter(e => e.name.endsWith('.glb')).length`)};
  });

  log('memory: 10 Super Smash Bros. Ultimate clips');
  results.memory.smashTenClips = await withBrowser(async b => {
    const p = await openPage(b, {cache: true});
    await p.goto(ME + '#g=super-smash-bros-ultimate&c=kazuya'); await p.until(`!document.querySelector('#dock').hidden`); await p.quiet(2000); await sleep(1500);
    const start = await memorySnapshot(b, p);
    await p.ev(`document.activeElement && document.activeElement.blur()`);
    for (let i = 0; i < 10; i++) { await p.key('ArrowDown', 'ArrowDown', 40); await p.key('ArrowDown', 'ArrowDown', 40, {type: 'keyUp'}); await p.quiet(800); await sleep(1500) }
    return {start, after: await memorySnapshot(b, p), at: await p.ev('DOCK.key')};
  });

  log('memory: Hollow Knight large sheet');
  results.memory.hollowKnightLargeSheet = await withBrowser(async b => {
    const p = await openPage(b, {cache: true});
    await p.goto(ME + '#g=hollow-knight&c=knight'); await p.until(`!document.querySelector('#dock').hidden`); await p.quiet(2000); await sleep(1000);
    const start = await memorySnapshot(b, p);
    const t0 = Date.now();
    await p.ev(`location.hash = 'g=hollow-knight&c=nkg&m=nkg.attack.firebats'`);
    const shown = await p.until(`DOCK.key === 'nkg|nkg.attack.firebats'`); await p.quiet(2000); await sleep(2000);
    return {start, after: await memorySnapshot(b, p), shown, secondsToSettle: Math.round((Date.now() - t0) / 1000),
      sheets: await p.ev(`performance.getEntriesByType('resource').filter(e => e.name.includes('/sheets/nkg')).map(e => ({file: e.name.split('/').pop(), KB: Math.round(e.encodedBodySize / 1024)}))`)};
  });

  log('memory: five game switches');
  results.memory.fiveGameSwitches = await withBrowser(async b => {
    const p = await openPage(b, {cache: true});
    await p.goto(ME); await p.until('__perf.firstDraw > 0'); await p.quiet(2000);
    const start = await memorySnapshot(b, p);
    const games = ['no-rest-for-the-wicked', 'ninja-gaiden-black', 'devil-may-cry-3', 'elden-ring', 'no-rest-for-the-wicked'];
    for (const g of games) { await p.ev(`location.hash = 'g=${g}'`); await sleep(500); await p.quiet(2000); await sleep(1000) }
    return {games, start, after: await memorySnapshot(b, p), webglWarnings: p.consoleMsgs.filter(m => /webgl/i.test(m))};
  });
}

function scenarioHosting() {
  log('hosting and repository');
  const sh = (cmd, args) => { try { return execFileSync(cmd, args, {encoding: 'utf8'}).trim() } catch (e) { return null } };
  results.repository = Object.fromEntries((sh('git', ['count-objects', '-vH']) || '').split('\n').filter(Boolean).map(l => l.split(': ')));
  results.repository.trackedFiles = (sh('git', ['ls-files']) || '').split('\n').length;
  results.repository.commit = sh('git', ['rev-parse', '--short', 'HEAD']);
  const run = sh('gh', ['run', 'list', '--workflow', 'static.yml', '--branch', 'main', '--status', 'success', '--limit', '1', '--json', 'databaseId,createdAt,displayTitle']);
  if (run) {
    const [r] = JSON.parse(run);
    const art = sh('gh', ['api', `repos/{owner}/{repo}/actions/runs/${r.databaseId}/artifacts`, '--jq', '.artifacts[0].size_in_bytes']);
    const steps = JSON.parse(sh('gh', ['run', 'view', String(r.databaseId), '--json', 'jobs']) || '{"jobs":[]}').jobs.flatMap(j => j.steps)
      .map(s => [s.name, (new Date(s.completedAt) - new Date(s.startedAt)) / 1000]);
    results.pages = {run: r, artifactMB: art && Math.round(art / 2 ** 20), stepSeconds: Object.fromEntries(steps)};
  }
}

// the Pages deployment being measured, read before and after the run: a push to main during the run would mix two
// versions of the site, so the run is flagged
function deployed() {
  try {
    const [r] = JSON.parse(execFileSync('gh', ['run', 'list', '--workflow', 'static.yml', '--branch', 'main', '--limit', '1', '--json', 'databaseId,headSha,status,conclusion,updatedAt'], {encoding: 'utf8'}));
    return r && {run: r.databaseId, commit: r.headSha.slice(0, 7), status: r.status, conclusion: r.conclusion, at: r.updatedAt};
  } catch { return null }
}

const SCENARIOS = {load: scenarioLoad, scroll: scenarioScroll, interact: scenarioInteract, idle: scenarioIdle, hover: scenarioHover, memory: scenarioMemory, hosting: scenarioHosting};
results.site = {before: BASE.includes('github.io') ? deployed() : null};
for (const k of ONLY) {
  try { await SCENARIOS[k]() } catch (e) { log(k, 'failed:', e.message); results[k + 'Error'] = e.message }
}
results.finishedAt = new Date().toISOString();
if (results.site.before) {
  results.site.after = deployed();
  results.site.changedDuringRun = results.site.after?.run !== results.site.before.run || results.site.before.status !== 'completed';
  if (results.site.changedDuringRun) log('WARNING: the site was redeployed during the run; measure again');
}
mkdirSync(path.dirname(OUT), {recursive: true});
writeFileSync(OUT, JSON.stringify(results, null, 2) + '\n');
log('wrote', OUT);

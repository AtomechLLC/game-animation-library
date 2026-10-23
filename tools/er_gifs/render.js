// Renders Elden Ring moves from the Frame Data 3D preview (frame-data/viewer3d.js) to animated WebP for the library.
//   node tools/er_gifs/render.js [out ...]     serves the repo itself on a free port; needs playwright and ffmpeg
// Each job in jobs.json: {out, class, move, weapon?, every?}. Output: gifs/<out>.webp, cropped to the character
// over the whole move (found on a grid-less copy of every frame), square, OUT px.
const http = require('http'), fs = require('fs'), os = require('os'), path = require('path'), {execFileSync} = require('child_process');
const {chromium} = require(process.env.PLAYWRIGHT || 'playwright');
const ROOT = path.resolve(__dirname, '../..'), SIZE = 720, OUT = 360, BG = [0x1d, 0x1f, 0x24];
const types = {'.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.glb': 'model/gltf-binary'};
const server = http.createServer((q, r) => {
  const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end() }
  r.writeHead(200, {'content-type': types[path.extname(p)] || 'application/octet-stream'}); fs.createReadStream(p).pipe(r);
});

// bounding box of pixels that differ from the background, from raw RGB (ffmpeg decodes the PNG)
function bbox(file) {
  const raw = execFileSync('ffmpeg', ['-loglevel', 'error', '-i', file, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], {maxBuffer: 1 << 24});
  let x0 = SIZE, y0 = SIZE, x1 = -1, y1 = -1;
  for (let y = 0; y < SIZE; y++) for (let x = 0; x < SIZE; x++) {
    const i = (y * SIZE + x) * 3;
    if (Math.abs(raw[i] - BG[0]) + Math.abs(raw[i + 1] - BG[1]) + Math.abs(raw[i + 2] - BG[2]) > 24) {
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
  }
  return x1 < 0 ? null : [x0, y0, x1, y1];
}

(async () => {
  await new Promise(r => server.listen(0, r));
  const jobs = JSON.parse(fs.readFileSync(path.join(__dirname, 'jobs.json'), 'utf8'));
  const only = process.argv.slice(2);
  const fd = JSON.parse(fs.readFileSync(path.join(ROOT, 'frame-data/elden-ring.json'), 'utf8'));
  const browser = await chromium.launch({args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  const page = await browser.newPage({viewport: {width: SIZE, height: SIZE}, deviceScaleFactor: 1});
  page.on('console', m => m.type() === 'error' && console.error('page:', m.text()));
  await page.goto(`http://localhost:${server.address().port}/tools/er_gifs/render.html?w=${SIZE}&h=${SIZE}`);
  await page.waitForFunction(() => window.READY, null, {timeout: 120000});
  for (const j of jobs) {
    if (only.length && !only.includes(j.out)) continue;
    const m = fd.moves.find(x => x.class === j.class && x.id === j.move);
    if (!m) { console.error('no move', j.class, j.move); continue }
    const n = await page.evaluate(([m, w]) => ER.show(m, w), [m, j.weapon || null]);
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'er-')), stage = page.locator('.v3d-stage'), every = j.every || 2;
    let k = 0, box = null;
    for (let f = 1; f <= n; f++) {
      if ((f - 1) % every === 0) {
        const name = String(k++).padStart(4, '0');
        await page.evaluate(() => ER.grid(false));
        await stage.screenshot({path: path.join(dir, 'bare.png')});
        const b = bbox(path.join(dir, 'bare.png'));
        if (b) box = box ? [Math.min(box[0], b[0]), Math.min(box[1], b[1]), Math.max(box[2], b[2]), Math.max(box[3], b[3])] : b;
        await page.evaluate(() => ER.grid(true));
        await stage.screenshot({path: path.join(dir, name + '.png')});
      }
      if (f < n) await page.evaluate(() => ER.step());
    }
    // square crop around the union box with a margin, kept inside the frame
    const side = Math.min(SIZE, Math.round(Math.max(box[2] - box[0], box[3] - box[1]) * 1.12));
    const cx = (box[0] + box[2]) / 2, cy = (box[1] + box[3]) / 2;
    const x = Math.round(Math.min(Math.max(cx - side / 2, 0), SIZE - side)), y = Math.round(Math.min(Math.max(cy - side / 2, 0), SIZE - side));
    const out = path.join(ROOT, 'gifs', j.out + '.webp');
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(30 / every), '-i', path.join(dir, '%04d.png'),
      '-vf', `crop=${side}:${side}:${x}:${y},scale=${OUT}:${OUT}:flags=lanczos,eq=gamma=1.25`,
      '-c:v', 'libwebp_anim', '-quality', '70', '-compression_level', '6', '-loop', '0', out]);
    fs.rmSync(dir, {recursive: true});
    console.log(j.out, n, 'frames ->', k, 'crop', side, (fs.statSync(out).size / 1024).toFixed(0) + ' KB');
  }
  await browser.close(); server.close();
})().catch(e => { console.error(e); process.exit(1) });

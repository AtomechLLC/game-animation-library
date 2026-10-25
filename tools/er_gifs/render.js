// Renders Elden Ring animations with Move Explorer's 3D preview (frame-data/viewer3d.js) to animated WebP for the
// library. Needs playwright and ffmpeg; serves the repo itself on a free port.
//   node tools/er_gifs/render.js [out ...]             render jobs.json (or only the named outs) to gifs/<out>.webp
//   node tools/er_gifs/render.js --sheet DIR [id ...]   8-frame contact sheets of common_anims.json ids, to pick ids
//                                                      (GAME=no-rest-for-the-wicked: nrftw_common_anims.json)
// A job: {out, game? (default elden-ring), class, move | moves: [ids played in a row], weapon?, grip? (Offhand holds the weapon left),
// bare? (hide the weapon), every?}. Class "Common" plays the common
// (non-weapon) animations from tools/frame_data/export_er_common.py. Frames are cropped to the character over the
// whole job and scaled to a square of OUT px.
const http = require('http'), fs = require('fs'), os = require('os'), path = require('path'), {execFileSync} = require('child_process');
const {chromium} = require(process.env.PLAYWRIGHT || 'playwright');
const ROOT = path.resolve(__dirname, '../..'), SIZE = 600, OUT = 360, WORKERS = +(process.env.WORKERS || 3);
const types = {'.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.glb': 'model/gltf-binary'};
const server = http.createServer((q, r) => {
  const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end() }
  r.writeHead(200, {'content-type': types[path.extname(p)] || 'application/octet-stream'}); fs.createReadStream(p).pipe(r);
});
const fdata = {}, fdOf = g => fdata[g] ||= JSON.parse(fs.readFileSync(path.join(ROOT, `frame-data/${g}.json`), 'utf8'));
// common (non-weapon) animations have no frame-data row: they play as a bare move of the Common class
const moveOf = (game, cls, id, grip = '1h') => cls === 'Common' ? {id, class: 'Common', grip} : fdOf(game).moves.find(x => x.class === cls && x.id === id);

async function open(browser, game) {
  const page = await browser.newPage({viewport: {width: SIZE, height: SIZE}, deviceScaleFactor: 1});
  page.on('console', m => m.type() === 'error' && console.error('page:', m.text()));
  await page.goto(`http://localhost:${server.address().port}/tools/er_gifs/render.html?w=${SIZE}&h=${SIZE}&game=${game}`);
  await page.waitForFunction(() => window.READY, null, {timeout: 120000});
  return page;
}

// capture frames of each move in turn; returns [files, union screen box]
async function capture(page, game, cls, ids, weapon, pick, dir, grip, bare) {
  const files = [];
  let box = null;
  for (const id of ids) {
    const n = await page.evaluate(([m, w, b]) => ER.show(m, w, b), [moveOf(game, cls, id, grip), weapon || null, !!bare]);
    if (!n) throw new Error('cannot show ' + id);
    for (const f of pick(n)) {
      await page.evaluate(f => ER.seek(f), f);
      const b = await page.evaluate(() => ER.box());
      box = box ? [Math.min(box[0], b[0]), Math.min(box[1], b[1]), Math.max(box[2], b[2]), Math.max(box[3], b[3])] : b;
      const file = path.join(dir, String(files.length).padStart(4, '0') + '.png');
      fs.writeFileSync(file, Buffer.from(await page.evaluate(() => ER.frame()), 'base64')); files.push(file);
    }
  }
  return [files, box];
}

// a square around the box, padded for cloth and armor beyond the bones, kept inside the frame
function crop(box, pad = 1.25) {
  const side = Math.min(SIZE, Math.round(Math.max(box[2] - box[0], box[3] - box[1]) * pad));
  const cx = (box[0] + box[2]) / 2, cy = (box[1] + box[3]) / 2;
  const x = Math.round(Math.min(Math.max(cx - side / 2, 0), SIZE - side)), y = Math.round(Math.min(Math.max(cy - side / 2, 0), SIZE - side));
  return `crop=${side}:${side}:${x}:${y}`;
}

// frames per second of a game's baked animations (Elden Ring 30, No Rest for the Wicked 60)
const fpsOf = g => JSON.parse(fs.readFileSync(path.join(ROOT, `frame-data/models/${g}/models.json`), 'utf8')).fps || 30;

async function renderJob(pageFor, j) {
  const game = j.game || 'elden-ring', page = await pageFor(game), fps = fpsOf(game);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'er-')), every = j.every || fps / 15;
  const [files, b] = await capture(page, game, j.class, j.moves || [j.move], j.weapon, n => Array.from({length: Math.ceil(n / every)}, (_, i) => 1 + i * every), dir, j.grip, j.bare);
  const out = path.join(ROOT, 'gifs', j.out + '.webp');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps / every), '-i', path.join(dir, '%04d.png'),
    '-vf', `${crop(b)},scale=${OUT}:${OUT}:flags=lanczos,eq=gamma=1.25`,
    '-c:v', 'libwebp_anim', '-quality', '70', '-compression_level', '6', '-loop', '0', out]);
  fs.rmSync(dir, {recursive: true});
  console.log(j.out, files.length, 'frames', (fs.statSync(out).size / 1024).toFixed(0) + ' KB');
}

async function renderSheet(pageFor, game, id, label, outDir) {
  const page = await pageFor(game);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'er-'));
  const [files, b] = await capture(page, game, 'Common', [id], null, n => Array.from({length: 8}, (_, i) => 1 + Math.round(i * (n - 1) / 7)), dir);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', path.join(dir, '%04d.png'), '-vf',
    `${crop(b)},scale=200:200,eq=gamma=1.25,tile=8x1,drawtext=text='${id} ${label.replace(/[':\\]/g, '')}':x=4:y=4:fontcolor=yellow:fontsize=14`,
    '-frames:v', '1', path.join(outDir, id + '.png')]);
  fs.rmSync(dir, {recursive: true});
  console.log('sheet', id);
}

(async () => {
  await new Promise(r => server.listen(0, r));
  let tasks;
  if (process.argv[2] === '--sheet') {
    const game = process.env.GAME || 'elden-ring', outDir = process.argv[3], ids = process.argv.slice(4);
    fs.mkdirSync(outDir, {recursive: true});
    const list = JSON.parse(fs.readFileSync(path.join(__dirname, game === 'elden-ring' ? 'common_anims.json' : 'nrftw_common_anims.json'), 'utf8'));
    tasks = list.filter(c => !ids.length || ids.includes(c.id) || ids.includes(c.want)).map(c => p => renderSheet(p, game, c.id, c.label, outDir));
  } else {
    const only = process.argv.slice(2);
    tasks = JSON.parse(fs.readFileSync(path.join(__dirname, 'jobs.json'), 'utf8')).filter(j => !only.length || only.includes(j.out)).map(j => p => renderJob(p, j));
  }
  const browsers = [];
  await Promise.all(Array.from({length: Math.min(WORKERS, tasks.length)}, async () => {
    const b = await chromium.launch({args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
    browsers.push(b);
    const pages = {}, pageFor = async g => pages[g] ||= await open(b, g);   // one page per game, opened when first needed
    for (let t; (t = tasks.shift());) await t(pageFor).catch(e => console.error('failed:', e.message));
  }));
  await Promise.all(browsers.map(b => b.close())); server.close();
})().catch(e => { console.error(e); process.exit(1) });

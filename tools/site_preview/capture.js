// Records the site preview: Action Atlas scrolling through its card grid, as an animated WebP for the README and a
// still of the first frame for link previews (og:image), which LinkedIn and most platforms show without animation.
// Needs Playwright (with Chromium) and ffmpeg built with libwebp. Run from the repo root:
//   node tools/site_preview/capture.js [url]
// Writes shared/preview/site-preview.webp (800px wide) and shared/preview/site-preview.jpg (1200×630).
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');

const URL_ = process.argv[2] || 'https://gameanimationlibrary.com/action-atlas.html';
const OUT = path.join('shared', 'preview');
const FPS = 12, END = 3200; // scroll depth in px: past the first categories' cards

(async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'site-preview-'));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 630 }, colorScheme: 'dark' });
  await p.goto(URL_, { waitUntil: 'networkidle', timeout: 60000 });
  // Load the lazy clips along the way first, so none are blank while recording
  for (let y = 0; y <= END + 630; y += 300) { await p.evaluate(y => scrollTo(0, y), y); await p.waitForTimeout(250); }
  await p.waitForLoadState('networkidle');
  await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(1500);

  let n = 0;
  const frame = async step => {
    const t = Date.now();
    if (step) await step();
    await p.screenshot({ path: path.join(dir, String(n++).padStart(4, '0') + '.png') });
    const d = 1000 / FPS - (Date.now() - t); // keep the clips on the cards at their real speed
    if (d > 0) await p.waitForTimeout(d);
  };
  const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const hold = async s => { for (let i = 0; i < s * FPS; i++) await frame(); };
  const scroll = async (a, z, s) => { const N = s * FPS; for (let i = 1; i <= N; i++) await frame(() => p.evaluate(y => scrollTo(0, y), Math.round(a + (z - a) * ease(i / N)))); };
  await hold(1.5); await scroll(0, END, 5); await hold(1.5); await scroll(END, 0, 1.5);
  await b.close();

  fs.mkdirSync(OUT, { recursive: true });
  const ff = (...a) => execFileSync('ffmpeg', ['-loglevel', 'error', '-y', ...a], { stdio: 'inherit' });
  ff('-framerate', String(FPS), '-i', path.join(dir, '%04d.png'), '-vf', 'fps=10,scale=800:-1:flags=lanczos',
     '-c:v', 'libwebp_anim', '-q:v', '55', '-compression_level', '6', '-loop', '0', '-an', path.join(OUT, 'site-preview.webp'));
  ff('-i', path.join(dir, '0000.png'), '-q:v', '3', path.join(OUT, 'site-preview.jpg'));
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`${n} frames → ${OUT}/site-preview.webp, ${OUT}/site-preview.jpg`);
})();

"""Add Street Fighter III: 3rd Strike hitbox clips from Baston (http://ensabahnur.free.fr/BastonNew/) to library.json.

Baston's hitbox viewer stores every frame of a move as a 384x224 sprite capture plus that frame's boxes. For each
mapped move this downloads the frames (cached in .cache/baston/frames/), draws the character's hurtboxes (blue),
attack boxes (red, projectiles included) and throw boxes (yellow) on them the way Baston does, crops to the
character over the whole move and writes a 60 fps animated WebP at gifs/<id>-baston-<n>.webp (host `Baston`).
Superfreeze frames are kept, so Super Arts show their flash.

Run tools/frame_data/import_baston_sf3.py first (it caches the hitbox pages this reads). Safe to rerun: records
already present (same page_url) are skipped. Needs Pillow and ffmpeg.
"""
import json, os, re, subprocess, tempfile, time, urllib.request
from PIL import Image, ImageDraw
from blocklist import load, blocked

GAME = 'Street Fighter III: 3rd Strike'
CACHE = os.path.join('.cache', 'baston')
SCALE = 2  # sprites are tiny; scale up with nearest neighbour

# animation id -> [(frame data move id, label)]; ids are <character>.<type>.<Baston move> as in
# frame-data/street-fighter-3-third-strike.json
MAP = {
 'fighting.special-move-projectile': [('ryu.special.035', 'Ryu Hadouken (Fierce)'), ('chun-li.special.038', 'Chun-Li Kikkoken (Fierce)')],
 'fighting.rising-uppercut-shoryuken': [('ken.special.043', 'Ken Shoryuken (Fierce)')],
 'fighting.spinning-kick-tatsumaki': [('ken.special.047', 'Ken Tatsumaki Senpuu Kyaku (Roundhouse)')],
 'fighting.super-critical-art': [('ken.super.055', 'Ken Shippu Jinrai Kyaku, Super Art III'), ('chun-li.super.053', 'Chun-Li Houyoku Sen, Super Art II')],
 'fighting.forward-back-dash': [('chun-li.movement.dashForwardFull', 'Chun-Li forward dash'), ('ryu.movement.dashBackwardFull', 'Ryu back dash')],
 'fighting.taunt': [('dudley.normal.027', 'Dudley taunt (rose toss)')],
 'melee.spin-attack': [('chun-li.special.046', 'Chun-Li Spinning Bird Kick (Roundhouse)')],
 'melee.dash-attack-lunge': [('makoto.special.036', 'Makoto Hayate (Fierce)')],
 'melee.charged-attack': [('makoto.special.033', 'Makoto Hayate, fully charged')],
 'melee.overhead-slam': [('elena.special.036', 'Elena Mallet Smash (Fierce)')],
 'melee.punch-combo': [('dudley.special.034', 'Dudley Machine Gun Blow (Fierce)')],
 'melee.kick': [('chun-li.normal.016', 'Chun-Li standing Roundhouse')],
 'defense.dash': [('dudley.movement.dashForwardFull', 'Dudley forward dash')],
 'reactions.get-up-wake-up': [('chun-li.movement.wakeUp', 'Chun-Li wake-up')],
 'reactions.tech-recovery-breakfall': [('ken.movement.wakeUpQuickRoll', 'Ken quick roll on wake-up')],
}
# weaker matches, marked for a second look in gif-screening.json
LOW = {'reactions.tech-recovery-breakfall', 'fighting.taunt'}
TABLE = {'normal': 'fd_normals', 'special': 'fd_specials', 'super': 'fd_supers', 'gjNormal': 'fd_gj_normals',
         'gjSpecial': 'fd_gj_specials', 'movement': 'fd_misc'}
COLORS = {'p_hb': (40, 90, 255), 'v_hb': (40, 170, 255), 'a_hb': (235, 30, 30), 't_hb': (230, 190, 0)}


def get(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'game-animation-library gif import'})
        with urllib.request.urlopen(req, timeout=90) as r: body = r.read()
        open(path, 'wb').write(body)
        time.sleep(0.15)
    return path


def draw(img, fr, who):
    hb = (fr.get(who) or {}).get('hitboxes') or {}
    d = ImageDraw.Draw(img, 'RGBA')
    for key, rgb in COLORS.items():
        for raw, box in zip(hb.get(key, []), hb.get(key + '_to_draw', [])):
            if raw == '0,0,0,0': continue
            x1, x2, y1, y2 = box
            r = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
            d.rectangle(r, fill=rgb + (60,), outline=rgb + (255,))


def render(mid, out):
    fd = {m['id']: m for m in json.load(open('frame-data/street-fighter-3-third-strike.json', encoding='utf-8'))['moves']}[mid]
    slug, mtype, move = mid.split('.')
    ch = int(re.search(r'iChar=(\d+)', fd['url']).group(1))
    page = open(os.path.join(CACHE, 'hb', f'{ch}_{TABLE[mtype]}_{move}.html'), encoding='utf-8', errors='replace').read()
    frames = json.loads(re.search(r'aFramesInfos = (\{.*?\});\n', page).group(1))
    base = re.search(r"sBaseUrl = '([^']+)'", page).group(1)
    imgs = []
    for k in sorted(frames, key=int)[1:-1]:  # frame 0 is the commit frame (some captures are a stale sprite), the last is back in neutral
        fr = frames[k]
        if not fr.get('pngFileName'): continue
        png = get(base + k + '_canvas.png', os.path.join(CACHE, 'frames', f'{ch}_{TABLE[mtype]}_{move}', k + '.png'))
        img = Image.open(png).convert('RGB')
        bg = img.getpixel((0, 0))  # captures use a key colour (magenta or white) for the background
        if bg != (255, 255, 255):
            mask = Image.eval(Image.merge('RGB', [c.point(lambda v, t=t: 255 if v == t else 0) for c, t in zip(img.split(), bg)]).convert('L'), lambda v: 255 if v == 255 else 0)
            img.paste((255, 255, 255), mask=mask)
        draw(img, fr, 'P1')
        for o in fr.get('objects_list', []): draw(img, fr, o)
        imgs.append(img)
    # crop to everything that is not background over the whole move, with a margin
    box = None
    for img in imgs:
        b = Image.eval(img.convert('L'), lambda v: 255 if v < 250 else 0).getbbox()
        if b: box = b if not box else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    W, H = imgs[0].size
    box = (max(0, box[0] - 8), max(0, box[1] - 8), min(W, box[2] + 8), min(H, box[3] + 8))
    with tempfile.TemporaryDirectory() as t:
        for i, img in enumerate(imgs):
            c = img.crop(box)
            c.resize((c.width * SCALE, c.height * SCALE), Image.NEAREST).save(os.path.join(t, '%04d.png' % i))
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', '60', '-i', os.path.join(t, '%04d.png'),
                        '-loop', '0', '-c:v', 'libwebp', '-lossless', '1', '-compression_level', '6', out], check=True)
    return fd['url'], len(imgs)


d = json.load(open('library.json', encoding='utf-8'))
byid = {a['id']: a for a in d['animations']}
bl = load()
scr = json.load(open('gif-screening.json', encoding='utf-8'))
added = []
for aid, moves in MAP.items():
    a = byid[aid]
    a.setdefault('gifs', [])
    have = {g.get('page_url') for g in a['gifs']} | {g.get('page_url') for g in a.get('rejected_gifs', [])}
    n = sum(1 for g in a['gifs'] if g.get('host') == 'Baston')
    for mid, label in moves:
        url = {m['id']: m for m in json.load(open('frame-data/street-fighter-3-third-strike.json', encoding='utf-8'))['moves']}[mid]['url']
        if url in have:
            continue
        local = f'gifs/{aid}-baston-{n}.webp'
        _, count = render(mid, local)
        conf = 'low' if aid in LOW else 'high'
        g = {'page_url': url, 'media_url': url, 'title': f'{label}, with hitboxes', 'game': GAME,
             'host': 'Baston', 'local': local, 'source_url': url,
             'screened': {'verdict': 'added', 'confidence': conf, 'what': f'{label}: sprite frames with hurtboxes and attack boxes'}}
        if blocked(bl, g, open(local, 'rb').read()):
            os.remove(local)
            continue
        a['gifs'].append(g)
        scr['added'].append({'animation': aid, 'clip': local[5:-5], 'game': GAME, 'what': g['screened']['what'], 'confidence': conf})
        added.append((aid, local, count))
        n += 1
json.dump(d, open('library.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
json.dump(scr, open('gif-screening.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
for x in added: print(*x)
print('added', len(added))

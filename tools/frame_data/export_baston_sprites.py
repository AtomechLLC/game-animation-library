"""Exports Baston's per-frame sprites and hitboxes for Move Explorer's 2D preview (frame-data/sprites2d.js).

    python tools/frame_data/import_baston_sf3.py          # first: the frame data and the cached hitbox pages
    python tools/frame_data/export_baston_sprites.py      # ~50,000 frame captures, fetched 6 at a time, cached

Baston's hitbox viewer (http://ensabahnur.free.fr/BastonNew/hitboxesDisplay.php) stores every frame of a move as a
384x224 capture of the character on a key colour, plus that frame's boxes for the character and its projectiles.
This keeps the frames the tab counts (superfreeze, the commit frame and the closing neutral frame dropped, so frame N
here is frame N in the table), crops them to the character over the whole move, keys out the background and packs
them into one lossless WebP sheet per move. Writes frame-data/sprites/street-fighter-3-third-strike/:

- sprites.json: fps, source, box kinds and per character its moves file.
- moves/<character>.json: per move id `sheet`, cell size `w` x `h`, `cols`, and `frames`: one list of boxes per frame,
  each [kind, x1, y1, x2, y2] in cell pixels. Kinds: p hurtbox, v other vulnerability box, a attack box (projectiles
  included), t throw box, ta throwable box, pu pushbox.
- sheets/<move id>.webp: the frames left to right, top to bottom.
"""
import json, os, re, sys, time, urllib.request, concurrent.futures as cf
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, '.cache', 'baston')
OUT = os.path.join(ROOT, 'frame-data', 'sprites', 'street-fighter-3-third-strike')
FD = os.path.join(ROOT, 'frame-data', 'street-fighter-3-third-strike.json')
TABLE = {'normal': 'fd_normals', 'special': 'fd_specials', 'super': 'fd_supers', 'gjNormal': 'fd_gj_normals',
         'gjSpecial': 'fd_gj_specials', 'movement': 'fd_misc'}
KINDS = ['p', 'v', 'a', 't', 'ta', 'pu']
MAXW = 4096


def page(m):
    slug, mtype, move = m['id'].split('.')
    ch = int(re.search(r'iChar=(\d+)', m['url']).group(1))
    path = os.path.join(CACHE, 'hb', f'{ch}_{TABLE[mtype]}_{move}.html')
    if not os.path.exists(path): return None
    s = open(path, encoding='utf-8', errors='replace').read()
    fr = re.search(r'aFramesInfos = (\{.*?\});\n', s)
    if not fr: return None
    frames = json.loads(fr.group(1))
    keys = sorted(frames, key=int)
    kept = [k for k in keys[1:-1] if frames[k]['GLOBAL'].get('superfreeze', '0') == '0' and frames[k].get('pngFileName')]
    return {'dir': f'{ch}_{TABLE[mtype]}_{move}', 'base': re.search(r"sBaseUrl = '([^']+)'", s).group(1), 'frames': frames, 'keys': kept}


def get(url, path):
    if os.path.exists(path): return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'game-animation-library frame-data import'})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r: body = r.read()
            open(path + '.part', 'wb').write(body); os.replace(path + '.part', path)
            return True
        except OSError:
            time.sleep(2 ** i)
    return False


def download(pages):
    jobs = [(p['base'] + k + '_canvas.png', os.path.join(CACHE, 'frames', p['dir'], k + '.png')) for p in pages for k in p['keys']]
    todo = [j for j in jobs if not os.path.exists(j[1])]
    print(f'{len(jobs)} frames, {len(todo)} to fetch', flush=True)
    failed = 0
    with cf.ThreadPoolExecutor(6) as ex:
        for i, ok in enumerate(ex.map(lambda j: get(*j), todo)):
            failed += not ok
            if i % 1000 == 999: print(f'  {i + 1}/{len(todo)}', flush=True)
    print('failed', failed)


def boxes(fr, who):
    hb = (fr.get(who) or {}).get('hitboxes') or {}
    out = []
    for k in KINDS:
        for raw, b in zip(hb.get(k + '_hb', []), hb.get(k + '_hb_to_draw', [])):
            if raw == '0,0,0,0': continue
            x1, x2, y1, y2 = b
            out.append([k, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)])
    return out


def keyed(png):
    img = Image.open(png).convert('RGB')
    bg = img.getpixel((0, 0))
    # alpha 0 where all three channels equal the key colour
    same = [c.point(lambda v, t=t: 255 if v == t else 0) for c, t in zip(img.split(), bg)]
    key = Image.eval(Image.merge('RGB', same).convert('L', (1 / 3, 1 / 3, 1 / 3, 0)), lambda v: 0 if v >= 254 else 255)
    img.putalpha(key)
    return img


def pack(m, p):
    imgs, bx = [], []
    for k in p['keys']:
        png = os.path.join(CACHE, 'frames', p['dir'], k + '.png')
        if not os.path.exists(png): return None
        imgs.append(keyed(png))
        fr = p['frames'][k]
        bx.append(boxes(fr, 'P1') + [b for o in fr.get('objects_list', []) for b in boxes(fr, o)])
    if not imgs: return None
    W, H = imgs[0].size
    box = None
    for img, bs in zip(imgs, bx):
        b = img.getbbox()
        for _, x1, y1, x2, y2 in bs: b = (min(b[0], x1), min(b[1], y1), max(b[2], x2 + 1), max(b[3], y2 + 1)) if b else (x1, y1, x2 + 1, y2 + 1)
        if b: box = b if not box else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    box = (max(0, box[0] - 4), max(0, box[1] - 4), min(W, box[2] + 4), min(H, box[3] + 4))
    w, h = box[2] - box[0], box[3] - box[1]
    cols = max(1, min(len(imgs), MAXW // w))
    rows = -(-len(imgs) // cols)
    sheet = Image.new('RGBA', (cols * w, rows * h), (0, 0, 0, 0))
    for i, img in enumerate(imgs): sheet.paste(img.crop(box), ((i % cols) * w, (i // cols) * h))
    name = m['id'] + '.webp'
    sheet.save(os.path.join(OUT, 'sheets', name), 'WEBP', lossless=True, method=6)
    rel = [[[k, x1 - box[0], y1 - box[1], x2 - box[0], y2 - box[1]] for k, x1, y1, x2, y2 in bs] for bs in bx]
    return {'sheet': 'sheets/' + name, 'w': w, 'h': h, 'cols': cols, 'frames': rel}


def main():
    d = json.load(open(FD, encoding='utf-8'))
    only = set(sys.argv[1:])
    moves = [m for m in d['moves'] if not only or m['id'] in only or m['class'] in only]
    pages = {m['id']: page(m) for m in moves}
    download([p for p in pages.values() if p])
    os.makedirs(os.path.join(OUT, 'sheets'), exist_ok=True); os.makedirs(os.path.join(OUT, 'moves'), exist_ok=True)
    by = {}
    for m in moves:
        p = pages[m['id']]
        r = p and pack(m, p)
        if r: by.setdefault(m['class'], {})[m['id']] = r
    for c, mv in by.items():
        path = os.path.join(OUT, 'moves', c + '.json')
        old = json.load(open(path)) if only and os.path.exists(path) else {'moves': {}}
        old['moves'].update(mv)
        json.dump(old, open(path, 'w'), separators=(',', ':'))
    man = {'fps': 60, 'kinds': {'p': 'Hurtbox', 'v': 'Other vulnerability', 'a': 'Attack', 't': 'Throw', 'ta': 'Throwable', 'pu': 'Pushbox'},
           'source': {'name': 'Baston', 'url': 'http://ensabahnur.free.fr/BastonNew/', 'author': 'ensabahnur'},
           'classes': {c['id']: {'file': f'moves/{c["id"]}.json'} for c in d['classes'] if os.path.exists(os.path.join(OUT, 'moves', c['id'] + '.json'))}}
    json.dump(man, open(os.path.join(OUT, 'sprites.json'), 'w'), indent=1)
    n = sum(len(v) for v in by.values())
    size = sum(os.path.getsize(os.path.join(OUT, 'sheets', f)) for f in os.listdir(os.path.join(OUT, 'sheets')))
    print(f'packed {n}/{len(moves)} moves, sheets {size // 1024 // 1024} MB')


if __name__ == '__main__':
    main()

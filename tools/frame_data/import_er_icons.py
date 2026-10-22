"""Downloads Elden Ring weapon and shield icons for the frame data page into frame-data/icons/elden-ring/.

    python tools/frame_data/import_er_icons.py

Run after import_er_nyasu.py (it reads the cached armaments list). Icons are the game's own inventory icons, taken from
the Elden Ring wiki on wiki.gg ("ER Icon Weapon <name>.png"), with the Elden Ring Fan API (https://eldenring.fanapis.com)
as a fallback. Each is saved as a 96px WebP; frame-data/icons/elden-ring/index.json maps weapon name to file and source.
Weapons without an icon fall back to a lettered tile on the page.
"""
import io, json, os, re, urllib.parse, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'frame-data', 'icons', 'elden-ring')
ARMS = os.path.join(ROOT, '.cache', 'er-nyasu', '1.17', 'armaments.json')
WIKI = 'https://eldenring.wiki.gg/api.php'
FAN = 'https://eldenring.fanapis.com/api'
PATTERNS = ['ER Icon Weapon {}.png', 'ER Icon weapon {}.png', 'ER Icon Shield {}.png', 'ER Icon shield {}.png']

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'game-animation-library frame-data import'})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()

def slug(name): return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
def norm(name): return re.sub(r'[^a-z0-9]', '', name.lower())

def wiki_urls(names):
    found = {}
    for pat in PATTERNS:
        todo = [n for n in names if n not in found]
        for i in range(0, len(todo), 50):
            want = {('File:' + pat.format(n)): n for n in todo[i:i + 50]}
            q = urllib.parse.urlencode({'action': 'query', 'prop': 'imageinfo', 'iiprop': 'url', 'iiurlwidth': 96, 'titles': '|'.join(want), 'format': 'json'})
            d = json.loads(get(f'{WIKI}?{q}'))['query']
            back = {x['to']: x['from'] for x in d.get('normalized', [])}
            for p in d['pages'].values():
                if 'imageinfo' in p:
                    n = want[back.get(p['title'], p['title'])]
                    found[n] = (p['imageinfo'][0].get('thumburl') or p['imageinfo'][0]['url'], p['imageinfo'][0]['descriptionurl'])
    return found

def fan_urls():
    found = {}
    for kind in ('weapons', 'shields'):
        page = 0
        while True:
            items = json.loads(get(f'{FAN}/{kind}?limit=100&page={page}'))['data']
            if not items: break
            for it in items:
                if it.get('image'): found[norm(it['name'])] = (it['image'], f"{FAN}/{kind}/{it['id']}")
            page += 1
    return found

def main():
    names = sorted({w['name'] for w in json.load(open(ARMS, encoding='utf-8')).values()})
    os.makedirs(OUT, exist_ok=True)
    wiki, fan = wiki_urls(names), None
    index = {}
    for n in names:
        src = wiki.get(n)
        if not src:
            fan = fan if fan is not None else fan_urls()
            src = fan.get(norm(n))
        if not src: continue
        fn = slug(n) + '.webp'
        path = os.path.join(OUT, fn)
        if not os.path.exists(path):
            try:
                im = Image.open(io.BytesIO(get(src[0]))).convert('RGBA')
            except Exception as e:
                print('skip', n, e); continue
            im.thumbnail((96, 96))
            im.save(path, 'WEBP', quality=82, method=6)
        index[n] = {'file': fn, 'source': src[1]}
    with open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump({'sources': [{'name': 'Elden Ring Wiki (wiki.gg)', 'url': 'https://eldenring.wiki.gg'},
                               {'name': 'Elden Ring Fan API', 'url': 'https://eldenring.fanapis.com'}],
                   'note': 'Icons are the game\'s inventory art, (c) FromSoftware / Bandai Namco.',
                   'icons': index}, f, ensure_ascii=False, indent=1)
    print(len(index), 'of', len(names), 'icons; missing:', [n for n in names if n not in index])

if __name__ == '__main__':
    main()

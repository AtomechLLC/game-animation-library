"""Builds frame-data/elden-ring.json from the Elden Ring Frame Data Explorer (https://er-frame-data.nyasu.business).

    python tools/frame_data/import_er_nyasu.py            # patch 1.17, cached downloads in .cache/er-nyasu/
    python tools/frame_data/import_er_nyasu.py 1.14.1     # another patch the explorer publishes

The explorer is by Emilia (sovietspaceship), built from the game's TAE events and params. This script only reshapes
its published JSON into the site's game-agnostic frame data format (see frame-data/README.md). import_er_game.py
reads the game files directly and writes the same format.
"""
import json, os, re, sys, urllib.request, datetime
from er_common import CLASS_FAMILY, build as wrap, grip, move_type

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = 'https://er-frame-data.nyasu.business'
VERSION = sys.argv[1] if len(sys.argv) > 1 else '1.17'
CACHE = os.path.join(ROOT, '.cache', 'er-nyasu', VERSION)
OUT = os.path.join(ROOT, 'frame-data', 'elden-ring.json')

def fetch(name):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        req = urllib.request.Request(f'{BASE}/generated/{VERSION}/{name}', headers={'User-Agent': 'game-animation-library frame-data import'})
        with urllib.request.urlopen(req) as r, open(path, 'wb') as f: f.write(r.read())
    return json.load(open(path, encoding='utf-8'))

def start(c, *types):
    s = [c[t] for t in types if t in c]
    return min(s) if s else None

def build():
    anims, attacks, arms = fetch('animations.json'), fetch('attacks.json'), fetch('armaments.json')
    weapons_by_class = {}
    for w in arms.values():
        weapons_by_class.setdefault(w['category'], []).append(w['name'])
    moves, seen = [], set()
    for key, a in anims.items():
        ev = a.get('events', {})
        af = [e for e in ev.get('activeFrames', []) if e.get('type') == 'Attack']
        if 'Attack' not in a['labels'] or not af or re.match(r'^a\d{3}_', a['name']): continue
        mt = move_type(a['name'])
        if not mt: continue
        for cls in a['categories']:
            if cls not in CLASS_FAMILY: continue
            mid = f"{cls}|{key}"
            if mid in seen: continue
            seen.add(mid)
            # Explorer frames are 0-based TAE frames at 30 fps; the site shows 1-based frames like the explorer does.
            active = sorted([e['range'][0], e['range'][1]] for e in af)
            c = {}
            for x in ev.get('cancels', []):
                r = x.get('range', {}).get('Regular')
                if r and r[0] < 1000: c[x['type']] = r[0]
            ends = [x['range']['Regular'][1] for x in ev.get('cancels', []) if x.get('range', {}).get('Regular') and x['range']['Regular'][1] < 1000]
            last = max(e[1] for e in active)
            dodge = c.get('Dodge')
            atk = (attacks.get((a.get('attacks') or [None])[0]) or {})
            users = sorted({u['name'] for u in a.get('users', []) if u.get('type') == 'Weapon'})
            m = {
                'id': key, 'class': cls, 'type': mt, 'grip': grip(a['name']), 'name': a['name'],
                'startup': active[0][0] + 1,
                'active': [[s + 1, e] for s, e in active],
                'activeFrames': sum(e - s for s, e in active),
                'hits': len(active),
                'recovery': dodge - last if dodge is not None else None,
                'total': max(ends) if ends else None,
                'cancels': {k: v + 1 for k, v in {
                    'attack': start(c, 'LightAttackOnly', 'HeavyAttackOnly', 'RightAttack'),
                    'dodge': dodge, 'block': c.get('Block'), 'skill': start(c, 'FastWeaponArt', 'WeaponArt'),
                    'item': start(c, 'FastGoods', 'Goods'), 'move': c.get('Move')}.items() if v is not None},
                'armor': [[r['range'][0] + 1, r['range'][1]] for r in ev.get('hyperArmour', [])],
                'iframes': [[s + 1, e] for s, e in ev.get('iframes', [])],
                'parryable': 'Parriable' in a['labels'],
                'damage': {k: v for k, v in {
                    'type': atk.get('physAttribute'), 'mv': atk.get('physicalDamageMV'),
                    'poise': atk.get('poiseDamageFlat'), 'level': atk.get('damageLevel'),
                    'stamina': atk.get('staminaCost')}.items() if v not in (None, '')},
                'weapons': users,
            }
            moves.append(m)
    return wrap(moves, weapons_by_class,
        {'id': 'elden-ring', 'name': 'Elden Ring', 'fps': 30, 'version': VERSION,
         'frameNote': 'Frames are animation (TAE) frames at 30 fps, 1-based: startup is the first frame the hitbox is out.'},
        {'name': 'Elden Ring Frame Data Explorer', 'url': BASE, 'moveUrl': BASE + '/?animation={id}', 'author': 'Emilia (sovietspaceship)',
         'retrieved': datetime.date.today().isoformat(), 'method': 'import_er_nyasu.py',
         'note': 'Data extracted from the game by the explorer and reshaped here. Support the original author: https://ko-fi.com/sovietspaceship'})

if __name__ == '__main__':
    data = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print('wrote', OUT, len(data['classes']), 'classes', len(data['moves']), 'moves')

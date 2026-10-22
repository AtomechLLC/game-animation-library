"""Builds frame-data/elden-ring.json from the Elden Ring Frame Data Explorer (https://er-frame-data.nyasu.business).

    python tools/frame_data/import_er_nyasu.py            # patch 1.17, cached downloads in .cache/er-nyasu/
    python tools/frame_data/import_er_nyasu.py 1.14.1     # another patch the explorer publishes

The explorer is by Emilia (sovietspaceship), built from the game's TAE events and params. This script only reshapes
its published JSON into the site's game-agnostic frame data format (see frame-data/README.md). A later importer that
reads the game files directly only has to write the same format.
"""
import json, os, re, sys, urllib.request, datetime

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

# Weapon families for the class list (sidebar groups), in display order.
FAMILIES = [
    ('blades', 'Swords & daggers', ['Dagger', 'Throwing Blade', 'Straight Sword', 'Light Greatsword', 'Greatsword', 'Colossal Sword', 'Curved Sword', 'Curved Greatsword', 'Backhand Blade', 'Katana', 'Great Katana', 'Twinblade']),
    ('thrust', 'Thrusting', ['Thrusting Sword', 'Heavy Thrusting Sword', 'Spear', 'Great Spear', 'Halberd', 'Reaper']),
    ('blunt', 'Axes & hammers', ['Axe', 'Greataxe', 'Hammer', 'Great Hammer', 'Flail', 'Colossal Weapon']),
    ('unarmed', 'Fists & claws', ['Fist', 'Hand-to-Hand', 'Claw', 'Beast Claw']),
    ('flexible', 'Whips, tools & throwables', ['Whip', 'Torch', 'Perfume Bottle', 'Throwing Weapon']),
    ('ranged', 'Bows & crossbows', ['Light Bow', 'Bow', 'Greatbow', 'Crossbow', 'Ballista']),
    ('shields', 'Shields', ['Small Shield', 'Medium Shield', 'Greatshield', 'Thrusting Shield']),
]
# The weapon whose icon stands for each class in the visual index: a well-known pick players recognise.
ICONIC = {
    'Dagger': ['Black Knife'], 'Throwing Blade': ['Smithscript Dagger'], 'Straight Sword': ['Longsword'],
    'Light Greatsword': ['Milady'], 'Greatsword': ['Claymore'], 'Colossal Sword': ['Greatsword'],
    'Curved Sword': ['Scimitar', 'Shamshir'], 'Curved Greatsword': ["Bloodhound's Fang"], 'Backhand Blade': ['Backhand Blade'],
    'Katana': ['Moonveil', 'Uchigatana'], 'Great Katana': ["Rakshasa's Great Katana"], 'Twinblade': ['Godskin Peeler'],
    'Thrusting Sword': ["Rogier's Rapier"], 'Heavy Thrusting Sword': ['Great Epee'], 'Spear': ['Bolt of Gransax'],
    'Great Spear': ["Siluria's Tree"], 'Halberd': ['Golden Halberd'], 'Reaper': ['Winged Scythe'], 'Axe': ['Battle Axe'],
    'Greataxe': ['Rusted Anchor'], 'Hammer': ['Morning Star'], 'Great Hammer': ['Brick Hammer'], 'Flail': ['Nightrider Flail'],
    'Colossal Weapon': ['Giant-Crusher'], 'Fist': ['Caestus'], 'Hand-to-Hand': ['Dryleaf Arts'], 'Claw': ['Bloodhound Claws'],
    'Beast Claw': ['Beast Claw'], 'Whip': ["Hoslow's Petal Whip"], 'Torch': ['Torch'], 'Perfume Bottle': ['Firespark Perfume Bottle'],
    'Throwing Weapon': ['Smithscript Dagger'], 'Light Bow': ['Shortbow'], 'Bow': ['Longbow'], 'Greatbow': ['Golem Greatbow'],
    'Crossbow': ['Pulley Crossbow'], 'Ballista': ['Hand Ballista'], 'Small Shield': ['Buckler'], 'Medium Shield': ['Heater Shield', 'Brass Shield'],
    'Greatshield': ['Fingerprint Stone Shield'], 'Thrusting Shield': ['Dueling Shield'],
}
CLASS_FAMILY = {c: fid for fid, _, cs in FAMILIES for c in cs}

# Move types, in the order a player meets them. Matched against the explorer's animation names.
MOVE_TYPES = [
    ('light', 'Light chain', 'R1 / L1 combo strings'),
    ('heavy', 'Heavy', 'R2 strikes, uncharged and charged'),
    ('feint', 'Heavy feint', 'Charged R2 cancelled into a feint'),
    ('running', 'Running', 'Attacks out of a sprint'),
    ('rolling', 'Rolling', 'Attacks out of a roll'),
    ('backstep', 'Backstep', 'Attacks out of a backstep'),
    ('crouch', 'Crouch', 'Attacks from crouch or sneak'),
    ('jumping', 'Jumping', 'Jump attacks, airborne and landing'),
    ('guard-counter', 'Guard counter', 'Counter after blocking a hit'),
    ('critical', 'Criticals', 'Backstabs and ripostes'),
    ('parry', 'Parry', 'Parries and parry-like skills'),
    ('shieldpoke', 'Shield poke', 'Thrusting-shield attacks from guard'),
    ('buffed', 'Skill-buffed heavy', 'R2 variants while War Cry or Barbaric Roar is active'),
    ('mounted', 'Mounted', 'Attacks on Torrent'),
]

def move_type(name):
    n = name
    if n.startswith('Mounted'): return 'mounted'
    if 'War Cry' in n or 'Barbaric Roar' in n or 'Buffed' in n: return 'buffed'
    if 'Feint' in n: return 'feint'
    if 'Guard Counter' in n: return 'guard-counter'
    if n.startswith(('Backstab', 'Riposte')) or 'Riposte' in n: return 'critical'
    if 'Parry' in n: return 'parry'
    if 'Shieldpoke' in n: return 'shieldpoke'
    if 'Running' in n: return 'running'
    if 'Rolling' in n: return 'rolling'
    if 'Backstep' in n: return 'backstep'
    if 'Crouch' in n: return 'crouch'
    if 'Jumping' in n or 'Landing' in n: return 'jumping'
    if re.search(r'\bR2\b', n): return 'heavy'
    if re.search(r'\b[RL]1\b', n): return 'light'
    return None

def grip(name):
    for g, label in (('1h', 'One-handed'), ('2h', 'Two-handed'), ('Paired', 'Powerstance'), ('Offhand', 'Off-hand'), ('Mounted', 'Mounted')):
        if name.startswith(g): return g
    return 'any'

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
    # A class's default moveset is its most-used animation section; weapons with their own animations list them.
    classes = []
    for fid, _, names in FAMILIES:
        for cls in names:
            cm = [m for m in moves if m['class'] == cls]
            if not cm: continue
            secs = {}
            for m in cm: secs[m['id'].split('_')[0]] = secs.get(m['id'].split('_')[0], 0) + 1
            base = max(secs, key=secs.get)
            ws = sorted(weapons_by_class.get(cls, []))
            pos = {w: i for i, w in enumerate(ws)}
            for m in cm:
                m['default'] = m['id'].startswith(base + '_')
                # Indexes into the class's weapon list; empty means the class's default moveset only
                m['weapons'] = [pos[w] for w in m['weapons'] if w in pos]
            icon = next((w for w in ICONIC.get(cls, []) if w in pos), ws[0] if ws else (ICONIC.get(cls) or [None])[0])
            classes.append({'id': cls, 'name': cls, 'family': fid, 'icon': icon, 'weapons': ws, 'moves': len(cm)})
    order = {t[0]: i for i, t in enumerate(MOVE_TYPES)}
    corder = {c['id']: i for i, c in enumerate(classes)}
    moves.sort(key=lambda m: (corder[m['class']], order[m['type']], m['grip'], m['name'], m['id']))
    return {
        'schema': 'frame-data/1',
        'game': {'id': 'elden-ring', 'name': 'Elden Ring', 'fps': 30, 'version': VERSION,
                 'frameNote': 'Frames are animation (TAE) frames at 30 fps, 1-based: startup is the first frame the hitbox is out.'},
        'source': {'name': 'Elden Ring Frame Data Explorer', 'url': BASE, 'moveUrl': BASE + '/?animation={id}', 'author': 'Emilia (sovietspaceship)',
                   'retrieved': datetime.date.today().isoformat(), 'method': 'import_er_nyasu.py',
                   'note': 'Data extracted from the game by the explorer and reshaped here. Support the original author: https://ko-fi.com/sovietspaceship'},
        'families': [{'id': f, 'name': n} for f, n, _ in FAMILIES],
        'classes': classes,
        'moveTypes': [{'id': i, 'name': n, 'description': d} for i, n, d in MOVE_TYPES],
        'grips': [{'id': '1h', 'name': 'One-handed'}, {'id': '2h', 'name': 'Two-handed'}, {'id': 'Paired', 'name': 'Powerstance'},
                  {'id': 'Offhand', 'name': 'Off-hand'}, {'id': 'Mounted', 'name': 'Mounted'}, {'id': 'any', 'name': 'Other'}],
        'moves': moves,
    }

if __name__ == '__main__':
    data = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print('wrote', OUT, len(data['classes']), 'classes', len(data['moves']), 'moves')

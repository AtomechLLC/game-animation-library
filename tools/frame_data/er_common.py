"""Elden Ring pieces shared by the frame data importers: weapon families, move types, and the frame-data/1 envelope."""
import re

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

# Move types, in the order a player meets them. Matched against the move names.
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
GRIPS = [{'id': '1h', 'name': 'One-handed'}, {'id': '2h', 'name': 'Two-handed'}, {'id': 'Paired', 'name': 'Powerstance'},
         {'id': 'Offhand', 'name': 'Off-hand'}, {'id': 'Mounted', 'name': 'Mounted'}, {'id': 'any', 'name': 'Other'}]

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
    for g in ('1h', '2h', 'Paired', 'Offhand', 'Mounted'):
        if name.startswith(g): return g
    return 'any'

def build(moves, weapons_by_class, game, source):
    """Wraps moves (with 'weapons' as weapon names) in the frame-data/1 envelope: classes, default movesets, order."""
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
    moves = [m for m in moves if m['class'] in corder]
    moves.sort(key=lambda m: (corder[m['class']], order[m['type']], m['grip'], m['name'], m['id']))
    return {
        'schema': 'frame-data/1', 'game': game, 'source': source,
        'families': [{'id': f, 'name': n} for f, n, _ in FAMILIES],
        'classes': classes,
        'moveTypes': [{'id': i, 'name': n, 'description': d} for i, n, d in MOVE_TYPES],
        'grips': GRIPS,
        'moves': moves,
    }

"""No Rest for the Wicked's "Gathering" class in Move Explorer: mining, woodcutting, fishing, digging, harvesting, looting
and farming. The clips are the entries of tools/er_gifs/nrftw_common_anims.json that have a "type"; each entry's "tool"
is the model it previews with.

export_nrftw_common.py bakes them and writes moves/gathering.json. merge() then adds the class to
frame-data/no-rest-for-the-wicked.json, and import_nrftw_game.py calls it too, so a rebuild keeps the class.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIST = os.path.join(ROOT, 'tools', 'er_gifs', 'nrftw_common_anims.json')
MOVES = os.path.join(ROOT, 'frame-data', 'models', 'no-rest-for-the-wicked', 'moves', 'gathering.json')
CLASS = 'gathering'
BARE_HANDS = 'Bare hands'
TOOL_ROOT = 'Assets/quantumAssetDatabase/entities/items/tools/'
# Tool name -> its assets under TOOL_ROOT: the lowest tier, except the pickaxe (the copper one's icon is in a bundle the
# game doesn't ship). The hoe and the watering can have view prefabs but no item in this build, so they have no icon.
TOOLS = {
    'Iron Pickaxe': 'pickaxes/ironPickaxe',
    "Copper Woodcutter's Axe": 'woodcuttersAxes/copperWoodcuttersAxe',
    'Pine Fishing Rod': 'fishingRods/pineFishingRod',
    'Copper Shovel': 'shovels/copperShovel',
    'Pine Hoe': 'hoes/pineHoe',
    'Copper Watering Can': 'wateringCans/copperWateringCan',
}
TYPES = [
    ('mining', 'Mining', 'Pickaxe strikes on an ore vein'),
    ('woodcutting', 'Woodcutting', 'Axe strikes on a tree or log'),
    ('fishing', 'Fishing', 'The rod, from cast to catch'),
    ('digging', 'Digging', 'Shovel work at a dig spot'),
    ('harvesting', 'Harvesting', 'Crops, herbs and items picked up by hand'),
    ('looting', 'Looting', 'Opening chests and taking what is inside'),
    ('farming', 'Farming', 'Tilling and watering'),
]
GRIPS = [{'id': 'tool', 'name': 'Tool', 'short': 'Tool'}, {'id': 'bare', 'name': 'Bare hands', 'short': 'Hands'}]

def entries():
    return [w for w in json.load(open(LIST, encoding='utf-8')) if w.get('type')]

def merge(data):
    """Puts the Gathering class in the frame data, replacing any earlier copy. These clips have no hitboxes, so a move
    has only its total
    (and parryable stays true so the "Can't be parried" count keeps to attacks). Returns the number of moves; 0 (and no
    class) until export_nrftw_common.py has baked them."""
    data['moves'] = [m for m in data['moves'] if m['class'] != CLASS]
    data['classes'] = [c for c in data['classes'] if c['id'] != CLASS]
    data['families'] = [f for f in data['families'] if f['id'] != CLASS]
    types = {t[0] for t in TYPES}
    data['moveTypes'] = [t for t in data['moveTypes'] if t['id'] not in types]
    data['grips'] = [g for g in data['grips'] if g['id'] not in {x['id'] for x in GRIPS}]
    if not os.path.exists(MOVES): return 0
    baked = json.load(open(MOVES, encoding='utf-8'))['moves']
    weapons = list(TOOLS)
    moves = []
    for w in entries():
        mv = baked.get(w['id'])
        if mv is None: continue
        tool = w['tool']
        moves.append({'id': w['id'], 'class': CLASS, 'type': w['type'], 'grip': 'bare' if tool == BARE_HANDS else 'tool',
                      'name': w['label'], 'startup': None, 'active': [], 'activeFrames': None, 'hits': 0, 'recovery': None,
                      'total': mv['frames'], 'cancels': {}, 'armor': [], 'iframes': [], 'parryable': True, 'damage': {},
                      'anim': [], 'weapons': [weapons.index(tool)] if tool in weapons else [], 'default': True,
                      'action': w['id'].split('-', 1)[1]})
    if not moves: return 0
    data['families'].append({'id': CLASS, 'name': 'Gathering'})
    data['classes'].append({'id': CLASS, 'name': 'Gathering', 'family': CLASS, 'icon': weapons[0], 'weapons': weapons,
                            'moves': len(moves)})
    data['moveTypes'].extend({'id': i, 'name': n, 'description': d} for i, n, d in TYPES)
    data['grips'].extend(GRIPS)
    data['moves'].extend(moves)
    return len(moves)

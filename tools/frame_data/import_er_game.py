"""Builds frame-data/elden-ring.json straight from an Elden Ring install, in the same format as import_er_nyasu.py.

    python tools/frame_data/import_er_game.py "D:/SteamLibrary/steamapps/common/ELDEN RING"
    python tools/frame_data/import_er_game.py <game folder> --out frame-data/elden-ring-game.json

Reads only; nothing in the game folder is written. Needs Windows (the game's Oodle DLL decompresses its archives),
Python 3.14+ (zstd) and the `cryptography` package. Community reference data is downloaded once into .cache/er-game/:
param layouts from Paramdex and the archive header keys from UXM Selective Unpack.

Where the numbers come from:
    regulation.bin          EquipParamWeapon (class, moveset sections, behavior variation), BehaviorParam_PC (stamina,
                            attack link), AtkParam_Pc (motion value, damage level, physical type)
    Data*.bdt  c0000.anibnd  one TAE per moveset section: hitboxes (event 1), cancel windows (event 300 for the regular
                            equip load, else jump table event 0), get-parried window (jump table 5), hyper armor (791/795),
                            playback speed changes (608) that shift every later frame
    Data*.bdt  item msgbnd  English weapon names
Move names follow the anim id conventions the Frame Data Explorer uses (MOVE_NAMES).
"""
import datetime, json, os, re, struct, sys, urllib.request
from er_common import CLASS_FAMILY, build as wrap, grip, move_type
import er_files as F

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, '.cache', 'er-game')
REFS = {
    'AtkParam.xml': 'https://raw.githubusercontent.com/soulsmods/Paramdex/master/ER/Defs/AtkParam.xml',
    'BehaviorParam.xml': 'https://raw.githubusercontent.com/soulsmods/Paramdex/master/ER/Defs/BehaviorParam.xml',
    'EquipParamWeapon.xml': 'https://raw.githubusercontent.com/soulsmods/Paramdex/master/ER/Defs/EquipParamWeapon.xml',
    'ArchiveKeys.cs': 'https://raw.githubusercontent.com/Nordgaren/UXM-Selective-Unpack/master/UXM/ArchiveKeys.cs',
}
ARCHIVES = ['Data0', 'Data1', 'Data2', 'Data3', 'DLC']
SELF_URL = 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_er_game.py'
EXPLORER = 'https://er-frame-data.nyasu.business'
FPS = 30

# EquipParamWeapon.wepType -> class
CLASSES = {
    1: 'Dagger', 3: 'Straight Sword', 5: 'Greatsword', 7: 'Colossal Sword', 9: 'Curved Sword', 11: 'Curved Greatsword',
    13: 'Katana', 14: 'Twinblade', 15: 'Thrusting Sword', 16: 'Heavy Thrusting Sword', 17: 'Axe', 19: 'Greataxe',
    21: 'Hammer', 23: 'Great Hammer', 24: 'Flail', 25: 'Spear', 28: 'Great Spear', 29: 'Halberd', 31: 'Reaper',
    35: 'Fist', 37: 'Claw', 39: 'Whip', 41: 'Colossal Weapon', 50: 'Light Bow', 51: 'Bow', 53: 'Greatbow',
    55: 'Crossbow', 56: 'Ballista', 65: 'Small Shield', 67: 'Medium Shield', 69: 'Greatshield', 87: 'Torch',
    88: 'Hand-to-Hand', 89: 'Perfume Bottle', 90: 'Thrusting Shield', 91: 'Throwing Blade', 92: 'Backhand Blade',
    93: 'Light Greatsword', 94: 'Great Katana', 95: 'Beast Claw',
}
# AtkParam.atkAttribute -> physical damage type; 253/252 take the weapon's first/second type
PHYS = {0: 'Slash', 1: 'Strike', 2: 'Pierce', 3: 'Standard'}

# Jump table ids that open each cancel window
CANCELS = {
    'attack': (115, 116, 4),  # light-only, heavy-only, any right-hand attack: the earliest counts
    'dodge': (26,), 'block': (22,), 'skill': (103, 104), 'item': (107, 31), 'move': (11,),
}
# Every cancel window the game opens (adds left-hand attack, weapon switch and magic); the last jump table window
# closing is the total
CANCEL_IDS = {j for js in CANCELS.values() for j in js} | {16, 32, 29}

MOVE_NAMES = {
    '030000': '1h R1 1', '030010': '1h R1 2', '030020': '1h R1 3', '030030': '1h R1 4', '030040': '1h R1 5',
    '030050': '1h R1 6', '030200': '1h Running R1', '030210': '1h Running R2', '030300': '1h Rolling R1',
    '030310': '1h Crouch R1', '030400': '1h Backstep R1', '030500': '1h Charged R2 1', '030505': '1h R2 1 Release',
    '030510': '1h Charged R2 2', '030515': '1h R2 2 Release', '030600': '1h Barbaric Roar R2 1 Charged',
    '030605': '1h Barbaric Roar R2 1 Release', '030610': '1h Barbaric Roar R2 2 Charged',
    '030615': '1h Barbaric Roar R2 2 Release', '030620': '1h War Cry R2 1 Charged',
    '030625': '1h War Cry R2 1 Release', '030630': '1h War Cry R2 2 Charged', '030635': '1h War Cry R2 2 Release',
    '030700': '1h Guard Counter', '030900': 'Shieldpoke', '030901': 'Shieldpoke (Greatshield)',
    '030902': 'Shieldpoke (Weapon)', '030903': 'Shieldpoke (Torch)', '030950': '1h Charged R2 1 Feint',
    '030955': '1h Charged R2 2 Feint', '031030': '1h Jumping R1', '031060': '1h Jumping R1 Hangtime',
    '031070': '1h Jumping R1 Landing', '031071': '1h Attack Landing Light', '031072': '1h Attack Landing Medium',
    '031081': '1h Attack Landing Recovery', '031082': '1h Attack Landing Heavy', '031230': '1h Jumping R2',
    '031260': '1h Jumping R2 Hangtime', '031270': '1h Jumping R2 Landing', '031700': 'Riposte', '031710': 'Backstab',
    '031719': 'Backstab Whiff', '031720': 'Backstab (Ground Stab, PvE)', '031730': 'Backstab (Ground Stab, PvE)',
    '031750': '1h Weak-Point Riposte', '032000': '2h R1 1', '032010': '2h R1 2', '032020': '2h R1 3',
    '032030': '2h R1 4', '032040': '2h R1 5', '032050': '2h R1 6', '032200': '2h Running R1',
    '032210': '2h Running R2', '032300': '2h Rolling R1', '032310': '2h Crouch R1', '032400': '2h Backstep R1',
    '032500': '2h Charged R2 1', '032505': '2h R2 1 Release', '032510': '2h Charged R2 2',
    '032515': '2h R2 2 Release', '032600': '2h Barbaric Roar R2 1 Charged', '032605': '2h Barbaric Roar R2 1 Release',
    '032610': '2h Barbaric Roar R2 2 Charged', '032615': '2h Barbaric Roar R2 2 Release',
    '032620': '2h War Cry R2 1 Charged', '032625': '2h War Cry R2 1 Release', '032630': '2h War Cry R2 2 Charged',
    '032635': '2h War Cry R2 2 Release', '032700': '2h Guard Counter', '032950': '2h Charged R2 1 Feint',
    '032955': '2h Charged R2 2 Feint', '033030': '2h Jumping R1', '033060': '2h Jumping R1 Hangtime',
    '033070': '2h Jumping R1 Landing', '033071': '2h Attack Landing Light', '033072': '2h Attack Landing Medium',
    '033081': '2h Attack Landing Recovery', '033082': '2h Attack Landing Heavy', '033230': '2h Jumping R2',
    '033260': '2h Jumping R2 Hangtime', '033270': '2h Jumping R2 Landing', '034000': 'Paired L1 1',
    '034010': 'Paired L1 2', '034020': 'Paired L1 3', '034030': 'Paired L1 4', '034040': 'Paired L1 5',
    '034050': 'Paired L1 6', '034200': 'Paired Running L1', '034300': 'Paired Rolling L1',
    '034310': 'Paired Crouch L1', '034400': 'Paired Backstep L1', '034530': 'Paired Jumping L1',
    '034560': 'Paired Jumping L1 Hangtime', '034570': 'Paired Jumping L1 Landing', '034572': '2H Landing 2',
    '034582': '2H Landing 4', '035000': 'Offhand L1 1', '035010': 'Offhand L1 2', '035020': 'Offhand L1 3',
    '035030': 'Offhand L1 4', '035040': 'Offhand L1 5', '035050': 'Offhand L1 6', '038000': 'Mounted R1 1',
    '038010': 'Mounted R1 2', '038020': 'Mounted R1 3', '039000': 'Mounted L1 1', '039010': 'Mounted L1 2',
    '039020': 'Mounted L1 3', '039100': 'Mounted L2 Charging', '039110': 'Mounted L2',
}

def fetch(name):
    path = os.path.join(CACHE, 'ref', name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        req = urllib.request.Request(REFS[name], headers={'User-Agent': 'game-animation-library frame-data import'})
        with urllib.request.urlopen(req) as r, open(path, 'wb') as f: f.write(r.read())
    return open(path, encoding='utf-8-sig').read()

def game_dir(arg):
    for d in (arg, os.path.join(arg, 'Game')):
        if os.path.exists(os.path.join(d, 'regulation.bin')): return d
    sys.exit(f'No regulation.bin under {arg}: pass the ELDEN RING install folder')

class Archives:
    """Finds files by path across the Data archives without unpacking them."""
    def __init__(self, game):
        self.game, keys = game, F.archive_keys(fetch('ArchiveKeys.cs'))
        self.index = {}
        for a in ARCHIVES:
            raw = F.rsa_decrypt(open(os.path.join(game, a + '.bhd'), 'rb').read(), keys[a])
            for h, entry in F.read_bhd5(raw).items(): self.index[h] = (a, entry)
    def read(self, path):
        a, entry = self.index[F.path_hash(path)]
        data = F.read_from_bdt(os.path.join(self.game, a + '.bdt'), entry)
        return F.dcx_decompress(data, os.path.join(self.game, 'oo2core_6_win64.dll'))

def regulation_version(v):
    m = re.match(r'1(\d\d)(\d)', v)
    if not m: return v
    return f'1.{int(m.group(1))}' + (f'.{m.group(2)}' if m.group(2) != '0' else '')

def jt(p): return struct.unpack_from('<i', p)[0]

def windows(events, frame, types, test):
    return sorted({(frame(s) + 1, frame(e)) for t, s, e, p in events if t in types and e < 1e6 and test(p) and frame(e) > frame(s)})

def build(game):
    bnd = F.decrypt_regulation(open(os.path.join(game, 'regulation.bin'), 'rb').read())
    reg_ver, reg = bnd[0x18:0x20].rstrip(b'\0').decode('ascii'), F.read_bnd4(bnd)
    weapons = F.read_param(reg['EquipParamWeapon.param'], fetch('EquipParamWeapon.xml'))
    behaviors = F.read_param(reg['BehaviorParam_PC.param'], fetch('BehaviorParam.xml'))
    attacks = F.read_param(reg['AtkParam_Pc.param'], fetch('AtkParam.xml'))
    arc = Archives(game)
    msg = F.read_bnd4(arc.read('/msg/engus/item_dlc02.msgbnd.dcx'))
    names = {}
    for f in ('WeaponName.fmg', 'WeaponName_dlc01.fmg', 'WeaponName_dlc02.fmg'):
        names.update({k: v for k, v in F.read_fmg(msg[f]).items() if v and v != '%null%'})
    taes = {}
    for f, data in F.read_bnd4(arc.read('/chr/c0000.anibnd.dcx')).items():
        if f.endswith('.tae'):
            sec, anims = F.read_tae(data); taes[sec] = anims

    # Base weapons (no affinity) by class, and the TAE sections each one plays: its own special section first
    by_class, users = {}, {}
    for wid, w in sorted(weapons.items()):
        cls = CLASSES.get(w['wepType'])
        if wid % 10000 or not cls or wid not in names or names[wid].startswith('[ERROR]'): continue
        by_class.setdefault(cls, []).append(names[wid])
        users[wid] = (cls, [s for s in (w['spAtkcategory'], w['wepmotionCategory']) if s])

    def events_of(sec, aid):
        evs, imp = taes[sec][aid]
        if imp is not None and imp // 1000000 in taes and imp % 1000000 in taes[imp // 1000000]:
            evs = evs + events_of(imp // 1000000, imp % 1000000)
        return evs

    moves = {}
    for wid, (cls, secs) in users.items():
        if cls not in CLASS_FAMILY: continue
        for suffix, name in MOVE_NAMES.items():
            aid = int(suffix)
            sec = next((s for s in secs if aid in taes.get(s, {})), None)
            if sec is None: continue
            key = (cls, f'a{sec:03d}_{suffix}')
            if key in moves:
                moves[key]['weapons'].append(names[wid]); continue
            mt = move_type(name)
            if not mt: continue
            ev = events_of(sec, aid)
            frame = F.frame_clock(ev, FPS)
            # Hitboxes: event 1 (judge id at +8), or 304 for criticals and throws (judge id at +4)
            hits = sorted((frame(s), frame(e), struct.unpack_from('<i', p, 8 if t == 1 else 4)[0])
                          for t, s, e, p in ev if t in (1, 304) and e < 1e6 and frame(e) > frame(s))
            if not hits: continue
            active = [[s + 1, e] for s, e, _ in hits]
            first, ends = {}, []
            for t, s, e, p in ev:
                # Event 300 is a cancel window per equip load (byte 2: 1 light, 2 regular); a jump table window at
                # frame 0 is carried over from the previous animation
                j = struct.unpack_from('<H', p)[0] if t == 300 and p[2] == 2 else jt(p) if t == 0 and frame(s) else None
                if j not in CANCEL_IDS: continue
                first[j] = min(first.get(j, 1 << 30), frame(s))
                if e < 1e6 and t == 0: ends.append(frame(e))
            cancels = {k: min(first[j] for j in js if j in first) + 1 for k, js in CANCELS.items() if any(j in first for j in js)}
            last = max(e for _, e in active)
            # First hit's damage: behavior variation + judge id -> BehaviorParam_PC -> AtkParam_Pc
            w = weapons[wid]
            # (judge ids from 1000 up belong to skills and use the skill's variation, which this doesn't resolve)
            judge = hits[0][2]
            b = None if judge >= 1000 else behaviors.get(100000000 + w['behaviorVariationId'] * 1000 + judge) \
                or behaviors.get(100000000 + w['behaviorVariationId'] // 100 * 100 * 1000 + judge)
            atk = attacks.get(b['refId']) if b and b['refType'] == 0 else None
            phys = None
            if atk:
                a = atk['atkAttribute']
                phys = PHYS.get(w['atkAttribute'] if a == 253 else w['atkAttribute2'] if a == 252 else a)
            moves[key] = {
                'id': key[1], 'class': cls, 'type': mt, 'grip': grip(name), 'name': name,
                'startup': active[0][0], 'active': active,
                'activeFrames': sum(e - s + 1 for s, e in active), 'hits': len(active),
                'recovery': cancels['dodge'] - 1 - last if 'dodge' in cancels else None,
                'total': max(ends) if ends else None,
                'cancels': cancels,
                'armor': windows(ev, frame, (791, 795), lambda p: True),
                'iframes': windows(ev, frame, (0,), lambda p: jt(p) == 8),
                'parryable': any(t == 0 and jt(p) == 5 for t, s, e, p in ev),
                'damage': {k: v for k, v in {
                    'type': phys, 'mv': atk and atk['atkPhysCorrection'], 'level': atk and atk['dmgLevel'],
                    'stamina': b and b['stamina']}.items() if v not in (None, '')},
                'weapons': [names[wid]],
            }
    return wrap(list(moves.values()), by_class,
        {'id': 'elden-ring', 'name': 'Elden Ring', 'fps': FPS, 'version': regulation_version(reg_ver),
         'frameNote': 'Frames are animation (TAE) frames at 30 fps, 1-based: startup is the first frame the hitbox is out.'},
        {'name': 'Elden Ring game files', 'url': SELF_URL, 'author': 'FromSoftware',
         'retrieved': datetime.date.today().isoformat(), 'method': 'import_er_game.py',
         'moveUrl': EXPLORER + '/?animation={id}', 'moveName': 'Frame Data Explorer',
         'note': f'Elden Ring data is read straight from the game files (patch {regulation_version(reg_ver)}, regulation '
                 f'{reg_ver}, read {datetime.date.today().isoformat()}): hitboxes, cancel windows and hyper armor from the '
                 'player animation events, damage from the game params. Poise damage and skill-buffed damage are not read '
                 'yet. Move names follow the Elden Ring Frame Data Explorer by Emilia (sovietspaceship), and each move '
                 'links to it for comparison.',
         'links': [{'name': 'Importer', 'url': SELF_URL}, {'name': 'Frame Data Explorer', 'url': EXPLORER},
                   {'name': 'Ko-fi', 'url': 'https://ko-fi.com/sovietspaceship'}]})

if __name__ == '__main__':
    args = sys.argv[1:]
    out = os.path.join(ROOT, 'frame-data', 'elden-ring.json')
    if '--out' in args:
        i = args.index('--out'); out = os.path.abspath(args[i + 1]); del args[i:i + 2]
    if not args: sys.exit(__doc__)
    data = build(game_dir(args[0]))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print('wrote', out, len(data['classes']), 'classes', len(data['moves']), 'moves')

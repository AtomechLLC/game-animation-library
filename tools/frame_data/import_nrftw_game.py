"""Builds frame-data/no-rest-for-the-wicked.json from a No Rest for the Wicked install, in the frame-data/1 format.

    python tools/frame_data/import_nrftw_game.py "Z:/SteamLibrary/steamapps/common/NoRestForTheWicked"
    python tools/frame_data/import_nrftw_game.py <game folder> --out frame-data/nrftw-test.json --no-icons

Also writes 96 px weapon icons to frame-data/icons/no-rest-for-the-wicked/ (skip with --no-icons).

Reads only; nothing in the game folder is written. Needs UnityPy and lz4. The decoded database is cached in
.cache/nrftw/ (about 1 GB) so later runs take seconds.

Where the numbers come from (file formats in nrftw_files.py, enum names in nrftw_il2cpp.py):
    quantumDatabase.bin  worldlut.asset          every weapon (armament) with its class filter, moveset (.actions) and
                                                 collider data; class filters carry the class's default moveset
                         <weapon>.actions        moveset slots (ArmamentActionType: specials = runes, normal combos,
                                                 run, quickstep, roll, knockdown, plunge, parry), each a list of
                                                 actions in combo order; a weapon's slot replaces its class's slot
                         <move>.action           TimelineData: WeaponColliders (hitbox windows), Sections (cancel,
                                                 i-frame and armor windows, QuantumActionSectionId), Duration;
                                                 DamageConfig (damage school, parryable). Windup actions hold the tap
                                                 (NormalAttack) and hold (ChargedAttack) versions of a combo step.
    qdb_assets bundle    item MonoBehaviours     English weapon and rune names (ItemNameMsg)
    global-metadata.dat                          enum names: section ids, action types, damage schools
Times are seconds in the simulation, which runs at 60 fps; frames here are 1-based at 60 fps.
"""
import datetime, json, os, re, sys
import nrftw_files as N
from nrftw_il2cpp import Metadata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SELF_URL = 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_nrftw_game.py'
FPS = 60

# Quantum asset type hashes (first element of each database entry)
T_WINDUP = 268113678      # ActionComboRootTimeline-like: NormalAttack / ChargedAttack
T_PARRY = 858221116

FAMILIES = [('dualWield', 'Dual wield'), ('oneHanded', 'One-handed'), ('twoHanded', 'Two-handed')]
GRIPS = [{'id': 'Paired', 'name': 'Dual wield', 'short': 'Dual'}, {'id': '1h', 'name': 'One-handed', 'short': '1H'},
         {'id': '2h', 'name': 'Two-handed', 'short': '2H'}]
FAMILY_GRIP = {'dualWield': 'Paired', 'oneHanded': '1h', 'twoHanded': '2h'}
CLASS_NAMES = {'crossbowss': 'Crossbows', 'curvedGreatSwords': 'Curved Greatswords', 'greatAxes': 'Greataxes',
               'greatSwords': 'Greatswords', 'doubleDaggers': 'Double Daggers'}

# ArmamentActionType slot -> move type; combos split into tap (light) and hold (charged)
SLOTS = {1: 'light', 2: 'running', 3: 'quickstep', 4: 'rolling', 6: 'plunge', 5: 'getup', 7: 'parry', 0: 'rune'}
MOVE_TYPES = [
    ('light', 'Combo', 'Attack button, tapped: the weapon\'s combo string'),
    ('charged', 'Charged', 'Attack button, held: each combo step\'s charged version, timed from release'),
    ('running', 'Running', 'Attacks out of a sprint'),
    ('quickstep', 'Quickstep', 'Attacks out of a quickstep'),
    ('rolling', 'Rolling', 'Attacks out of a roll'),
    ('plunge', 'Plunge', 'Attacks falling from a ledge'),
    ('getup', 'Get-up', 'Attacks out of a knockdown'),
    ('parry', 'Parry', 'Parries; the active window is the parry window'),
    ('rune', 'Rune', 'The weapon\'s own runes (weapon skills)'),
]
TYPE_LABEL = {t: n for t, n, _ in MOVE_TYPES}

# QuantumActionSectionId and the ActionType flags in a section's Mask (nrftw_il2cpp.py prints both)
S_ALL, S_MOVE, S_ACTION, S_NEXT_ATTACK, S_INVINCIBLE, S_PARRY = 2, 3, 4, 6, 7, 13
S_ARMOR = (45, 46, 47)    # ImmunitySturdy, ImmunityResilient, ImmunityImmune
F_MELEE, F_SPECIAL, F_DODGE, F_QUICKDODGE, F_BLOCK = 2, 8, 16, 32, 64
CANCELS = {'attack': (S_NEXT_ATTACK,), 'dodge': (), 'block': (), 'skill': (), 'move': (S_MOVE,)}
CANCEL_FLAGS = {'attack': F_MELEE, 'dodge': F_DODGE | F_QUICKDODGE, 'block': F_BLOCK, 'skill': F_SPECIAL, 'move': 0}

def fx(v):
    return v['RawValue'] / 65536 if isinstance(v, dict) else v

def frame(t):
    """0-based frame index at time t (seconds)."""
    return int(round(fx(t) * FPS))

def window(s, e):
    """1-based inclusive frames of a [s, e) time window."""
    a = frame(s) + 1
    return [a, max(a, frame(e))]

def merge(ws):
    out = []
    for a, b in sorted(ws):
        if out and a <= out[-1][1] + 1: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out

def words(name):
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', name).split()

def humanize(name):
    return ' '.join(w[:1].upper() + w[1:] for w in words(name))

def short_label(stem, cls):
    """'doubleDaggerAttackA1' in class doubleDaggers -> 'Attack A1'; borrowed animations keep their class."""
    s = re.sub(r'^hero(?=[A-Z])', '', stem)
    s = s[:1].lower() + s[1:]
    base = ''.join(w.lower() for w in words(cls))
    for prefix in (base, base[:-1], base.rstrip('s')):
        if prefix and s.lower().startswith(prefix) and len(s) > len(prefix):
            s = s[len(prefix):]
            break
    label = humanize(s)
    # 'Combo A4' / 'Attack A1' under a Combo heading reads as 'A4' / 'A1'
    return re.sub(r'^(Combo|Attack) (?=[A-Z]\d)', '', label)

class Importer:
    def __init__(self, game_dir):
        self.g = N.Game(game_dir)
        self.meta = Metadata(game_dir)
        self.schools = self.meta.enum('DamageSchool')
        self.items = {}          # weapon name -> item asset path (for icons)

    def stem(self, ref):
        p = self.g.path.get(ref['Id']['Value'] if isinstance(ref, dict) else ref, '')
        return p.rsplit('/', 1)[-1].rsplit('.', 1)[0]

    def timing(self, a):
        """Frame data of one action asset (anything with TimelineData), or None when it never hits."""
        T = a.get('TimelineData')
        if not T or 'Duration' not in T: return None
        hits = [window(c['StartTime'], c['EndTime']) for c in T.get('WeaponColliders', [])]
        hits += [window(c['StartTime'], c['EndTime']) for c in T.get('Hitcolliders', []) if 'StartTime' in c]
        hits += [window(p['SpawnTime'], p['SpawnTime']) for p in T.get('ProjectileEvents', [])]
        hits += [window(p['spawnTime'], p['spawnTime']) for p in T.get('SpawnEntityEvents', [])]
        secs = T.get('Sections', [])
        if not hits:
            hits = [window(s['Start'], s['End']) for s in secs if s['Id'] == S_PARRY]
        if not hits:
            at = T.get('AttackSections', {})
            if fx(at.get('RecoveryStartTime', 0)) > fx(at.get('ActiveStartTime', 0)):
                hits = [window(at['ActiveStartTime'], at['RecoveryStartTime'])]
        if not hits: return None
        active = merge(hits)
        cancels = {}
        for kind, ids in CANCELS.items():
            starts = [frame(s['Start']) + 1 for s in secs
                      if s['Id'] in ids or s['Id'] == S_ALL
                      or (s['Id'] == S_ACTION and CANCEL_FLAGS[kind] and s['Mask'] & CANCEL_FLAGS[kind])]
            if starts: cancels[kind] = min(starts)
        total = frame(T['Duration'])
        last = active[-1][1]
        dc = a.get('DamageConfig') or {}
        dmg = (dc.get('Damage') or {})
        damage = {}
        if dmg.get('DamageSchool') in self.schools and dmg.get('DamageSchool'):
            damage['type'] = self.schools[dmg['DamageSchool']]
        return {
            'startup': active[0][0], 'active': active, 'activeFrames': sum(b - a + 1 for a, b in active),
            'hits': len(active),
            'recovery': (cancels['dodge'] - last - 1) if cancels.get('dodge', 0) > last else max(0, total - last),
            'total': total, 'cancels': cancels,
            'armor': merge([window(s['Start'], s['End']) for s in secs if s['Id'] in S_ARMOR]),
            'iframes': merge([window(s['Start'], s['End']) for s in secs if s['Id'] == S_INVINCIBLE]),
            'parryable': bool(dc.get('Parryable', True)),
            'damage': damage,
            'anim': [self.g.path.get(x['Animation']['Id']['Value'], '').rsplit('/', 1)[-1] for x in a.get('Animations', [])],
        }

    def expand(self, slot, entry):
        """One moveset entry -> [(move type, action guid, charge frames)]; windups give their tap and hold versions."""
        gid = entry['Action']['Id']['Value']
        a = self.g.asset(gid)
        if a is None: return []
        mtype = SLOTS[slot]
        if self.g.type_of(gid) == T_WINDUP:
            hold = [frame(s['Start']) for s in a['TimelineData']['Sections'] if s['Id'] == 12]
            out = [(mtype, a['NormalAttack']['Id']['Value'], None)]
            if a['ChargedAttack']['Id']['Value']:
                out.append(('charged' if slot == 1 else mtype, a['ChargedAttack']['Id']['Value'], min(hold) if hold else None))
            return out
        if slot == 1 and a.get('IsChargedAttack'): mtype = 'charged'
        return [(mtype, gid, None)]

    def build(self):
        g = self.g
        lut = g.asset('Assets/worldlut.asset')
        filters = lut['ArmamentFilters']
        parent = {x['FilterIndex']: x['ParentIndex'] for x in lut['ArmamentFilterParentLookup']}
        fname = [self.stem(f['Data']) for f in filters]
        classes, moves = [], {}
        for fi, f in enumerate(filters):
            cls_actions = g.asset(f['ActionSelection']) if f['ActionSelection']['Id']['Value'] else None
            if not cls_actions: continue
            fam = fname[parent.get(fi, 0)]
            if fam not in FAMILY_GRIP: continue
            cid = fname[fi]
            arms = [a for a in lut['Armaments'] if a['Filter']['Id']['Value'] == f['Data']['Id']['Value']]
            if not arms: continue      # classes no weapon uses yet (nunchucks, crossbows)
            weapons = []
            for arm in arms:
                item = g.path.get(arm['Weapons'][0]['Id']['Value']) if arm['Weapons'] else None
                name = (g.english(item) if item else None) or humanize(self.stem(arm['Data']))
                weapons.append((name, arm))
                if item: self.items[name] = item
            weapons.sort(key=lambda w: w[0])
            names = [w for w, _ in weapons]
            base = dict(zip(cls_actions['SelectionData'], cls_actions['SelectionData$1']))
            # Index -1 = the class's default moveset (no weapon picked)
            for wi, (wname, arm) in [(-1, (None, None))] + list(enumerate(weapons)):
                slots = dict(base)
                if arm:
                    own = g.asset(arm['ActionSelection'])
                    if own: slots.update(zip(own['SelectionData'], own['SelectionData$1']))
                for slot, entries in slots.items():
                    if slot not in SLOTS or (slot == 0 and wi < 0): continue
                    for step, entry in enumerate(entries['Actions'], 1):
                        for mtype, gid, charge in self.expand(slot, entry):
                            stem = self.stem(gid)
                            mid = f'{cid}.{mtype}{step}.{stem}'
                            m = moves.get(mid)
                            if m is None:
                                t = self.timing(g.asset(gid))
                                if t is None: continue
                                if mtype == 'rune':
                                    rune = next((p for p in g.guid if p.endswith('/' + stem + '.asset') and '/items/runes/' in p), None)
                                    label = (g.english(rune) if rune else None) or humanize(stem)
                                    name = label
                                else:
                                    label = short_label(stem, cid)
                                    if mtype == 'charged': label = re.sub(r' Charge$', '', label)
                                    name = f'{TYPE_LABEL[mtype]} {step} · {label}' if len(entries['Actions']) > 1 or slot == 1 else f'{TYPE_LABEL[mtype]} · {label}'
                                m = moves[mid] = {'id': mid, 'class': cid, 'type': mtype, 'grip': FAMILY_GRIP[fam],
                                                  'name': name, **t, 'weapons': set(), 'default': False,
                                                  'step': step, 'action': stem}
                                if charge is not None: m['charge'] = charge
                            if wi < 0: m['default'] = True
                            else: m['weapons'].add(wi)
            classes.append({'id': cid, 'name': CLASS_NAMES.get(cid, humanize(cid)), 'family': fam,
                            'icon': names[0] if names else None, 'weapons': names})
        order = {t[0]: i for i, t in enumerate(MOVE_TYPES)}
        fam_order = {f: i for i, (f, _) in enumerate(FAMILIES)}
        classes.sort(key=lambda c: (fam_order[c['family']], c['name']))
        corder = {c['id']: i for i, c in enumerate(classes)}
        out = sorted(moves.values(), key=lambda m: (corder[m['class']], order[m['type']], m['step'], m['name']))
        for m in out:
            m['weapons'] = sorted(m['weapons'])
            del m['step']
        for c in classes: c['moves'] = sum(1 for m in out if m['class'] == c['id'])
        return {
            'schema': 'frame-data/1',
            'game': {'id': 'no-rest-for-the-wicked', 'name': 'No Rest for the Wicked', 'fps': FPS,
                     'version': self.version(),
                     'frameNote': 'Frames are simulation frames at 60 fps, 1-based: startup is the first frame a hitbox '
                                  'is out. Charged attacks are timed from the release; holding the button first takes '
                                  'the frames shown as charge.'},
            'source': {'name': 'No Rest for the Wicked game files', 'url': SELF_URL, 'author': 'Moon Studios',
                       'retrieved': datetime.date.today().isoformat(), 'method': 'import_nrftw_game.py',
                       'note': 'No Rest for the Wicked data is read straight from the game files (' + self.version() +
                               '): hitbox windows, cancel windows, i-frames and armor from each action\'s timeline in '
                               'the gameplay database, movesets from each weapon\'s action selection. Damage numbers '
                               'scale with the weapon and are not shown yet.',
                       'links': [{'name': 'Importer', 'url': SELF_URL}]},
            'families': [{'id': f, 'name': n} for f, n in FAMILIES],
            'classes': classes,
            'moveTypes': [{'id': i, 'name': n, 'description': d} for i, n, d in MOVE_TYPES],
            'grips': GRIPS,
            'moves': out,
        }

    def version(self):
        acf = os.path.join(self.g.dir, '..', '..', 'appmanifest_1371980.acf')
        try:
            build = re.search(r'"buildid"\s+"(\d+)"', open(acf).read()).group(1)
            return f'Steam build {build}'
        except (OSError, AttributeError):
            cfg = open(os.path.join(self.g.dir, 'NoRestForTheWicked_Data', 'boot.config')).read()
            return 'build ' + re.search(r'build-guid=(\w+)', cfg).group(1)[:8]

def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

def write_icons(imp, folder, size=96):
    """96 px WebP inventory icons per weapon and icons.json (weapon name -> file), like import_er_icons.py."""
    os.makedirs(folder, exist_ok=True)
    icons = {}
    for name, item in sorted(imp.items.items()):
        im = imp.g.icon(item)
        if im is None: continue
        im = im.convert('RGBA')
        im.thumbnail((size, size))
        fn = slug(name) + '.webp'
        im.save(os.path.join(folder, fn), 'WEBP', quality=82, method=6)
        icons[name] = {'file': fn, 'source': item}
    with open(os.path.join(folder, 'icons.json'), 'w', encoding='utf-8') as f:
        json.dump({'sources': [{'name': 'No Rest for the Wicked game files', 'url': SELF_URL}],
                   'note': "Icons are the game's inventory art, (c) Moon Studios / Private Division.", 'icons': icons},
                  f, ensure_ascii=False, indent=1)
    return len(icons)

if __name__ == '__main__':
    args = sys.argv[1:]
    out = os.path.join(ROOT, 'frame-data', 'no-rest-for-the-wicked.json')
    if '--out' in args:
        i = args.index('--out'); out = os.path.abspath(args[i + 1]); del args[i:i + 2]
    icons = '--no-icons' not in args
    args = [a for a in args if a != '--no-icons']
    if not args: sys.exit(__doc__)
    imp = Importer(args[0])
    data = imp.build()
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print('wrote', out, len(data['classes']), 'classes', len(data['moves']), 'moves')
    if icons:
        print('icons', write_icons(imp, os.path.join(ROOT, 'frame-data', 'icons', 'no-rest-for-the-wicked')))

"""Builds frame-data/street-fighter-3-third-strike.json from Baston (http://ensabahnur.free.fr/BastonNew/).

    python tools/frame_data/import_baston_sf3.py      # cached downloads in .cache/baston/ (~1,300 pages, ~110 MB)

Baston is a Street Fighter III: 3rd Strike frame data site by ensabahnur, with data and hitboxes extracted from the
CPS3 emulator FBA-RR (hitbox work credited there to LennethEX, Dammit, C_cube and ComedyBlissOption). Each character
has frame data tables (normals, specials, Super Arts, Genei-Jin moves for Yun, and misc movement), and each move
has a hitbox page holding its per-frame boxes and a sprite capture per frame.

The tables give startup, active total, recovery, advantage, cancels, parry direction, damage and stun. The hitbox
pages give exact active windows: a frame is active when P1 or one of its objects (projectiles) has an attack box,
or P1 has a throw box. Superfreeze frames are dropped, so frame 1 of a Super Art is the first frame after the
freeze, as in the tables. Baston's startup counts the frames before the hit; the site's format wants the first
active frame, which is Baston's startup + 1.
"""
import json, os, re, sys, time, html, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = 'http://ensabahnur.free.fr/BastonNew/'
CACHE = os.path.join(ROOT, '.cache', 'baston')
OUT = os.path.join(ROOT, 'frame-data', 'street-fighter-3-third-strike.json')
ICONS = os.path.join(ROOT, 'frame-data', 'icons', 'street-fighter-3-third-strike')

# Baston character id -> (slug, name)
CHARS = {1: ('alex', 'Alex'), 2: ('ryu', 'Ryu'), 3: ('yun', 'Yun'), 4: ('dudley', 'Dudley'), 5: ('necro', 'Necro'),
         6: ('hugo', 'Hugo'), 7: ('ibuki', 'Ibuki'), 8: ('elena', 'Elena'), 9: ('oro', 'Oro'), 10: ('yang', 'Yang'),
         11: ('ken', 'Ken'), 12: ('sean', 'Sean'), 13: ('urien', 'Urien'), 14: ('gouki', 'Gouki (Akuma)'),
         16: ('chun-li', 'Chun-Li'), 17: ('makoto', 'Makoto'), 18: ('q', 'Q'), 19: ('twelve', 'Twelve'),
         20: ('remy', 'Remy'), 0: ('gill', 'Gill')}
# Baston table -> move type
TABLES = {'fd_normals': 'normal', 'fd_specials': 'special', 'fd_supers': 'super', 'fd_gj_normals': 'gjNormal',
          'fd_gj_specials': 'gjSpecial', 'fd_misc': 'movement'}
CANCEL = {'SA': 'Super Art', 'SP': 'Special', 'SC': 'Self (chain)', 'NC': 'Normal / target combo', 'DC': 'Dash',
          'SJ': 'Superjump'}


def fetch(name, url, data=None, binary=False):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        req = urllib.request.Request(url, data=data and urllib.parse.urlencode(data).encode(),
                                     headers={'User-Agent': 'game-animation-library frame-data import'})
        for i in range(4):
            try:
                with urllib.request.urlopen(req, timeout=90) as r: body = r.read()
                break
            except OSError:
                if i == 3: raise
                time.sleep(2 ** i)
        open(path, 'wb').write(body)
        time.sleep(0.3)  # a hobby site: go slowly
    return path if binary else open(path, encoding='utf-8', errors='replace').read()


def text(td):
    return html.unescape(re.sub(r'<[^>]+>', '', td)).strip()


def num(v):
    v = (v or '').strip()
    return int(v) if re.fullmatch(r'[+-]?\d+', v) else None


def adv(v):
    """Advantage: an int, a range like '-5 ~ +7' kept as text, 'D' (knockdown) as 'KD', '-' as None."""
    v = (v or '').strip()
    if v in ('', '-'): return None
    if v == 'D': return 'KD'
    return int(v) if re.fullmatch(r'[+-]?\d+', v) else v


def table(ch, t):
    s = fetch(f't_{ch}_{t}.html', BASE + 'index.php',
              {'page': 'ajax_loadData.php', 'iChar': ch, 'type': 'fd', 'id': t[3:], 'div': 'content_char', 'version': 'revised'})
    if t == 'fd_misc':
        rows = []
        for mid, label, val in re.findall(r'id="load_(\w+)"></div><p>([^<]*)</p>\s*:\s*([^<]*)</dd>', s):
            rows.append({'move': mid, 'Name': html.unescape(label), 'Total': val.strip()})
        return rows
    head = [text(h) for h in re.findall(r'<th[^>]*>(.*?)</th>', s, re.S)]
    rows = []
    for r in re.findall(r'<tr class="fd_tr_hover">(.*?)</tr>', s, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
        row = {h: text(td) for h, td in zip(head, tds)}
        row['move'] = '%03d' % int(re.search(r'id="load_(\d+)"', r).group(1))
        cancel = next((td for h, td in zip(head, tds) if h == 'Cancel'), '')
        row['cancels'] = [a for b, a in re.findall(r'BcancelBit_(\w+)" title="[^"]*">([^<]*)<', cancel) if b != 'X' and a in CANCEL]
        rows.append(row)
    return rows


def frames(ch, t, move):
    mt = move if t == 'fd_misc' else t
    s = fetch(f'hb/{ch}_{t}_{move}.html', BASE + 'hitboxesDisplay.php?' + urllib.parse.urlencode(
        {'sMode': 'f', 'iChar': ch, 'sMoveType': mt, 'sAction': 'w', 'iMove': move}))
    m = re.search(r'aFramesInfos = (\{.*?\});\n', s)
    return json.loads(m.group(1)) if m else None


def boxes(fr, who, key):
    return [b for b in ((fr.get(who) or {}).get('hitboxes') or {}).get(key, []) if b != '0,0,0,0']


def windows(fs):
    """Active windows (1-based, superfreeze dropped), freeze length and frame count of a hitbox page."""
    keys = sorted(fs, key=int)
    kept = [k for i, k in enumerate(keys) if i == 0 or fs[k]['GLOBAL'].get('superfreeze', '0') == '0']
    on = []
    for i, k in enumerate(kept):
        fr = fs[k]
        hit = boxes(fr, 'P1', 'a_hb') or boxes(fr, 'P1', 't_hb') or any(boxes(fr, o, 'a_hb') for o in fr.get('objects_list', []))
        if hit: on.append(i)
    win = []
    for f in on:
        if win and win[-1][1] == f - 1: win[-1][1] = f
        else: win.append([f, f])
    return win, len(keys) - len(kept), len(kept)


def stance(t, name, motion):
    s = (name + ' ' + motion).lower()
    if re.search(r'\bjump|\(air\)|air throw|\bair\b|dive kick', s): return 'air'
    if t in ('fd_normals', 'fd_gj_normals') and 'crouching' in s: return 'crouch'
    return 'stand'


def build():
    moves, classes, agree, total_ok, checked = [], [], 0, 0, 0
    for ch, (slug, cname) in CHARS.items():
        page = fetch(f'char_{ch}.html', f'{BASE}index.php?id={ch}')
        n = 0
        for t in re.findall(r'<li id="(fd_\w+)"', page):
            for row in table(ch, t):
                fs = frames(ch, t, row['move'])
                win, freeze, count = windows(fs) if fs else ([], 0, 0)
                name, motion = row['Name'], row.get('Motion', '')
                st_t, hit, rec = num(row.get('Startup')), num(row.get('Hit')), num(row.get('Recovery'))
                if win and st_t is not None:
                    checked += 1; agree += win[0][0] == st_t + 1
                # The table's startup wins, except where the capture's first box comes much later (a charged
                # capture, e.g. Denjin Hadouken). A projectile's box shows a frame before the table counts it,
                # so windows are trimmed to start no earlier than the startup.
                startup = st_t + 1 if st_t is not None else (win[0][0] if win else None)
                if win and win[0][0] > startup + 2: startup = win[0][0]
                win = [[max(s, startup), e] for s, e in win if e >= startup]
                if t == 'fd_misc':
                    total = num(row['Total'].split()[0])
                elif count > 2:
                    total = count - 2  # the page's last frame is the first one back in neutral
                    total_ok += None not in (st_t, hit, rec) and st_t + hit + rec + sum(win[i][0] - win[i - 1][1] - 1 for i in range(1, len(win))) == total
                elif None not in (st_t, hit, rec):
                    total = st_t + hit + rec
                else:
                    total = None
                last = win[-1][1] if win else None
                dmg, stun = num(row.get('Damage')), num(row.get('Stun'))
                m = {
                    'id': f'{slug}.{TABLES[t]}.{row["move"]}', 'class': slug, 'type': TABLES[t],
                    'grip': stance(t, name, motion), 'name': name, 'input': motion or None,
                    'startup': startup, 'active': win, 'activeFrames': sum(e - s + 1 for s, e in win) or hit,
                    'hits': len(win), 'recovery': total - last if total and last and total >= last else rec,
                    'total': total, 'cancels': {}, 'cancelTo': row.get('cancels', []),
                    'armor': [], 'iframes': [],
                    'parryable': row.get('Parry', '-') not in ('-', ''),
                    'blockAdv': adv(row.get('Blk. Adv.')), 'hitAdv': adv(row.get('Hit Adv.')),
                    'crHitAdv': adv(row.get('Cr. Hit Adv.')),
                    'damage': {k: v for k, v in (('amount', dmg), ('stun', stun), ('guard', row.get('Parry') or None)) if v not in (None, '-')},
                    'weapons': [], 'default': True,
                    'url': BASE + 'hitboxesDisplay.php?' + urllib.parse.urlencode(
                        {'sMode': 'f', 'iChar': ch, 'sMoveType': row['move'] if t == 'fd_misc' else t, 'sAction': 'w', 'iMove': row['move']}),
                }
                extra = {}
                if freeze: extra['Superfreeze'] = f'{freeze} frames (not counted)'
                for k, label in (('Kara Range', 'Kara range'), ('Throw Range', 'Throw range'), ('BarGainAtt', 'Super bar gain (whiff / hit / block)'),
                                 ('BarGainOpp', 'Opponent bar gain (hit / block)')):
                    v = re.sub(r'\s+', ' ', row.get(k, '')).strip()
                    if v and v != '-': extra[label] = v
                if t == 'fd_misc': extra['Length'] = row['Total']
                if extra: m['extra'] = extra
                moves.append(m); n += 1
        classes.append({'id': slug, 'name': cname, 'family': 'roster', 'icon': cname, 'weapons': [], 'moves': n})
    print(f'{len(moves)} moves; hitbox startup = table startup + 1 on {agree}/{checked}; table startup + active + recovery = page length on {total_ok}')
    return {
        'schema': 'frame-data/1',
        'game': {'id': 'street-fighter-3-third-strike', 'name': 'Street Fighter III: 3rd Strike', 'fps': 60,
                 'version': 'CPS3 (Baston revised data)',
                 'frameNote': 'Frames are game frames at 60 fps, 1-based: startup is the first frame the hitbox (or throw box, or projectile) is out. Super Arts are timed from the end of the superfreeze. Advantage is on block, on hit and on crouching hit; KD is a knockdown.'},
        'source': {'name': 'Baston', 'url': BASE, 'author': 'ensabahnur', 'retrieved': time.strftime('%Y-%m-%d'),
                   'method': 'import_baston_sf3.py', 'moveName': 'Baston hitbox viewer',
                   'note': 'Street Fighter III: 3rd Strike frame data and hitboxes from Baston by ensabahnur, extracted from the CPS3 emulator FBA-RR (hitbox work by LennethEX, Dammit, C_cube and ComedyBlissOption; the parry column is from the old karathrow.com data). Active windows come from the per-frame hitboxes; every move links to its Baston hitbox viewer.',
                   'links': [{'name': 'Baston', 'url': BASE}, {'name': 'Importer', 'url': 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_baston_sf3.py'}]},
        'labels': {'class': 'Character', 'classes': 'characters', 'allClasses': 'All characters', 'grip': 'Stance',
                   'allFamilies': 'All characters', 'search': 'Search moves, characters, inputs…', 'everyClass': 'Every character', 'patch': '',
                   'pickClass': 'Pick a character to see their moves by type, or filter and sort the whole roster below.',
                   'classView': 'every move, by type.', 'recovery': 'Frames from the last active frame until the move ends'},
        'columns': ['name', 'class', 'strip', 'startup', 'active', 'recovery', 'total', 'blockAdv', 'hitAdv', 'dmg', 'stun', 'guard', 'cancel'],
        'families': [{'id': 'roster', 'name': 'Roster'}],
        'classes': classes,
        'moveTypes': [
            {'id': 'normal', 'name': 'Normals', 'description': 'Standing, crouching and jumping normals, command normals and throws'},
            {'id': 'special', 'name': 'Specials', 'description': 'Special moves, each strength and EX version'},
            {'id': 'super', 'name': 'Super Arts', 'description': 'Super Arts, timed from the end of the superfreeze'},
            {'id': 'gjNormal', 'name': 'Genei-Jin normals', 'description': 'Yun\'s normals during the Genei-Jin Super Art'},
            {'id': 'gjSpecial', 'name': 'Genei-Jin specials', 'description': 'Yun\'s specials during the Genei-Jin Super Art'},
            {'id': 'movement', 'name': 'Movement', 'description': 'Jumps, dashes and wake-ups: length only'},
        ],
        'grips': [{'id': 'stand', 'name': 'Standing', 'short': 'St'}, {'id': 'crouch', 'name': 'Crouching', 'short': 'Cr'},
                  {'id': 'air', 'name': 'Air', 'short': 'Air'}],
        'moves': moves,
    }


def icons():
    """Each character's animated stance from their Baston page, as a looping WebP (needs ffmpeg)."""
    import subprocess
    os.makedirs(ICONS, exist_ok=True)
    out = {}
    for ch, (slug, cname) in CHARS.items():
        url = re.search(r'id="charInfo">\s*<img src="([^"]+)"', fetch(f'char_{ch}.html', f'{BASE}index.php?id={ch}')).group(1)
        gif = fetch(f'icons/{ch}.gif', url, binary=True)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', gif, '-vf', "scale='min(144,iw)':-1:flags=neighbor",
                        '-loop', '0', '-c:v', 'libwebp', '-lossless', '1', '-compression_level', '6', os.path.join(ICONS, slug + '.webp')], check=True)
        out[cname] = {'file': slug + '.webp', 'source': url}
    json.dump({'sources': [{'name': 'Baston', 'url': BASE}], 'lead': 'Character icons are the game\'s stance animations',
               'note': 'Sprites (c) Capcom.', 'icons': out}, open(os.path.join(ICONS, 'icons.json'), 'w'), indent=1)


if __name__ == '__main__':
    icons()
    d = build()
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('{\n' + ',\n'.join(f' {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}' for k, v in d.items() if k != 'moves'))
        f.write(',\n "moves": [\n' + ',\n'.join('  ' + json.dumps(m, ensure_ascii=False) for m in d['moves']) + '\n ]\n}\n')
    print('wrote', os.path.relpath(OUT, ROOT), os.path.getsize(OUT) // 1024, 'KB')

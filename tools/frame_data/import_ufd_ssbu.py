"""Builds frame-data/super-smash-bros-ultimate.json from Ultimate Frame Data (https://ultimateframedata.com/smash).

    python tools/frame_data/import_ufd_ssbu.py            # 90 pages, ~2 minutes the first time (cached in .cache/ufd/)
    python tools/frame_data/import_ufd_ssbu.py --clips    # also the hitbox GIFs, ~3,500 of them, about an hour

Ultimate Frame Data is a Super Smash Bros. Ultimate frame data site by MetalMusicMan, with Zeckemyro and many
contributors (credited on the site's About box). Each character page lists ground attacks, aerials, specials,
grabs/throws and dodges, each move with startup, active frames, total frames, landing lag, notes, base damage,
shield lag, shield stun, which hitbox the values are for, advantage on shield and endlag, plus one or more hitbox
GIFs. The GIFs are captures of the game (Nintendo's footage) with hitboxes drawn on, one GIF frame per game frame.

--clips downloads each move's GIFs and converts them to animated WebPs (at most 440x280) in
frame-data/clips/super-smash-bros-ultimate/<character>/ (Move Explorer's docked previewer steps through them
frame by frame). Moves only list clips that exist locally, so run it before the JSON build you commit.
"""
import json, os, re, sys, time, html, subprocess, tempfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = 'https://ultimateframedata.com/'
CACHE = os.path.join(ROOT, '.cache', 'ufd')
OUT = os.path.join(ROOT, 'frame-data', 'super-smash-bros-ultimate.json')
ICONS = os.path.join(ROOT, 'frame-data', 'icons', 'super-smash-bros-ultimate')
CLIPS = os.path.join(ROOT, 'frame-data', 'clips', 'super-smash-bros-ultimate')
DELAY = 1.0  # one request a second: a community site

# page section -> move type; Kazuya's page splits ground attacks into several sections. Misc Info (stats, ledge
# options, get-up attacks without numbers) is left out.
SECTIONS = {'groundattacks': 'ground', 'jabattacks': 'ground', 'tiltattacks': 'ground', 'inputattacks': 'ground',
            'crouchingattacks': 'ground', 'smashattacks': 'ground', 'dashattacks': 'ground',
            'aerialattacks': 'aerial', 'specialattacks': 'special', 'grabs': 'grab', 'dodges': 'dodge'}
# Olimar's values are per Pikmin colour
# links on the site that point at a missing file, and the file that exists
FIXED = {'hitboxes/dark_pit/PitGuardianOrbitarsAerial.gif': 'hitboxes/dark_pit/DarkPitGuardianOrbitarsAerial.gif'}
PIKMIN = {'rp': 'Red', 'yp': 'Yellow', 'bp': 'Blue', 'wp': 'White', 'pp': 'Purple'}


LAST = [0.0]


def fetch(name, url, binary=False):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        time.sleep(max(0.0, LAST[0] + DELAY - time.time()))
        req = urllib.request.Request(url.replace(' ', '%20'), headers={'User-Agent': 'game-animation-library frame-data import'})
        for i in range(4):
            try:
                with urllib.request.urlopen(req, timeout=90) as r: body = r.read()
                break
            except OSError:
                if i == 3: raise
                time.sleep(2 ** (i + 1))
        open(path, 'wb').write(body)
        LAST[0] = time.time()
    return path if binary else open(path, encoding='utf-8', errors='replace').read()


def text(v):
    v = re.sub(r'<div class="(rp|yp|bp|wp|pp)">([^<]*)(?:</div>)?', lambda m: f' {PIKMIN[m.group(1)][0]}{m.group(2)}', v)
    v = re.sub(r'<br\s*/?>', ' ', v)
    v = html.unescape(re.sub(r'<[^>]+>', '', v))
    v = re.sub(r'\s+', ' ', v).strip()
    return None if v in ('', '--', '-', '**', '***') else v


def first_int(v):
    m = re.search(r'-?\d+', v or '')
    return int(m.group()) if m else None


def value(v):
    """A number when the cell is one number, else the site's text (several hitboxes, ranges)."""
    if v is None: return None
    return int(v) if re.fullmatch(r'[+-]?\d+', v) else float(v) if re.fullmatch(r'[+-]?\d+\.\d+', v) else v


def windows(v):
    """Active windows from text such as 5—7, 6—9(10—25), 7(8—11), 4/7/10..., 11/15/19: every frame number or range,
    in order, merged where they touch. Parentheses mark later (weaker or lingering) hitboxes; they are still active."""
    if not v: return []
    out = []
    for a, b in re.findall(r'(\d+)\s*(?:[—–-]\s*(\d+))?', v):
        a, b = int(a), int(b or a)
        if b < a or b > 600: continue
        out.append([a, b])
    out.sort()
    merged = []
    for s, e in out:
        if merged and s <= merged[-1][1] + 1: merged[-1][1] = max(merged[-1][1], e)
        else: merged.append([s, e])
    return merged


def noted(notes, *words):
    """Frame windows the notes give for a property, e.g. 'Intangible on frame 3-21', 'heavy armor (4%) on frame 7-9'."""
    out = []
    for rest in re.findall(r'(?:%s)\w*[^.;]*?\bframes?\s*(\d[\d\s,/—–-]*(?:\s*(?:and|&)\s*\d[\d—–-]*)*)' % '|'.join(words), notes or '', re.I):
        out += windows(rest)
    return sorted(out)


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def grip(mtype, name):
    if mtype == 'aerial': return 'air'
    if re.search(r'\bair\b|aerial|\(air', name, re.I) and not re.search(r'air(borne)? dodge', name, re.I) or re.search(r'air dodge', name, re.I):
        return 'air'
    return 'ground'


def roster():
    page = fetch('smash.html', BASE + 'smash')
    return [(s, n) for n, s in re.findall(r'<a title="([^"]+)" href="/?([a-z_]+)"', page) if s != 'stats']


def clip_label(texts, names, i):
    if texts[i]: return texts[i]
    if len(names) == 1: return 'Hitboxes'
    pre = os.path.commonprefix(names)
    rest = names[i][len(pre):]
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', rest) or 'Default'


def clip(cslug, src):
    """The local WebP for one hitbox GIF: (file relative to CLIPS, frames), or None when not downloaded."""
    name = os.path.splitext(os.path.basename(src))[0]
    rel = f'{cslug}/{name}.webp'
    out = os.path.join(CLIPS, rel)
    if not os.path.exists(out): return None
    from PIL import Image
    return rel, Image.open(out).n_frames


def convert(gif, out, src):
    tmp = out[:-5] + '.part.webp'
    try:
        # fit in 440x280, keeping the site's slow-motion timing; a GIF frame is a game frame
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', gif, '-vf', "scale='min(440,iw)':'min(280,ih)':force_original_aspect_ratio=decrease:flags=lanczos",
                        '-loop', '0', '-c:v', 'libwebp', '-quality', '50', '-compression_level', '6', tmp], check=True)
        os.replace(tmp, out)
    except Exception as e:
        print('  skipped', src, e)
        if os.path.exists(tmp): os.remove(tmp)
    os.remove(gif)  # keep the cache small; the WebP is what we keep


def download_clips():
    """Every move's hitbox GIFs, one download at a time; conversions run alongside."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(3) as pool:
        for cslug, cname in roster():
            for mtype, f in parse(cslug, fetch(cslug + '.html', BASE + cslug)):
                for src in f['gifs']:
                    name = os.path.splitext(os.path.basename(src))[0]
                    out = os.path.join(CLIPS, cslug, name + '.webp')
                    if os.path.exists(out): continue
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    try:
                        gif = fetch(f'gif/{cslug}/{name}.gif', BASE + src, binary=True)
                    except OSError as e:
                        print('  missing', src, e); continue
                    pool.submit(convert, gif, out, src)
            print('clips:', cname, flush=True)


def parse(cslug, page):
    moves = []
    for sec in re.split(r'<h2 class="movecategory" id="', page)[1:]:
        mtype = SECTIONS.get(sec[:sec.find('"')])
        if not mtype: continue
        for mc in re.split(r'<div class="movecontainer', sec)[1:]:
            f = {}
            for k, v in re.findall(r'<div class="([a-z]+)">(.*?)</div>(?=\s*<div class="(?!rp"|yp"|bp"|wp"|pp")[a-z]+">|\s*</div>|\s*$)', mc, re.S):
                if k != 'hitbox': f.setdefault(k, text(v))
            if not f.get('movename'): continue
            hb = re.search(r'<div class="hitbox">(.*?)</div>', mc, re.S)
            gifs, texts = [], []
            if hb:
                for pre, src in re.findall(r'([^<>]*)<a class="hitboximg" data-featherlight="([^"]+)"', hb.group(1)):
                    if not src.lower().endswith('.gif'): continue
                    src = FIXED.get(src, src)
                    t = re.sub(r'\s+', ' ', html.unescape(pre)).strip()
                    gifs.append(src); texts.append('' if '*' in t else t)
            f['gifs'], f['texts'] = gifs, texts
            moves.append((mtype, f))
    return moves


def build():
    moves, classes = [], []
    for cslug, cname in roster():
        page = fetch(cslug + '.html', BASE + cslug)
        ids, n = set(), 0
        for mtype, f in parse(cslug, page):
            name = f['movename']
            mid = f'{cslug.replace("_", "-")}.{mtype}.{slug(name)}'
            while mid in ids: mid += '-2'
            ids.add(mid)
            active = windows(f.get('activeframes'))
            startup = first_int(f.get('startup'))
            if startup is None and active: startup = active[0][0]
            total = first_int(f.get('totalframes'))
            endlag = first_int(f.get('endlag'))
            notes = f.get('notes')
            recovery = endlag if endlag is not None else (total - active[-1][1] if total and active and total > active[-1][1] else None)
            names = [os.path.splitext(os.path.basename(g))[0] for g in f['gifs']]
            clips = []
            for i, g in enumerate(f['gifs']):
                c = clip(cslug, g)
                if c: clips.append({'file': c[0], 'frames': c[1], 'label': clip_label(f['texts'], names, i), 'source': BASE + g})
            extra = {}
            for k, label in [('whichhitbox', 'Values are for'), ('shieldlag', 'Shield lag'), ('hopsautocancel', 'Autocancels from'),
                             ('hopsactionable', 'Actionable before landing from'), ('notes', 'Notes')]:
                if f.get(k): extra[label] = f[k]
            if f.get('startup') and not re.fullmatch(r'\d+', f['startup']): extra['Startup (as listed)'] = f['startup']
            if f.get('activeframes') and not re.fullmatch(r'\d+(—\d+)?', f['activeframes']): extra['Active frames (as listed)'] = f['activeframes']
            if f.get('totalframes') and not re.fullmatch(r'\d+', f['totalframes']): extra['Total frames (as listed)'] = f['totalframes']
            m = {'id': mid, 'class': cslug.replace('_', '-'), 'type': mtype, 'grip': grip(mtype, name), 'name': name,
                 'startup': startup, 'active': active, 'activeFrames': sum(e - s + 1 for s, e in active) or None,
                 'hits': len(active), 'recovery': recovery, 'total': total, 'cancels': {}, 'armor': noted(notes, 'armor'),
                 'iframes': noted(notes, 'Intangib', 'Invincib', 'Invulnerab'), 'parryable': True, 'blockAdv': value(f.get('advantage')),
                 'landingLag': value(f.get('landinglag')), 'shieldStun': value(f.get('shieldstun')),
                 'damage': {'amount': value(f.get('basedamage'))}, 'weapons': [], 'default': True,
                 'url': f'{BASE}{cslug}', 'extra': extra or None}
            if not m['extra']: del m['extra']
            if clips: m['clips'] = clips
            moves.append(m); n += 1
        classes.append({'id': cslug.replace('_', '-'), 'name': cname, 'family': 'roster', 'icon': cname, 'weapons': [], 'moves': n})
        print(f'{cname}: {n} moves')
    return {
        'schema': 'frame-data/1',
        'game': {'id': 'super-smash-bros-ultimate', 'name': 'Super Smash Bros. Ultimate', 'fps': 60, 'version': 'Ultimate Frame Data',
                 'frameNote': 'Frames are game frames at 60 fps, 1-based: startup is the first frame a hitbox is out. On shield is '
                              'the advantage when the move hits a shield on its first active frame (shield drop is 11 frames, '
                              'jump, up B and up smash out of shield skip it). Several values split by / are for different hitboxes.'},
        'source': {'name': 'Ultimate Frame Data', 'url': BASE + 'smash', 'author': 'MetalMusicMan', 'retrieved': time.strftime('%Y-%m-%d'),
                   'method': 'import_ufd_ssbu.py', 'moveName': 'Ultimate Frame Data',
                   'note': 'Super Smash Bros. Ultimate frame data and hitbox GIFs from Ultimate Frame Data by MetalMusicMan, with '
                           'Zeckemyro and the contributors credited there. The hitbox GIFs are the site\'s, made from the game\'s footage '
                           '(Nintendo); every move links back to its character page.',
                   'links': [{'name': 'Ultimate Frame Data', 'url': BASE + 'smash'}, {'name': 'Support UFD', 'url': 'https://ko-fi.com/MetalMusicMan'},
                             {'name': 'Importer', 'url': 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_ufd_ssbu.py'}]},
        'labels': {'class': 'Character', 'classes': 'characters', 'allClasses': 'All characters', 'grip': 'Ground / air',
                   'allFamilies': 'All characters', 'search': 'Search moves, characters…', 'everyClass': 'Every character', 'patch': '',
                   'pickClass': 'Pick a character to see their moves by type with hitbox clips, or filter and sort the whole roster below.',
                   'classView': 'every move, by type. Click a move to step through its hitboxes.',
                   'recovery': 'Endlag: frames from the last active frame until the move ends'},
        'columns': ['name', 'class', 'strip', 'startup', 'active', 'recovery', 'total', 'landing', 'blockAdv', 'sstun', 'dmg'],
        'columnNames': {'recovery': 'Endlag', 'blockAdv': ['On shield', 'Frame advantage when the move hits a shield on its first active frame'],
                        'dmg': ['Damage', 'Base damage (1v1 multiplier not applied)']},
        'families': [{'id': 'roster', 'name': 'Roster'}],
        'classes': classes,
        'moveTypes': [
            {'id': 'ground', 'name': 'Ground attacks', 'description': 'Jabs, tilts, dash attack and smash attacks'},
            {'id': 'aerial', 'name': 'Aerials', 'description': 'Aerial attacks; landing lag is the lag when landing during the move'},
            {'id': 'special', 'name': 'Specials', 'description': 'Neutral, side, up and down B'},
            {'id': 'grab', 'name': 'Grabs and throws', 'description': 'Grabs, pummel and throws'},
            {'id': 'dodge', 'name': 'Dodges and rolls', 'description': 'Spot dodge, rolls and air dodges: length and intangibility'},
        ],
        'grips': [{'id': 'ground', 'name': 'Ground', 'short': 'Gnd'}, {'id': 'air', 'name': 'Air', 'short': 'Air'}],
        'moves': moves,
    }


def icons():
    """Each character's render from the site's character select, cropped to a 96px square (needs Pillow)."""
    from PIL import Image
    os.makedirs(ICONS, exist_ok=True)
    out = {}
    for cslug, cname in roster():
        url = f'{BASE}characterart/{cslug}.webp'
        path = os.path.join(ICONS, cslug.replace('_', '-') + '.webp')
        if not os.path.exists(path):
            img = Image.open(fetch(f'art/{cslug}.webp', url, binary=True)).convert('RGB')
            w, h = img.size
            side = min(w, h)
            top = max(0, min(h - side, int((h - side) * 0.25)))  # the site shows the art at centre 25%
            img.crop(((w - side) // 2, top, (w - side) // 2 + side, top + side)).resize((96, 96), Image.LANCZOS).save(path, quality=80)
        out[cname] = {'file': os.path.basename(path), 'source': url}
    json.dump({'sources': [{'name': 'Ultimate Frame Data', 'url': BASE + 'smash'}], 'lead': 'Character icons are the official renders',
               'note': 'Art (c) Nintendo and the characters\' owners.', 'icons': out}, open(os.path.join(ICONS, 'icons.json'), 'w'), indent=1)


if __name__ == '__main__':
    icons()
    if '--clips' in sys.argv: download_clips()
    d = build()
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('{\n' + ',\n'.join(f' {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}' for k, v in d.items() if k != 'moves'))
        f.write(',\n "moves": [\n' + ',\n'.join('  ' + json.dumps(m, ensure_ascii=False) for m in d['moves']) + '\n ]\n}\n')
    print('wrote', os.path.relpath(OUT, ROOT), os.path.getsize(OUT) // 1024, 'KB,', len(d['moves']), 'moves,',
          sum(1 for m in d['moves'] if m.get('clips')), 'with clips')

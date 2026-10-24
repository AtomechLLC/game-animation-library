"""Ninja Gaiden Black frame data and 2D preview for Ryu's Dragon Sword, read from the game disc. Read-only.

    python tools/frame_data/import_ngb_game.py "C:/Games/Ninja Gaiden Black.iso"
    python tools/frame_data/import_ngb_game.py <folder with cmn.afs and chr_ryu.afs>      # files already unpacked
    python tools/frame_data/import_ngb_game.py <iso> --no-sprites                          # frame data only

Writes frame-data/ninja-gaiden-black.json and frame-data/sprites/ninja-gaiden-black/. Needs numpy and Pillow.

Where the numbers come from (see frame-data/README.md, "Ninja Gaiden Black"):
  cmn.afs/ryu.mtn section 1 holds one timeline script per player state. '0 <frame>' waits for that frame of the
  state's motion; '0x0d slot state' switches an attack on (1) and off (0 or 4), slot 0 being the sword and 0x0c
  and up the feet; '9 1' / '9 0' open and close the combo input window that the game's input rules check before
  chaining to the next attack. Motions are cmn.afs/rm_kt.mot (Dragon Sword bank, motion 10000 + n of a script).
  Which state each input leads to was read from the input rules in ryu.chr (a small bytecode, interpreter at
  xbe 0x16300) and the names from the game's own technique list in default.xbe (.data, 0x436378).
"""
import argparse, datetime, io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import ngb_files as nf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME_ID = 'ninja-gaiden-black'
IMPORTER = 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_ngb_game.py'

# (script id, move id, name, input, type, grip, description). Inputs as the game's technique list writes them:
# X light, Y strong, 6 forward, ! hold, R block. The chains were traced through ryu.chr's input rules: state
# 0x1af (X) -> 0x1b0 -> 0x1b1 on X, 0x1b6 -> 0x1bf -> 0x1c0 on Y from the second hit, 0x1c3 on forward+X, ...
MOVES = [
    (400, 'x1', 'Crimson Slash (1st hit)', 'X', 'combo', 'ground', 'First swing of the basic combo'),
    (401, 'x2', 'Crimson Slash (2nd hit)', 'XX', 'combo', 'ground', 'Second swing'),
    (402, 'x3', 'Crimson Slash', 'XXX', 'combo', 'ground', 'Third swing, the end of the basic three-hit combo'),
    (409, 'xxxy', 'Dragon Tear', 'XXXY', 'combo', 'ground', 'Strong finisher after Crimson Slash'),
    (535, 'xxy', 'Tiger Roar', 'XXY', 'combo', 'ground', ''),
    (536, 'xxyy', 'Fang of the Wolf', 'XXYY', 'combo', 'ground', ''),
    (537, 'xxyyy', "Blade of the Dragon's Tail", 'XXYYY', 'combo', 'ground', 'Two-hit finisher'),
    (530, 'xx6x', 'Forward slash (XX6X)', 'XX6X', 'combo', 'ground', 'Opener of the XX6X strings'),
    (531, 'xx6xx', "Fiend's Bane Kick", 'XX6XX', 'combo', 'ground', 'A kick (foot hitbox)'),
    (410, 'xx6xy', 'Early Winter Rain', 'XX6XY', 'combo', 'ground', 'Three kicks'),
    (550, 'y', 'Blade of the Undefeatable', 'Y', 'combo', 'ground', 'Rising slash; after X it is the launcher of the XY air strings'),
    (431, '6x', 'Windmill Slash', '6X', 'combo', 'ground', 'Spinning slash'),
    (433, '6x.repeat', 'Windmill Slash (repeat)', '6X, X', 'combo', 'ground', 'Next spin while X is pressed again'),
    (420, 'run.x', 'Violent Wind', 'X while running', 'run', 'ground', ''),
    (538, 'run.xx', 'Violent Gale', 'XX while running', 'run', 'ground', ''),
    (551, 'xyx', 'Air slash (XYX)', 'XYX', 'air', 'air', 'First air slash after the launcher'),
    (552, 'xyxx', 'Air slash (XYXX)', 'XYXX', 'air', 'air', ''),
    (553, 'xyxxx', 'Air slash (XYXXX)', 'XYXXX', 'air', 'air', ''),
    (554, 'xyxxxx', 'Blade of Nirrti', 'XYXXXX', 'air', 'air', 'Diving finisher; the hitbox stays out until landing'),
    (573, 'xyxxxy', 'Izuna Drop', 'XYXXXY', 'air', 'air', 'The grab that starts the throw (attack code 0x15)'),
    (480, 'air.x', 'Blade of the Empty Air', 'X in a jump', 'air', 'air', ''),
    (484, 'flip.x', 'Air Destruction Slash', 'X in a flip', 'air', 'air', ''),
    (547, 'flip.y', 'Falling Dragon Blade', 'Y in a flip', 'air', 'air', 'The hitbox stays out until landing'),
    (1425, 'y.hold', 'Haze Straight Slash', 'Y!', 'ut', 'ground', 'Released without essence: five spinning hits'),
    (1427, 'y.et', 'Extinction Straight Slash', 'Y! (Essence Technique)', 'ut', 'ground', 'Same timing, with the ET effects'),
    (1429, 'y.ut', 'Hundred Wing Blade', 'Y! (Ultimate Technique)', 'ut', 'ground', 'Same timing, with the UT effects'),
    (1359, 'y.ut3', 'Storm of the Heavenly Dragon', 'Y! (Ultimate Technique, level 3)', 'ut', 'ground', 'Same timing, with the level 3 UT effects'),
]
TYPES = [('combo', 'Ground strings', 'X / Y strings on the ground, by the game\'s technique list'),
         ('run', 'Running', 'Attacks out of a run'),
         ('air', 'Air', 'Jump, flip and launcher strings'),
         ('ut', 'Charged', 'Hold Y: Ultimate Technique family, timed from the release')]

FPS = 60
SCALE = 90                      # preview pixels per metre


def frame_data(scr, kt, ryu_bank):
    rows = []
    for sid, mid, name, inp, typ, grip, desc in MOVES:
        w = scr[sid]
        evs = nf.events(w)
        motion = w[1]
        bank, m = (kt, motion - 10000) if motion >= 10000 else (ryu_bank, motion)
        length = bank.length(m) if bank.has(m) else None
        last_ev = max([f for f, _ in evs] + [0])
        total = length or last_ev
        wins = []
        for slot, on, off in nf.attack_windows(evs):
            if on == 0 and off == 0:
                continue
            wins.append((slot, on + 1, off if off is not None else total))
        active = [[a, b] for _, a, b in wins if b >= a]
        combo = nf.combo_windows(evs)
        r = {'id': mid, 'class': 'dragonSword', 'type': typ, 'grip': grip, 'name': name, 'input': inp,
             'startup': active[0][0] if active else None, 'active': active,
             'activeFrames': sum(b - a + 1 for a, b in active), 'hits': len(active),
             'recovery': (total - active[-1][1]) if active and total else None, 'total': total,
             'cancels': {'attack': combo[0][0] + 1} if combo else {},
             'armor': [], 'iframes': [], 'parryable': None, 'damage': {}, 'weapons': [], 'default': True,
             'desc': desc,
             'extra': {'Script': '%d (motion %d%s)' % (sid, motion, ' of rm_kt.mot' if motion >= 10000 else ' of ryu.mtn'),
                       'Hitbox slots': ', '.join(sorted({'sword' if s == 0 else 'foot 0x%x' % s for s, _, _ in wins})) or '—',
                       'Combo window': ', '.join('%d–%s' % (a + 1, b if b is not None else 'end') for a, b in combo) or '—'}}
        if any(off is None for _, _, off in nf.attack_windows(evs)):
            r['extra']['Note'] = 'The hitbox stays out to the end of the script (until landing for air moves)'
        rows.append((r, sid, bank, m, wins))
    return rows


# ---------------------------------------------------------------- preview sheets

def capsule(a, b, r, n=6):
    """2D capsule outline (list of points) around segment a-b."""
    a, b = np.array(a, float), np.array(b, float)
    d = b - a
    ang = np.arctan2(d[1], d[0]) if np.linalg.norm(d) > 1e-6 else 0.0
    pts = []
    for i in range(n + 1):
        t = ang - np.pi / 2 - np.pi * i / n
        pts.append(a + r * np.array([np.cos(t), np.sin(t)]))
    for i in range(n + 1):
        t = ang + np.pi / 2 - np.pi * i / n
        pts.append(b + r * np.array([np.cos(t), np.sin(t)]))
    return pts


def render_move(T, bank, m, total, wins):
    """One frame per tab frame (pose at the end of the frame), side view facing right. Returns (sheet, cell w, h,
    cols, per-frame boxes)."""
    from PIL import Image, ImageDraw
    if not bank.has(m):
        return None
    tracks = bank.tracks(m)
    poses = [nf.pose(T, tracks, min(f, total)) for f in range(1, total + 1)]
    proj = lambda p: np.array([p[2], p[1]])                    # (forward, up) in metres
    pts = []
    for P in poses:
        h, t = nf.blade(P)
        pts += [proj(P[k]) for k in ('root', 'spine', 'headtop')] + [proj(x) for k in ('rarm', 'larm', 'rleg', 'lleg') for x in P[k]]
        pts += [proj(h), proj(t)]
    pts = np.array(pts)
    lo = pts.min(0) - 0.15; hi = pts.max(0) + 0.15
    lo[1] = min(lo[1], -0.05)
    w, h = int((hi[0] - lo[0]) * SCALE) + 1, int((hi[1] - lo[1]) * SCALE) + 1
    px = lambda p: (float((p[0] - lo[0]) * SCALE), float((hi[1] - p[1]) * SCALE))
    cols = max(1, min(len(poses), 2400 // max(w, 1)))
    rows = (len(poses) + cols - 1) // cols
    sheet = Image.new('RGBA', (cols * w, rows * h), (0, 0, 0, 0))
    boxes = []
    for i, P in enumerate(poses):
        f = i + 1
        cell = Image.new('RGBA', (w * 2, h * 2), (0, 0, 0, 0))            # drawn at 2x, then reduced
        dr = ImageDraw.Draw(cell)
        q = lambda p: tuple(2 * c for c in px(proj(p)))
        line = lambda a, b, col, wd: dr.line([q(a), q(b)], fill=col, width=wd, joint='curve')
        gy = q(np.array([0, 0, 0]))[1]
        dr.line([(0, gy), (w * 2, gy)], fill=(120, 120, 120, 160), width=2)
        far, near, body = (125, 150, 195, 255), (85, 120, 185, 255), (65, 85, 135, 255)
        for k in ('larm', 'lleg'):
            b_, m_, e_ = P[k]; line(b_, m_, far, 14); line(m_, e_, far, 12)
        line(P['root'], P['spine'], body, 22); line(P['spine'], P['head'], body, 16)
        hc = q((P['head'] + P['headtop']) / 2)
        dr.ellipse([hc[0] - 15, hc[1] - 17, hc[0] + 15, hc[1] + 17], fill=body)
        for k in ('rleg', 'rarm'):
            b_, m_, e_ = P[k]; line(b_, m_, near, 15); line(m_, e_, near, 13)
        hand, tip = nf.blade(P)
        line(hand, tip, (215, 220, 230, 255), 5)
        line(hand, hand + (tip - hand) * 0.18, (30, 30, 30, 255), 7)
        fb = []
        for slot, a, b in wins:
            if a <= f <= b:
                if slot == 0:
                    seg = (proj(hand + (tip - hand) * 0.15), proj(tip)); r = 0.07
                else:
                    leg = P['rleg'] if slot == 0x0c else P['lleg']
                    seg = (proj(leg[1]), proj(leg[2])); r = 0.1
                poly = [px(p) for p in capsule(seg[0], seg[1], r)]
                fb.append(['a', [round(c, 1) for p in poly for c in p]])
        boxes.append(fb)
        cell = cell.resize((w, h), Image.LANCZOS)
        sheet.paste(cell, ((i % cols) * w, (i // cols) * h))
    return sheet, w, h, cols, boxes


def write_icon(sdir, mv, frame):
    """Dragon Sword icon: one preview frame (mid-swing) fitted in 96 px."""
    from PIL import Image
    sheet = Image.open(os.path.join(sdir, mv['sheet']))
    i = frame - 1
    cell = sheet.crop(((i % mv['cols']) * mv['w'], (i // mv['cols']) * mv['h'], (i % mv['cols'] + 1) * mv['w'], (i // mv['cols'] + 1) * mv['h']))
    cell = cell.crop(cell.getbbox())
    cell.thumbnail((92, 92), Image.LANCZOS)
    icon = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
    icon.paste(cell, ((96 - cell.width) // 2, (96 - cell.height) // 2))
    idir = os.path.join(ROOT, 'frame-data', 'icons', GAME_ID)
    os.makedirs(idir, exist_ok=True)
    icon.save(os.path.join(idir, 'dragonSword.webp'), 'WEBP', quality=80)
    with open(os.path.join(idir, 'icons.json'), 'w') as f:
        json.dump({'lead': 'The icon is a frame of the preview figure',
                   'note': 'Posed from Team Ninja\'s animation data.',
                   'icons': {'Dragon Sword': {'file': 'dragonSword.webp'}}}, f, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', help='disc image (.iso) or a folder holding cmn.afs and chr_ryu.afs')
    ap.add_argument('--no-sprites', action='store_true')
    args = ap.parse_args()
    disc = nf.Disc(args.source)
    cmn = nf.afs(disc.read('cmn.afs'))
    mtn = cmn['ryu.mtn']
    scr = nf.scripts(mtn)
    kt = nf.Bank(cmn['rm_kt.mot'])
    sec = nf.sections(mtn)
    ryu_bank = nf.Bank(mtn, sec[0], sec[1])
    rows = frame_data(scr, kt, ryu_bank)
    moves = [r for r, *_ in rows]
    today = datetime.date.today().isoformat()
    out = {
        'schema': 'frame-data/1',
        'game': {'id': GAME_ID, 'name': 'Ninja Gaiden Black', 'fps': FPS, 'version': 'Xbox, USA (5443000D)',
                 'frameNote': 'Frames are 1/60 s, 1-based, as the game counts them in its move scripts: an attack switched on at '
                              'script frame N is active from frame N + 1. Total is the length of the move\'s animation; '
                              'recovery is total minus the last active frame (the game has no separate dodge-cancel marker '
                              'that was decoded yet). → Attack is when the combo input window opens.'},
        'source': {'name': 'Ninja Gaiden Black game files', 'url': IMPORTER, 'author': 'Team Ninja', 'retrieved': today,
                   'method': 'import_ngb_game.py',
                   'note': 'Read straight from the disc: Ryu\'s move scripts (ryu.mtn), Dragon Sword motions (rm_kt.mot) and '
                           'input rules (ryu.chr), names from the technique list in default.xbe. The preview is a figure '
                           'posed from the game\'s animation (IK limbs from the motion\'s end-effectors) with the sword '
                           'placed along the right hand; the model itself is not drawn.',
                   'links': [{'name': 'Importer', 'url': IMPORTER},
                             {'name': 'Ninja Gaiden Black Recompiled (toolkit used to read the code)', 'url': 'https://github.com/gamboozino/ngbrecomp'}]},
        'labels': {'class': 'Weapon', 'classes': 'weapons', 'allClasses': 'All weapons', 'grip': 'Where',
                   'allFamilies': 'All weapons', 'everyClass': 'Every weapon', 'patch': '',
                   'pickClass': 'Pick a weapon to see its moves by type.', 'classView': 'every move, by type.',
                   'recovery': 'Frames from the last active frame to the end of the animation'},
        'columns': ['name', 'input'],
        'columnNames': {'attack': ['→ Attack', 'First frame the combo input window is open']},
        'families': [{'id': 'ryu', 'name': 'Ryu Hayabusa'}],
        'classes': [{'id': 'dragonSword', 'name': 'Dragon Sword', 'family': 'ryu', 'icon': 'Dragon Sword',
                     'weapons': [], 'moves': len(moves)}],
        'moveTypes': [{'id': i, 'name': n, 'description': d} for i, n, d in TYPES],
        'grips': [{'id': 'ground', 'name': 'Ground', 'short': 'Ground'}, {'id': 'air', 'name': 'Air', 'short': 'Air'}],
        'moves': moves,
    }
    path = os.path.join(ROOT, 'frame-data', GAME_ID + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('wrote', path, len(moves), 'moves')
    if args.no_sprites:
        return
    T, _ = nf.kmd_skeleton(nf.afs(disc.read('chr_ryu.afs'))['ryu.kmd'])
    sdir = os.path.join(ROOT, 'frame-data', 'sprites', GAME_ID)
    os.makedirs(os.path.join(sdir, 'sheets'), exist_ok=True)
    os.makedirs(os.path.join(sdir, 'moves'), exist_ok=True)
    mv, done = {}, {}
    for r, sid, bank, m, wins in rows:
        key = (id(bank), m, r['total'], tuple(wins))       # the UT family shares one animation and timing
        if key not in done:
            res = render_move(T, bank, m, r['total'], [(s, a, b) for s, a, b in wins])
            if not res:
                continue
            sheet, w, h, cols, boxes = res
            name = 'sheets/%s.webp' % r['id']
            sheet.save(os.path.join(sdir, name), 'WEBP', quality=70, method=4)
            done[key] = (name, w, h, cols, boxes)
        name, w, h, cols, boxes = done[key]
        mv[r['id']] = {'sheet': name, 'w': w, 'h': h, 'cols': cols, 'frames': boxes}
        print('  sheet', r['id'], len(boxes), 'frames')
    write_icon(sdir, mv['x2'], 13)
    with open(os.path.join(sdir, 'moves', 'dragonSword.json'), 'w') as f:
        json.dump({'moves': mv}, f, separators=(',', ':'))
    with open(os.path.join(sdir, 'sprites.json'), 'w') as f:
        json.dump({'fps': FPS, 'smooth': True, 'kinds': {'a': 'Attack'},
                   'source': {'name': 'Ninja Gaiden Black game files (figure posed from the game\'s animation)', 'url': IMPORTER, 'author': 'Team Ninja'},
                   'classes': {'dragonSword': {'file': 'moves/dragonSword.json'}}}, f, indent=1)


if __name__ == '__main__':
    main()

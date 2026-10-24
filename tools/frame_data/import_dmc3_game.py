"""Devil May Cry 3: Special Edition (PS2) frame data: Dante's moves, read from the game files. Read-only.

    python tools/frame_data/import_dmc3_game.py "<game folder with GData.afs>"      # or a folder of unpacked files

Writes frame-data/devil-may-cry-3.json and icons/devil-may-cry-3/ (the HUD's weapon and style icons). The 3D preview
files come from export_dmc3_models.py.

Where the numbers come from (see frame-data/README.md, "Devil May Cry 3"):
  The game's code starts each move by playing one or more of Dante's motion scripts (slot 5 of pl000.pac); which
  scripts each move plays is read off the executable's action dispatch (dmc3_moves.py). A script plays one motion
  of a motion pack (pl000_00_<n>.pac) from a start frame to its last frame at 60 fps; those spans added up are the
  move's total. The script also opens the next-action windows: the first frame it lets an attack, jump/roll,
  Royalguard block, style move or plain movement act is the cancel frame. When the hit comes out isn't in the
  scripts or any data file (the executable decides it), so startup, active frames and recovery are left unknown.
"""
import io, json, os, sys, datetime
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmc3_files as D
import dmc3_moves as M

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME_ID = 'devil-may-cry-3'
OUT = os.path.join(ROOT, 'frame-data', GAME_ID + '.json')
ICONS = os.path.join(ROOT, 'frame-data', 'icons', GAME_ID)

# HUD icons: id100.pac slot per class (texture slot; the model slot after it places it on screen). Same slots as the
# Crimson mod's HUD.cpp: weapons 42-50 and 30-38, styles 18-28 (Royalguard 24)
HUD_SLOTS = {'rebellion': 42, 'cerberus': 44, 'agni-rudra': 46, 'nevan': 48, 'beowulf': 50, 'ebony-ivory': 30,
             'shotgun': 32, 'artemis': 34, 'spiral': 36, 'kalina-ann': 38, 'royalguard': 24}


def icons(game):
    """96 px WebP per class from the HUD's icons, cropped to the picture and centred; returns {class name: file}."""
    os.makedirs(ICONS, exist_ok=True)
    hud = D.subfiles(game.read('id100.pac'))
    out = {}
    for cid, slot in HUD_SLOTS.items():
        a = D.textures(hud[slot])[0]
        ys, xs = np.nonzero(a[..., 3] > 16)
        if cid == 'royalguard': ys, xs = ys[ys >= 40], xs[ys >= 40]      # drop the rank arc above the emblem
        im = Image.fromarray(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], 'RGBA')
        k = 92 / max(im.size)
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
        sq = Image.new('RGBA', (96, 96))
        sq.alpha_composite(im, ((96 - im.width) // 2, (96 - im.height) // 2))
        sq.save(os.path.join(ICONS, cid + '.webp'), 'WEBP', quality=90)
        out[M.CLASSES[cid][0]] = {'file': cid + '.webp'}
    with open(os.path.join(ICONS, 'icons.json'), 'w', encoding='utf-8') as f:
        json.dump({'lead': "Icons are the game's own HUD art", 'note': 'Art (c) Capcom.', 'icons': out}, f, indent=1,
                  ensure_ascii=False)
    return out


def main(game_dir):
    game = D.Game(game_dir)
    icon_names = icons(game)
    pac = D.subfiles(game.read('pl000.pac'))
    scripts, cols = D.Scripts(pac[5]), D.colliders(pac)
    moves = []
    for mv in M.moves():
        segs = M.segments(game, scripts, mv)
        total, cancels = M.timing(segs)
        hs = M.move_hits(mv, segs, cols, pac[11])
        win = M.windows(hs)
        style = M.STYLE_GROUPS.get(mv['scripts'][0][0])
        extra = {'Motion': ', '.join('pl000_00_%d.pac #%d, frames %d–%d' % (g['pack'], g['slot'], g['start'], g['end'])
                                     for g in segs),
                 'Script': ', '.join('%d-%d' % s[:2] + (' from %d' % s[2] if len(s) > 2 else '') for s in mv['scripts'])}
        if style: extra['Style'] = style
        moves.append({'id': mv['id'], 'class': mv['class'], 'type': mv['type'], 'grip': mv['grip'], 'name': mv['name'],
                      'startup': win[0][0] if win else None, 'active': win,
                      'activeFrames': sum(b - a + 1 for a, b in win) if win else None,
                      'hits': max(h['hit'] for h in hs) if hs else None,
                      'recovery': total - win[-1][1] if win else None,
                      'total': total, 'cancels': cancels, 'armor': [], 'iframes': [], 'parryable': None,
                      'damage': {}, 'anim': [mv['id'].replace('.', '-')], 'weapons': [], 'default': True,
                      'extra': extra, **({'desc': mv['desc']} if mv.get('desc') else {})})
    counts = {}
    for m in moves: counts[m['class']] = counts.get(m['class'], 0) + 1
    classes = [{'id': cid, 'name': name, 'family': fam, 'icon': name if name in icon_names else None, 'weapons': [],
                'moves': counts[cid]} for cid, (name, fam, pac, hand) in M.CLASSES.items() if cid in counts]
    out = {
        'schema': 'frame-data/1',
        'game': {'id': GAME_ID, 'name': "Devil May Cry 3: Special Edition", 'fps': 60,
                 'version': 'PS2, Europe (SLES-54186)',
                 'frameNote': "Devil May Cry 3 runs its motions at 60 fps. Total is the move's motions from the frame "
                              "the game starts them to their last frame; cancels are the first frame the move's "
                              "script lets the next attack, jump or roll, block, style move or movement act. Active "
                              "frames are when the script has a damaging hitbox switched on, for the frames it gives; "
                              "startup is the first of them and recovery the frames after the last. Hits counts the "
                              "times the script lets the move strike the same enemy again; Cerberus's swings come from "
                              "the weapon's own script. For moves that fire or throw something (guns, Sword Pierce, "
                              "Crystal, Thunder Bolt, Zodiac, Distortion) active marks the frame each shot leaves, and "
                              "hits counts shots; how soon it lands depends on the distance. Gun rates are level 1's."},
        'source': {'name': 'Devil May Cry 3 game files',
                   'url': 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_dmc3_game.py',
                   'author': 'Capcom', 'retrieved': datetime.date.today().isoformat(), 'method': 'import_dmc3_game.py',
                   'note': "Read from the PS2 game's GData.afs and executable (SLES_541.86): the executable's action code "
                           "names which of Dante's motion scripts each move plays, and the scripts give each move's "
                           "motion, length, cancel frames and when its hitboxes switch on and off."},
        'families': [{'id': f, 'name': n} for f, n in M.FAMILIES],
        'classes': classes,
        'moveTypes': [{'id': t, 'name': n, 'description': d} for t, n, d in M.MOVE_TYPES],
        'grips': [{'id': 'ground', 'name': 'Ground', 'short': 'Ground'}, {'id': 'air', 'name': 'Air', 'short': 'Air'}],
        'moves': moves,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(OUT, len(moves), 'moves')


if __name__ == '__main__':
    main(sys.argv[1])

"""Devil May Cry 3: Special Edition (PS2) frame data: Dante's moves, read from the game files. Read-only.

    python tools/frame_data/import_dmc3_game.py "<game folder with GData.afs>"      # or a folder of unpacked files

Writes frame-data/devil-may-cry-3.json. The 3D preview files come from export_dmc3_models.py.

Where the numbers come from (see frame-data/README.md, "Devil May Cry 3"):
  The game's code starts each move by playing one or more of Dante's motion scripts (slot 5 of pl000.pac); which
  scripts each move plays is read off the executable's action dispatch (dmc3_moves.py). A script plays one motion
  of a motion pack (pl000_00_<n>.pac) from a start frame to its last frame at 60 fps; those spans added up are the
  move's total. The script also opens the next-action windows: the first frame it lets an attack, jump/roll,
  Royalguard block, style move or plain movement act is the cancel frame. When the hit comes out isn't in the
  scripts or any data file (the executable decides it), so startup, active frames and recovery are left unknown.
"""
import json, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmc3_files as D
import dmc3_moves as M

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME_ID = 'devil-may-cry-3'
OUT = os.path.join(ROOT, 'frame-data', GAME_ID + '.json')


def main(game_dir):
    game = D.Game(game_dir)
    scripts = D.Scripts(D.subfiles(game.read('pl000.pac'))[5])
    moves = []
    for mv in M.moves():
        segs = M.segments(game, scripts, mv)
        total, cancels = M.timing(segs)
        style = M.STYLE_GROUPS.get(mv['scripts'][0][0])
        extra = {'Motion': ', '.join('pl000_00_%d.pac #%d, frames %d–%d' % (g['pack'], g['slot'], g['start'], g['end'])
                                     for g in segs),
                 'Script': ', '.join('%d-%d' % s for s in mv['scripts'])}
        if style: extra['Style'] = style
        moves.append({'id': mv['id'], 'class': mv['class'], 'type': mv['type'], 'grip': mv['grip'], 'name': mv['name'],
                      'startup': None, 'active': [], 'activeFrames': None, 'hits': None, 'recovery': None,
                      'total': total, 'cancels': cancels, 'armor': [], 'iframes': [], 'parryable': None,
                      'damage': {}, 'anim': [mv['id'].replace('.', '-')], 'weapons': [], 'default': True,
                      'extra': extra, **({'desc': mv['desc']} if mv.get('desc') else {})})
    counts = {}
    for m in moves: counts[m['class']] = counts.get(m['class'], 0) + 1
    classes = [{'id': cid, 'name': name, 'family': fam, 'icon': None, 'weapons': [],
                'moves': counts[cid]} for cid, (name, fam, pac, hand) in M.CLASSES.items() if cid in counts]
    out = {
        'schema': 'frame-data/1',
        'game': {'id': GAME_ID, 'name': "Devil May Cry 3: Special Edition", 'fps': 60,
                 'version': 'PS2, Europe (SLES-54186)',
                 'frameNote': "Devil May Cry 3 runs its motions at 60 fps. Total is the move's motions from the frame "
                              "the game starts them to their last frame; cancels are the first frame the move's "
                              "script lets the next attack, jump or roll, block, style move or movement act. When "
                              "the hit comes out is decided by the game's code, not its data files, so startup and "
                              "active frames aren't known yet."},
        'source': {'name': 'Devil May Cry 3 game files',
                   'url': 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_dmc3_game.py',
                   'author': 'Capcom', 'retrieved': datetime.date.today().isoformat(), 'method': 'import_dmc3_game.py',
                   'note': "Read from the PS2 game's GData.afs and executable (SLES_541.86): the executable's action code "
                           "names which of Dante's motion scripts each move plays, and the scripts give each move's "
                           "motion, length and cancel frames."},
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

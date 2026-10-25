"""Add Ninja Gaiden Black clips of Ryu's Dragon Sword moves, rendered from the Frame Data 2D preview's sheets, to library.json.

Each mapped move's frames come from frame-data/sprites/ninja-gaiden-black/ (written by tools/frame_data/import_ngb_game.py
from the game disc): a figure posed from the game's own animation with the sword's attack capsule (red) drawn on the
frames the move scripts switch it on, on a dark background, as a 60 fps animated WebP at gifs/<id>-ngb-<n>.webp
(host `Ninja Gaiden Black render`, page_url = the move in Move Explorer). Safe to rerun: records already present
(same page) are skipped. Needs Pillow.
"""
import json, os
from PIL import Image, ImageDraw
from blocklist import load, blocked

GAME, GAME_ID = 'Ninja Gaiden Black', 'ninja-gaiden-black'
BASE = os.path.join('frame-data', 'sprites', GAME_ID)
BG = (38, 40, 52)
COLORS = {'p': (47, 107, 255), 'a': (229, 36, 43)}

# animation id -> [(frame data move id, label)]
MAP = {
 'melee.light-attack-combo-string': [('x3', "Ryu's Crimson Slash, the Dragon Sword's third X"), ('xxyyy', "Ryu's Blade of the Dragon's Tail (XXYYY finisher)")],
 'melee.combo-finisher': [('xxxy', "Ryu's Dragon Tear (XXXY finisher)")],
 'melee.uppercut-launcher': [('y', "Ryu's Blade of the Undefeatable, the launcher of the XY air strings")],
 'melee.aerial-attack': [('xyx', "Ryu's first air slash after the launcher"), ('air.x', "Ryu's Blade of the Empty Air (jump X)")],
 'melee.plunging-downward-attack': [('xyxxxx', "Ryu's Blade of Nirrti, a diving air finisher")],
 'melee.spin-attack': [('6x', "Ryu's Windmill Slash")],
 'melee.kick': [('xx6xx', "Ryu's Fiend's Bane Kick"), ('xx6xy', "Ryu's Early Winter Rain, three kicks")],
 'melee.sprint-attack': [('run.x', "Ryu's Violent Wind, X while running")],
 'melee.charged-attack': [('y.hold', "Ryu's Haze Straight Slash, released after holding Y")],
 'magic.ultimate-super-ability': [('y.ut', "Ryu's Hundred Wing Blade (Ultimate Technique) timing")],
}

def render(cls, mid, out):
    m = json.load(open(os.path.join(BASE, 'moves', cls + '.json')))['moves'][mid]
    sheet = Image.open(os.path.join(BASE, m['sheet'])).convert('RGBA')
    frames = []
    for i, boxes in enumerate(m['frames']):
        cx, cy = (i % m['cols']) * m['w'], (i // m['cols']) * m['h']
        img = Image.new('RGBA', (m['w'], m['h']), BG + (255,))
        img.alpha_composite(sheet.crop((cx, cy, cx + m['w'], cy + m['h'])))
        img = img.convert('RGB')                  # ImageDraw only blends translucent fills onto RGB
        d = ImageDraw.Draw(img, 'RGBA')
        for b in boxes:
            rgb = COLORS.get(b[0], (230, 190, 0))
            if isinstance(b[1], list):
                d.polygon([(b[1][j], b[1][j + 1]) for j in range(0, len(b[1]), 2)], fill=rgb + (60,), outline=rgb + (255,))
            else:
                d.rectangle(b[1:], fill=rgb + (60,), outline=rgb + (255,))
        frames.append(img)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=round(1000 / 60), loop=0, quality=85, method=6)
    return len(frames)


if __name__ == '__main__':
    import sys
    REDRAW = '--redraw' in sys.argv          # re-render clips already in the library
    fd = {m['id']: m for m in json.load(open(os.path.join('frame-data', GAME_ID + '.json'), encoding='utf-8'))['moves']}
    d = json.load(open('library.json', encoding='utf-8'))
    byid = {a['id']: a for a in d['animations']}
    bl = load()
    scr = json.load(open('gif-screening.json', encoding='utf-8'))
    rendered, added = {}, []
    for key, moves in MAP.items():
        aid = key.split('#')[0]
        a = byid[aid]
        a.setdefault('gifs', [])
        n = sum(1 for g in a['gifs'] if g.get('local', '').startswith(f'gifs/{aid}-ngb-'))
        for mid, label in moves:
            page = 'move-explorer.html#g=%s&c=%s&t=%s&m=%s' % (GAME_ID, fd[mid]['class'], fd[mid]['type'], mid)
            local = f'gifs/{aid}-ngb-{n}.webp'
            same = (page, page.replace('move-explorer.html', 'frame-data.html', 1))   # records written before the rename
            if any(g.get('page_url') in same for g in a['gifs'] + a.get('rejected_gifs', [])):
                if REDRAW: render(fd[mid]['class'], mid, next(g['local'] for g in a['gifs'] if g.get('page_url') in same))
                continue
            count = render(fd[mid]['class'], mid, local)
            conf = 'low'                        # a posed figure, not the game's model
            game = GAME
            g = {'page_url': page, 'media_url': '', 'title': f'{label}, with hitboxes, rendered from the Frame Data preview',
                 'game': game, 'host': game + ' render', 'local': local, 'source_url': '',
                 'screened': {'verdict': 'added', 'confidence': conf, 'what': f'{label}: figure posed from the game animation with the sword hitbox'}}
            if blocked(bl, g, open(local, 'rb').read()):
                os.remove(local)
                continue
            a['gifs'].append(g)
            scr['added'].append({'animation': aid, 'clip': local[5:-5], 'game': game, 'what': g['screened']['what'], 'confidence': conf})
            added.append((aid, local, count))
            n += 1
    json.dump(d, open('library.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    json.dump(scr, open('gif-screening.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for x in added: print(*x)
    print('added', len(added))

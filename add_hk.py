"""Add Hollow Knight clips of the Knight and bosses, rendered from the Frame Data 2D preview's sheets, to library.json.

Each mapped move's frames come from frame-data/sprites/hollow-knight/ (written by tools/frame_data/import_hk_game.py
from the installed game): the game's sprites with the move's hurtbox (blue) and attack polygons (red) drawn on, on
a dark background, as a 60 fps animated WebP at gifs/<id>-hk-<n>.webp (host `Hollow Knight render`, page_url = the
move in the Frame Data tab). Safe to rerun: records already present (same local file) are skipped. Needs Pillow.
"""
import json, os
from PIL import Image, ImageDraw
from blocklist import load, blocked

GAME, GAME_ID = 'Hollow Knight', 'hollow-knight'
BASE = os.path.join('frame-data', 'sprites', GAME_ID)
BG = (38, 40, 52)
COLORS = {'p': (47, 107, 255), 'a': (229, 36, 43)}

# animation id -> [(frame data move id, label)]
MAP = {
 'melee.light-attack': [('knight.nail.slash', 'Knight nail slash')],
 'melee.light-attack-combo-string': [('knight.nail.altSlash', 'Knight alternate nail slash (the second of the alternating swings)')],
 'melee.horizontal-sweep': [('knight.nail.slash', 'Knight nail slash')],
 'vfx.weapon-trail-slash-arc': [('knight.nail.slash', 'Knight nail slash and its slash arc')],
 'melee.aerial-attack': [('knight.nail.upSlash', 'Knight up slash'), ('knight.nail.wallSlash', 'Knight wall slash')],
 'melee.plunging-downward-attack': [('knight.nail.downSlash', 'Knight down slash (pogo)')],
 'melee.charged-attack': [('knight.nailArt.greatSlash', 'Knight Great Slash, released after the charge')],
 'melee.weapon-art-skill-attack': [('knight.nailArt.greatSlash', 'Knight Great Slash nail art')],
 'melee.dash-attack-lunge': [('knight.nailArt.dashSlash', 'Knight Dash Slash nail art')],
 'melee.spin-attack': [('knight.nailArt.cycloneSlash', 'Knight Cyclone Slash nail art')],
 'magic.projectile-cast-fireball': [('knight.spell.vengefulSpirit', 'Knight Vengeful Spirit'), ('knight.spell.shadeSoul', 'Knight Shade Soul')],
 'magic.spell-cast-instant': [('knight.spell.vengefulSpirit', 'Knight Vengeful Spirit')],
 'melee.ground-pound': [('knight.spell.desolateDive', 'Knight Desolate Dive, cast from the ground')],
 'magic.area-of-effect-slam': [('knight.spell.descendingDark', 'Knight Descending Dark, cast from the ground')],
 'vfx.shockwave-ground-crack': [('knight.spell.desolateDive', 'Knight Desolate Dive shockwave')],
 'magic.shout-roar-ability': [('knight.spell.howlingWraiths', 'Knight Howling Wraiths'), ('knight.spell.abyssShriek', 'Knight Abyss Shriek')],
 'defense.dash': [('knight.movement.dash', 'Knight dash (Mothwing Cloak)'), ('knight.movement.shadowDash', 'Knight Shadow Dash, invulnerable')],
 'defense.air-dash': [('knight.movement.dash', 'Knight dash, usable in the air')],
 'locomotion.jump': [('knight.movement.jump', 'Knight full-height jump')],
 'locomotion.double-jump': [('knight.movement.doubleJump', 'Knight Monarch Wings double jump')],
 'locomotion.landing-soft-hard': [('knight.movement.hardLanding', 'Knight hard landing')],
 'magic.heal': [('knight.movement.focus', 'Knight Focus, healing one mask')],
 'magic.spell-channel': [('knight.movement.focus', 'Knight Focus (channelled heal)')],
 'reactions.light-flinch-hit-react': [('knight.movement.hit', 'Knight taking a hit, then invulnerable')],
 'reactions.knockback': [('knight.movement.hit', 'Knight knocked back by a hit')],
 'death.death-collapse': [('knight.movement.death', 'Knight death')],
 # bosses
 'melee.dash-attack-lunge#2': [('hornet.attack.lunge', 'Hornet lunge')],
 'enemies.attack-telegraph-windup': [('hornet.attack.lunge', 'Hornet lunge, from its wind-up'), ('pureVessel.attack.dash', 'Pure Vessel dash stab, from its wind-up')],
 'melee.spin-attack#2': [('hornet.attack.spin', 'Hornet whirl')],
 'melee.weapon-throw-recall': [('hornet.attack.throw', 'Hornet needle throw and recall')],
 'ranged.boomerang-returning-throw': [('mantisLord.attack.throw', 'Mantis Lord boomerang throw (boomerang not shown)')],
 'melee.light-attack-combo-string#2': [('pureVessel.attack.slashes', 'Pure Vessel triple slash')],
 'melee.thrust-stab': [('pureVessel.attack.dash', 'Pure Vessel dash stab')],
 'defense.counter-attack': [('pureVessel.attack.counterSlash', 'Pure Vessel counter slash')],
 'melee.horizontal-sweep#2': [('nkg.attack.slash', 'Nightmare King Grimm slash')],
 'enemies.charging-rush': [('nkg.attack.groundDash', 'Nightmare King Grimm ground dash'), ('mantisLord.attack.dash', 'Mantis Lord dash slash')],
 'defense.backstep-backflip': [('hornet.attack.evade', 'Hornet evade')],
 # Silksong's Hornet (a character of the Hollow Knight frame data)
 'melee.light-attack#3': [('silksong.hunter.slash', 'Silksong Hornet needle slash (Hunter crest)')],
 'melee.aerial-attack#3': [('silksong.hunter.upSlash', 'Silksong Hornet up slash')],
 'melee.plunging-downward-attack#2': [('silksong.hunter.downSpike', 'Silksong Hornet down spike (Hunter crest)')],
 'melee.dash-attack-lunge#3': [('silksong.hunter.dashStab', 'Silksong Hornet dash stab')],
 'melee.sprint-attack': [('silksong.hunter.dashStab', 'Silksong Hornet sprint attack (dash stab)')],
 'defense.dash#2': [('silksong.movement.dash', 'Silksong Hornet dash')],
 'locomotion.jump#2': [('silksong.movement.jump', 'Silksong Hornet full-height jump')],
 'locomotion.double-jump#2': [('silksong.movement.doubleJump', 'Silksong Hornet double jump')],
 'reactions.light-flinch-hit-react#2': [('silksong.movement.hit', 'Silksong Hornet taking a hit')],
 'death.death-collapse#2': [('silksong.movement.death', 'Silksong Hornet death')],
 'magic.heal#2': [('silksong.movement.bind', 'Silksong Hornet Bind (heal)')],
 # Silksong bosses
 'melee.dash-attack-lunge#4': [('lace.attack.charge', 'Lace lunge')],
 'melee.plunging-downward-attack#3': [('lace.attack.downstab', 'Lace down stab')],
 'melee.combo-finisher': [('lace.attack.comboSlash', 'Lace combo slash')],
 'melee.spin-attack#3': [('lace.attack.circleSlash', 'Lace circle slash'), ('lastJudge.attack.spin', 'Last Judge censer spin')],
 'melee.dual-wield-flurry': [('lace.attack.rapidSlash', 'Lace rapid air slash')],
 'melee.thrust-stab#2': [('phantom.attack.stabs', 'Phantom stab flurry')],
 'melee.weapon-throw-recall#2': [('phantom.attack.throw', 'Phantom pin throw')],
 'melee.ground-pound#2': [('phantom.attack.dragoon', 'Phantom dragoon drop')],
 'enemies.charging-rush#2': [('bellBeast.attack.charge', 'Bell Beast charge'), ('widow.attack.dashCharge', 'Widow charge')],
 'melee.whip-chain-lash': [('lastJudge.attack.spin', 'Last Judge censer swing')],
 'creature.insect-spider-crawl': [('widow.attack.dashCharge', 'Widow skittering charge')],
}
SILK = {'silksong', 'lace', 'bellBeast', 'lastJudge', 'phantom', 'widow', 'mossMother'}
LOWB = {'ranged.boomerang-returning-throw', 'creature.insect-spider-crawl', 'melee.whip-chain-lash'}
LOW = {'melee.horizontal-sweep', 'magic.spell-cast-instant', 'vfx.shockwave-ground-crack', 'defense.air-dash', 'reactions.knockback'}


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
        n = sum(1 for g in a['gifs'] if g.get('local', '').startswith(f'gifs/{aid}-hk-'))
        for mid, label in moves:
            page = 'frame-data.html#g=%s&c=%s&t=%s&m=%s' % (GAME_ID, fd[mid]['class'], fd[mid]['type'], mid)
            local = f'gifs/{aid}-hk-{n}.webp'
            if any(g.get('page_url') == page for g in a['gifs'] + a.get('rejected_gifs', [])):
                if REDRAW: render(fd[mid]['class'], mid, next(g['local'] for g in a['gifs'] if g.get('page_url') == page))
                continue
            count = render(fd[mid]['class'], mid, local)
            conf = 'low' if aid in LOW or aid in LOWB else 'high'
            game = 'Hollow Knight: Silksong' if mid.split('.')[0] in SILK else GAME
            g = {'page_url': page, 'media_url': '', 'title': f'{label}, with hitboxes, rendered from the Frame Data preview',
                 'game': game, 'host': game + ' render', 'local': local, 'source_url': '',
                 'screened': {'verdict': 'added', 'confidence': conf, 'what': f'{label}: game sprites with hurtbox and attack hitboxes'}}
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

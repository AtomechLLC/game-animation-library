"""Dante's moves in Devil May Cry 3: Special Edition, as the game's executable dispatches them.

The executable (SLES_541.86) runs one function per action id, and the ids match the community's ACTION_DANTE list
(DDMK / Crimson, Vars.hpp): REBELLION_COMBO_1_PART_1 = 1 and so on, read from the compare chain at 0x263160 that
calls each action's function. Each function plays motion scripts by (group, index) through 0x250870; MOVES lists, per
action, the scripts it plays in order (start, loop, finish), which dmc3_files.Scripts turns into motion files and
cancel frames. Where one function serves several ids (Stinger levels 1 and 2, the Royalguard releases) one row stands
for them. Actions whose motion is picked at run time from aim tables (the guns' aimed shots, Twosome Time) and the
Trickster, Quicksilver and Doppelganger moves (handled outside this dispatcher) aren't listed yet.
"""
import re

# class id: (name, family, weapon pac or None, hand)
CLASSES = {
    'rebellion':   ('Rebellion', 'melee', 'plwp_sword.pac', 'R'),
    'cerberus':    ('Cerberus', 'melee', 'plwp_nunchaku.pac', 'R'),
    'agni-rudra':  ('Agni & Rudra', 'melee', 'plwp_2sword.pac', 'R'),
    'nevan':       ('Nevan', 'melee', 'plwp_guitar.pac', 'R'),
    'beowulf':     ('Beowulf', 'melee', 'plwp_fight.pac', 'R'),
    'ebony-ivory': ('Ebony & Ivory', 'guns', 'plwp_gun.pac', 'R'),
    'shotgun':     ('Shotgun', 'guns', 'plwp_shotgun.pac', 'R'),
    'artemis':     ('Artemis', 'guns', 'plwp_laser.pac', 'R'),
    'spiral':      ('Spiral', 'guns', 'plwp_rifle.pac', 'R'),
    'kalina-ann':  ('Kalina Ann', 'guns', 'plwp_ladygun.pac', 'R'),
    'royalguard':  ('Royalguard', 'styles', None, 'R'),
}
FAMILIES = [('melee', 'Devil Arms'), ('guns', 'Guns'), ('styles', 'Styles')]
MOVE_TYPES = [
    ('combo', 'Combos', 'Ground combo strings, part by part'),
    ('move', 'Moves', 'Attacks any style can use'),
    ('swordmaster', 'Swordmaster', 'Swordmaster style attacks'),
    ('shot', 'Shots', 'Gun attacks any style can use'),
    ('gunslinger', 'Gunslinger', 'Gunslinger style attacks'),
    ('style', 'Style moves', 'Royalguard releases'),
]

# (action id, class, move type, grip, name, [scripts (group, index) in play order], description)
MOVES = [
    (1, 'rebellion', 'combo', 'ground', 'Combo I · 1', [(3, 3)], 'First slash; also opens Combo II'),
    (2, 'rebellion', 'combo', 'ground', 'Combo I · 2', [(3, 4)], ''),
    (3, 'rebellion', 'combo', 'ground', 'Combo I · 3', [(3, 5)], ''),
    (4, 'rebellion', 'combo', 'ground', 'Combo II · 2', [(3, 6)], 'After a pause in Combo I'),
    (5, 'rebellion', 'combo', 'ground', 'Combo II · 3', [(3, 7)], ''),
    (14, 'rebellion', 'move', 'ground', 'Million Stab', [(3, 8), (3, 9)], 'Mashed stabs, then the finishing thrust'),
    (7, 'rebellion', 'move', 'ground', 'Stinger', [(3, 14), (3, 15), (3, 16)],
     'Lunge, travel, thrust; level 2 travels farther on the same motions'),
    (10, 'rebellion', 'move', 'ground', 'High Time', [(3, 11)], 'Launcher'),
    (11, 'rebellion', 'move', 'ground', 'High Time (jump)', [(3, 13)], 'Holding melee: Dante follows into the air'),
    (6, 'rebellion', 'move', 'air', 'Helm Breaker', [(3, 10)], ''),
    (12, 'rebellion', 'move', 'ground', 'Kick 1', [(3, 29)], ''),
    (13, 'rebellion', 'swordmaster', 'ground', 'Drive', [(3, 17), (3, 18), (3, 19)], 'Charge, hold, release'),
    (16, 'rebellion', 'swordmaster', 'ground', 'Prop', [(13, 19)], ''),
    (24, 'rebellion', 'swordmaster', 'ground', 'Shredder', [(13, 12), (13, 13)], ''),
    (18, 'rebellion', 'swordmaster', 'ground', 'Kick 2', [(13, 11)], ''),
    (15, 'rebellion', 'swordmaster', 'ground', 'Sword Pierce', [(13, 0)], 'Throws Rebellion'),
    (23, 'rebellion', 'swordmaster', 'ground', 'Sword Pierce (return)', [(13, 15)], 'Catching Rebellion'),
    (19, 'rebellion', 'swordmaster', 'air', 'Aerial Rave · 1', [(13, 7)], ''),
    (20, 'rebellion', 'swordmaster', 'air', 'Aerial Rave · 2', [(13, 8)], ''),
    (21, 'rebellion', 'swordmaster', 'air', 'Aerial Rave · 3', [(13, 9)], ''),
    (22, 'rebellion', 'swordmaster', 'air', 'Aerial Rave · 4', [(13, 10)], ''),
    (17, 'rebellion', 'swordmaster', 'air', 'Divekick', [(13, 4), (13, 5)], ''),
    (200, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 1', [(13, 17)], ''),
    (201, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 2', [(3, 46)], ''),
    (202, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 3', [(3, 47)], ''),
    (203, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 4', [(3, 48)], ''),
    (204, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 5', [(3, 49)], ''),
    (205, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 6', [(3, 50)], ''),
    (206, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 7', [(3, 51)], ''),
    (207, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 8', [(3, 52), (3, 53)], ''),
    (208, 'rebellion', 'swordmaster', 'ground', 'Crazy Dance', [(13, 18), (13, 20)], ''),

    (30, 'cerberus', 'combo', 'ground', 'Combo I · 1', [(4, 3)], ''),
    (31, 'cerberus', 'combo', 'ground', 'Combo I · 2', [(4, 4)], ''),
    (32, 'cerberus', 'combo', 'ground', 'Combo I · 3', [(4, 5)], ''),
    (33, 'cerberus', 'combo', 'ground', 'Combo I · 4', [(4, 6)], ''),
    (34, 'cerberus', 'combo', 'ground', 'Combo I · 5', [(4, 7)], ''),
    (35, 'cerberus', 'combo', 'ground', 'Combo II · 3', [(4, 8)], ''),
    (36, 'cerberus', 'combo', 'ground', 'Combo II · 4', [(4, 10), (4, 26)], ''),
    (37, 'cerberus', 'move', 'ground', 'Windmill', [(4, 27), (4, 29), (4, 26)], ''),
    (38, 'cerberus', 'move', 'ground', 'Revolver', [(4, 19), (4, 25), (4, 24)], 'Levels 1 and 2 share the motions'),
    (40, 'cerberus', 'move', 'air', 'Swing', [(4, 11)], ''),
    (41, 'cerberus', 'move', 'ground', 'Satellite', [(4, 22), (4, 23)], ''),
    (42, 'cerberus', 'swordmaster', 'ground', 'Flicker', [(14, 0), (14, 1)], ''),
    (43, 'cerberus', 'swordmaster', 'air', 'Air Flicker', [(14, 7), (14, 8)], ''),
    (44, 'cerberus', 'swordmaster', 'ground', 'Crystal', [(14, 2)], ''),
    (45, 'cerberus', 'swordmaster', 'ground', 'Million Carats', [(14, 3), (14, 4)], ''),
    (46, 'cerberus', 'swordmaster', 'ground', 'Ice Age', [(14, 5), (14, 6)], ''),

    (50, 'agni-rudra', 'combo', 'ground', 'Combo I · 1', [(5, 3)], ''),
    (51, 'agni-rudra', 'combo', 'ground', 'Combo I · 2', [(5, 4)], ''),
    (52, 'agni-rudra', 'combo', 'ground', 'Combo I · 3', [(5, 5)], ''),
    (53, 'agni-rudra', 'combo', 'ground', 'Combo I · 4', [(5, 6)], ''),
    (54, 'agni-rudra', 'combo', 'ground', 'Combo I · 5', [(5, 7)], ''),
    (55, 'agni-rudra', 'combo', 'ground', 'Combo II · 2', [(5, 8)], ''),
    (56, 'agni-rudra', 'combo', 'ground', 'Combo II · 3', [(5, 9)], ''),
    (57, 'agni-rudra', 'combo', 'ground', 'Combo III · 3', [(5, 10), (5, 25)], ''),
    (58, 'agni-rudra', 'move', 'ground', 'Jet-Stream (level 1)', [(5, 20), (5, 21)], ''),
    (59, 'agni-rudra', 'move', 'ground', 'Jet-Stream (level 2)', [(5, 20), (5, 22)], ''),
    (60, 'agni-rudra', 'move', 'ground', 'Jet-Stream (level 3)', [(5, 20), (5, 23)], ''),
    (62, 'agni-rudra', 'move', 'ground', 'Whirlwind', [(5, 18)], 'Launcher'),
    (63, 'agni-rudra', 'move', 'ground', 'Whirlwind (jump)', [(5, 19)], 'Holding melee: Dante follows into the air'),
    (64, 'agni-rudra', 'move', 'ground', 'Million Slash', [(5, 11), (5, 26)], ''),
    (61, 'agni-rudra', 'move', 'air', 'Aerial Cross', [(5, 17)], ''),
    (65, 'agni-rudra', 'swordmaster', 'ground', 'Crossed Swords', [(15, 0)], ''),
    (66, 'agni-rudra', 'swordmaster', 'ground', 'Crawler', [(15, 1)], ''),
    (67, 'agni-rudra', 'swordmaster', 'ground', 'Twister', [(15, 2), (15, 3)], ''),
    (71, 'agni-rudra', 'swordmaster', 'ground', 'Tempest', [(15, 8), (15, 9)], ''),
    (68, 'agni-rudra', 'swordmaster', 'air', 'Sky Dance · 1', [(15, 4)], ''),
    (69, 'agni-rudra', 'swordmaster', 'air', 'Sky Dance · 2', [(15, 5)], ''),
    (70, 'agni-rudra', 'swordmaster', 'air', 'Sky Dance · 3', [(15, 6), (15, 7)], ''),

    (80, 'nevan', 'move', 'ground', 'Tune Up', [(6, 3)], ''),
    (81, 'nevan', 'combo', 'ground', 'Combo 1', [(6, 9)], ''),
    (82, 'nevan', 'combo', 'ground', 'Combo 2', [(6, 14)], ''),
    (83, 'nevan', 'move', 'ground', 'Jam Session', [(6, 11), (6, 12)], ''),
    (84, 'nevan', 'move', 'ground', 'Bat Rift', [(6, 16)], ''),
    (85, 'nevan', 'move', 'ground', 'Bat Rift (level 2)', [(6, 17), (6, 36)], ''),
    (86, 'nevan', 'move', 'ground', 'Reverb Shock', [(6, 21), (6, 19), (6, 20)], 'Levels 1 and 2 share the motions'),
    (88, 'nevan', 'move', 'air', 'Air Play', [(6, 15), (6, 34)], ''),
    (96, 'nevan', 'move', 'air', 'Thunder Bolt', [(6, 23)], ''),
    (95, 'nevan', 'move', 'air', 'Vortex', [(6, 25), (6, 26), (6, 27)], ''),
    (89, 'nevan', 'swordmaster', 'ground', 'Slash', [(16, 0)], ''),
    (92, 'nevan', 'swordmaster', 'ground', 'Feedback', [(16, 3), (16, 4)], ''),
    (93, 'nevan', 'swordmaster', 'ground', 'Crazy Roll', [(16, 5)], ''),
    (94, 'nevan', 'swordmaster', 'ground', 'Distortion', [(16, 9), (16, 10)], ''),
    (90, 'nevan', 'swordmaster', 'air', 'Air Slash · 1', [(16, 7)], ''),
    (91, 'nevan', 'swordmaster', 'air', 'Air Slash · 2', [(16, 8)], ''),

    (110, 'beowulf', 'combo', 'ground', 'Combo I · 1', [(7, 3)], ''),
    (111, 'beowulf', 'combo', 'ground', 'Combo I · 2', [(7, 4)], ''),
    (112, 'beowulf', 'combo', 'ground', 'Combo I · 3', [(7, 5)], ''),
    (113, 'beowulf', 'combo', 'ground', 'Combo II · 3', [(7, 7), (7, 8)], ''),
    (114, 'beowulf', 'combo', 'ground', 'Combo II · 4', [(7, 9)], ''),
    (115, 'beowulf', 'move', 'ground', 'Hyper Fist', [(7, 10), (7, 11)], ''),
    (117, 'beowulf', 'move', 'ground', 'Beast Uppercut', [(7, 14)], ''),
    (119, 'beowulf', 'move', 'ground', 'Rising Dragon', [(7, 15)], 'Charged Beast Uppercut'),
    (121, 'beowulf', 'move', 'ground', 'Straight', [(7, 30), (7, 31), (7, 32)], 'Levels 1 and 2 share the motions'),
    (116, 'beowulf', 'move', 'air', 'Killer Bee', [(7, 12), (7, 13)], ''),
    (120, 'beowulf', 'move', 'air', 'Rising Dragon (whirlwind)', [(7, 16), (7, 17)], ''),
    (123, 'beowulf', 'swordmaster', 'ground', 'Zodiac', [(17, 0)], ''),
    (124, 'beowulf', 'swordmaster', 'ground', 'Volcano', [(17, 1)], ''),
    (126, 'beowulf', 'swordmaster', 'ground', 'Tornado', [(17, 4), (17, 5)], ''),
    (127, 'beowulf', 'swordmaster', 'ground', 'The Hammer', [(17, 6)], ''),
    (128, 'beowulf', 'swordmaster', 'ground', 'Real Impact', [(17, 3)], ''),
    (125, 'beowulf', 'swordmaster', 'air', 'Air Volcano', [(17, 2), (17, 1)], ''),

    (136, 'ebony-ivory', 'gunslinger', 'ground', 'Wild Stomp', [(8, 33), (8, 34), (8, 39)], ''),
    (135, 'ebony-ivory', 'gunslinger', 'air', 'Rain Storm', [(18, 15), (18, 16), (18, 17)], ''),
    (144, 'shotgun', 'gunslinger', 'ground', 'Fireworks', [(19, 0)], ''),
    (146, 'shotgun', 'gunslinger', 'ground', 'Gun Stinger', [(19, 2), (19, 3), (19, 4)], ''),
    (147, 'shotgun', 'gunslinger', 'ground', 'Point Blank', [(19, 5)], ''),
    (145, 'shotgun', 'gunslinger', 'air', 'Air Fireworks', [(19, 1)], ''),
    (150, 'artemis', 'shot', 'ground', 'Normal Shot', [(10, 4)], 'Multi-lock shot plays the same motion'),
    (151, 'artemis', 'shot', 'air', 'Air Normal Shot', [(10, 13)], 'Air multi-lock shot plays the same motion'),
    (154, 'artemis', 'gunslinger', 'ground', 'Sphere', [(20, 2)], ''),
    (155, 'artemis', 'gunslinger', 'ground', 'Acid Rain', [(20, 3), (20, 4)], ''),
    (161, 'spiral', 'gunslinger', 'ground', 'Sniper', [(21, 0)], ''),
    (162, 'spiral', 'gunslinger', 'ground', 'Trick Shot', [(21, 1)], ''),
    (171, 'kalina-ann', 'gunslinger', 'ground', 'Hysteric', [(22, 2), (22, 3)], ''),
    (172, 'kalina-ann', 'gunslinger', 'ground', 'Grapple', [(22, 1)], ''),

    (190, 'royalguard', 'style', 'ground', 'Release', [(24, 15), (24, 16)], 'Levels 1 to 4 share the motions'),
    (194, 'royalguard', 'style', 'air', 'Air Release', [(24, 18), (24, 19)], 'Levels 1 to 4 share the motions'),
]

# motion groups in Swordmaster / Gunslinger packs
STYLE_GROUPS = {13: 'Swordmaster', 14: 'Swordmaster', 15: 'Swordmaster', 16: 'Swordmaster', 17: 'Swordmaster',
                18: 'Gunslinger', 19: 'Gunslinger', 20: 'Gunslinger', 21: 'Gunslinger', 22: 'Gunslinger',
                24: 'Royalguard'}


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def moves():
    """MOVES as dicts with their frame-data move id ('<class>.<name slug>')."""
    out = []
    for aid, cls, typ, grip, name, scripts, desc in MOVES:
        out.append({'action': aid, 'id': '%s.%s' % (cls, slug(name).replace('-·-', '-').replace('·', '')),
                    'class': cls, 'type': typ, 'grip': grip, 'name': name, 'scripts': scripts, 'desc': desc})
    return out


def motion_id(pack, slot):
    return 'g%02d-%02d' % (pack, slot)


def segments(game, scripts, move, _packs={}):
    """The motions a move plays, in order: [dict(pack, slot, mot, start, end, slots)]; start / end are the motion's
    own frames the script plays (from its 01, else the motion's start frame, to its last frame)."""
    import dmc3_files as D
    out = []
    for grp, idx in move['scripts']:
        r = scripts.run(grp, idx)
        pack, slot = r['motion']
        if pack not in _packs: _packs[pack] = D.subfiles(game.read('pl000_00_%d.pac' % pack))
        mot = D.motion(_packs[pack][slot])
        start = int(round(mot['start'])) if r['start'] is None else r['start']
        out.append(dict(pack=pack, slot=slot, mot=mot, start=start, end=int(round(mot['frames'])), slots=r['slots']))
    return out


# frame-data cancel keys from the script's input slots
CANCEL_SLOTS = {'attack': 0, 'dodge': 5, 'block': 6, 'skill': 4, 'move': 15}


def timing(segs):
    """(total frames, {cancel key: first 1-based frame the game acts on it}) of a move's motions played in a row; cancels
    come from the last motion's script."""
    total = sum(max(s['end'] - s['start'], 1) for s in segs)
    last = segs[-1]
    off = total - max(last['end'] - last['start'], 1)
    cancels = {}
    for key, slot in CANCEL_SLOTS.items():
        f = next((f for f, st in last['slots'].get(slot, []) if st == 'go'), None)
        if f is not None:
            cancels[key] = off + max(f - last['start'], 0) + 1
    return total, cancels

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
    (23, 'rebellion', 'swordmaster', 'ground', 'Sword Pierce (return)', [(13, 15)],
     'Catching Rebellion; the sword hits on its way back as part of Sword Pierce, not here'),
    (19, 'rebellion', 'swordmaster', 'air', 'Aerial Rave · 1', [(13, 7)], ''),
    (20, 'rebellion', 'swordmaster', 'air', 'Aerial Rave · 2', [(13, 8)], ''),
    (21, 'rebellion', 'swordmaster', 'air', 'Aerial Rave · 3', [(13, 9)], ''),
    (22, 'rebellion', 'swordmaster', 'air', 'Aerial Rave · 4', [(13, 10)], ''),
    (17, 'rebellion', 'swordmaster', 'air', 'Divekick', [(13, 4), (13, 5)], ''),
    (200, 'rebellion', 'swordmaster', 'ground', 'Dance Macabre · 1', [(13, 17)],
     'The dash into part 2; it switches on no hitbox'),
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
    (71, 'agni-rudra', 'swordmaster', 'ground', 'Tempest', [(15, 8), (15, 10, 68), (15, 9)],
     'Held for one extra spin, which is the one that hits'),
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
    (172, 'kalina-ann', 'gunslinger', 'ground', 'Grapple', [(22, 0), (22, 1)], ''),

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


# weapons that run their own script alongside Dante's: pac, {Dante's script group: first weapon script}. Cerberus's
# script k plays with (Cerberus, k), Swordmaster Cerberus j with 30 + j (their motions match frame for frame)
WEAPON_SCRIPTS = {'cerberus': ('plwp_nunchaku.pac', {4: 0, 14: 30})}


def segments(game, scripts, move, _packs={}, _weapons={}):
    """The motions a move plays, in order: [dict(pack, slot, mot, start, end, slots)]; start / end are the motion's
    own frames the script plays (from a third value of the move's script entry, else its 01, else the motion's start
    frame, to its last frame)."""
    import dmc3_files as D
    out = []
    for entry in move['scripts']:
        grp, idx = entry[:2]
        r = scripts.run(grp, idx)
        pack, slot = r['motion']
        if pack not in _packs: _packs[pack] = D.subfiles(game.read('pl000_00_%d.pac' % pack))
        mot = D.motion(_packs[pack][slot])
        start = int(round(mot['start'])) if r['start'] is None else r['start']
        if len(entry) > 2: start = entry[2]     # the action code plays it from another frame
        whits = []
        if move['class'] in WEAPON_SCRIPTS:
            pac, first = WEAPON_SCRIPTS[move['class']]
            if pac not in _weapons: _weapons[pac] = D.WeaponScripts(D.subfiles(game.read(pac))[5])
            if grp in first: whits = _weapons[pac].run(0, first[grp] + idx)['hits']
        out.append(dict(pack=pack, slot=slot, mot=mot, start=start, end=int(round(mot['frames'])), slots=r['slots'],
                        hits=r['hits'], weapon_hits=whits, signals=r['signals']))
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


def hits(segs, colliders):
    """The damaging colliders a move's scripts switch on: [dict(start, end, id, hit, weapon)], frames 1-based as in
    timing(), hit = which of the move's hits (each 06 / 08 the script runs before switching colliders on starts a new
    one), weapon = switched on by the weapon's own script (Cerberus), whose colliders sit on its chain.
    A collider stays on for its frame count or until switched off; one left on for good ends with its motion."""
    out, total, n = [], timing(segs)[0], 0
    for key in ('hits', 'weapon_hits'):
        off, fresh = 0, False
        for s in segs:
            length = max(s['end'] - s['start'], 1)
            on = []
            for ev in s.get(key, []):
                f = off + max(ev[0] - s['start'], 0) + 1
                if f > off + length: break
                if ev[1] == 'wave':
                    fresh = True
                elif ev[1] == 'on':
                    ids = [i for i in ev[3] if i < len(colliders) and colliders[i]['type'] & 1]
                    if not ids: continue
                    if fresh: n += 1; fresh = False
                    for i in ids:
                        h = {'start': f, 'end': f + ev[2] - 1 if ev[2] else None, 'id': i, 'hit': max(n, 1),
                             'weapon': key == 'weapon_hits'}
                        out.append(h); on.append(h)
                else:
                    kind, v = ev[2]
                    for h in on:
                        if (h['id'] == v if kind == 'id' else colliders[h['id']]['type'] & v) and (h['end'] is None or h['end'] >= f):
                            h['end'] = f - 1
                    on = [h for h in on if h['end'] is None or h['end'] >= f]
            for h in on:
                if h['end'] is None: h['end'] = off + length
            off += length
    for h in out: h['end'] = min(h['end'], total)
    return [h for h in out if h['end'] >= h['start']]


def windows(hs):
    """Merged active windows [[start, end]] of hits()."""
    out = []
    for a, b in sorted((h['start'], h['end']) for h in hs):
        if out and a <= out[-1][1] + 1: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out


# Moves that hit with something they fire or throw, not with colliders of their own: when the action's code (its function
# in SLES_541.86) fires. ('signal', values): on the frames the script signals one of values (None: any);
# ('timer', segment, first frame of the segment, period): first, then every period frames while the segment plays, the
# frame and period being numbers or ('param', offset, add), a float of Dante's tuning table (pl000.pac slot 11) + add.
# Periods are Gunslinger level 1's.
SHOTS = {
    'rebellion.sword-pierce':  [('signal', None)],                  # 0x266f40 throws Rebellion
    'cerberus.crystal':        [('timer', 0, 41, None)],            # 0x272840: a 40-frame timer
    'nevan.thunder-bolt':      [('signal', {1, 2})],                # 0x2788a0
    'nevan.distortion':        [('timer', 1, 3, None)],             # 0x277ed0: a 1-frame timer after the release
    'beowulf.zodiac':          [('signal', {2})],                   # 0x27cee0
    'ebony-ivory.rain-storm':  [('signal', None), ('timer', 0, 13, ('param', 0x688, 0))],   # 0x26c050
    'shotgun.fireworks':       [('timer', 0, 2, ('param', 0x694, 0))],                      # 0x26de50
    'shotgun.air-fireworks':   [('timer', 0, 2, ('param', 0x694, 0))],                      # 0x26e1a0
    'shotgun.point-blank':     [('timer', 0, 1, None)],             # 0x26e940
    'artemis.normal-shot':     [('timer', 0, 3, None)],             # 0x26eb70
    'artemis.air-normal-shot': [('timer', 0, 2, None)],             # 0x26eff0
    'artemis.acid-rain':       [('timer', 0, ('param', 0x578, 1), ('param', 0x57c, 0))],   # 0x26f500
    'spiral.sniper':           [('signal', None)],                  # 0x26fdc0
    'spiral.trick-shot':       [('signal', None)],                  # 0x270270
    'kalina-ann.grapple':      [('signal', None)],                  # 0x271000
}


def shots(move, segs, tuning):
    """The 1-based frames a SHOTS move fires, as in timing(); tuning = pl000.pac slot 11."""
    import struct
    val = lambda v: v if not isinstance(v, tuple) else int(round(struct.unpack_from('<f', tuning, v[1])[0])) + v[2]
    out, offs, off = set(), [], 0
    for s in segs:
        offs.append(off); off += max(s['end'] - s['start'], 1)
    for rule in SHOTS.get(move['id'], []):
        if rule[0] == 'signal':
            for s, o in zip(segs, offs):
                for f, v in s['signals']:
                    if (rule[1] is None or v in rule[1]) and f < s['end']:
                        out.add(o + max(f - s['start'], 0) + 1)
        else:
            _, k, first, period = rule
            length = max(segs[k]['end'] - segs[k]['start'], 1)
            f = val(first)
            while f <= length:
                out.add(offs[k] + f)
                if period is None: break
                f += val(period)
    return sorted(out)


def move_hits(move, segs, colliders, tuning):
    """hits() plus a 1-frame entry (id None) per shot a SHOTS move fires, hit numbers following on."""
    hs = hits(segs, colliders)
    n = max((h['hit'] for h in hs), default=0)
    for k, f in enumerate(shots(move, segs, tuning)):
        hs.append({'start': f, 'end': f, 'id': None, 'hit': n + k + 1, 'weapon': False})
    return hs

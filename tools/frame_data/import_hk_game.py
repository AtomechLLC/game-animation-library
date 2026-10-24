"""Hollow Knight frame data and 2D preview sprites, read straight from an installed copy of the game. Read-only.

    python tools/frame_data/import_hk_game.py "Z:/SteamLibrary/steamapps/common/Hollow Knight"
    python tools/frame_data/import_hk_game.py <install> --no-sprites      # frame data only

Writes frame-data/hollow-knight.json, frame-data/sprites/hollow-knight/ (sheets, per-class moves, sprites.json) and
frame-data/icons/hollow-knight/. Needs UnityPy, TypeTreeGeneratorAPI and Pillow.

Where the numbers come from (see frame-data/README.md, "Hollow Knight"):
  The Knight prefab in resources.assets: HeroController's tuning fields (attack duration, recovery and cooldown,
  dash and shadow dash times, i-frames, jump steps, gravity scale), the nail slash children under Attacks with
  their NailSlash, PolygonCollider2D and tk2d clips, the spell and nail art objects with their colliders and
  PlayMaker FSMs (Spell Control, Nail Arts, and each hit object's own Control Collider / Hit Box Control FSM).
  NailSlash.FixedUpdate switches a slash's collider on at physics step 1 and off at step 5, so nail hitboxes are
  out on steps 1-4 (50 Hz). FSM timings come from hk_fsm.simulate.
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hk_unity, hk_tk2d, hk_fsm
from hk_render import Timeline, Xf, frames_of, frame_of, windows, render, sheet, FPS
from hk_fsm import STEP, steps_between

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME_ID = 'hollow-knight'
KNIGHT_GO = 'Knight'             # the hero prefab: the GameObject holding HeroController in resources.assets

def quat_z(q):
    return 2 * math.atan2(q.z, q.w)

class Knight:
    """The hero prefab and what hangs off it."""
    def __init__(self, g):
        self.g = g
        self.sp = hk_tk2d.Sprites(g)
        f = g.files['resources.assets']
        hc = next(o for o in f.objects.values() if o.type.name == 'MonoBehaviour' and g.script(o) == 'HeroController')
        self.go = f.objects[hk_unity.mono_header(hc.get_raw_data())[0]]
        self.hc = g.mono(hc)
        anim = g.mono(g.comp(self.go, 'tk2dSpriteAnimator'))
        self.lib = self.sp.library(anim['library'], self.go)
        self.clips = self.lib['byName']
        spr = g.mono(g.comp(self.go, 'tk2dSprite'))
        self.sprite_scale = (spr['_scale']['x'], spr['_scale']['y'])
        self.fsms = {}
        for t, o in g.components(self.go):
            if t == 'PlayMakerFSM':
                d = g.mono(o)['fsm']; self.fsms[d['name']] = d

    def xf(self, path):
        """Transform of a child (path under the Knight) in the Knight's space, its tk2dSprite scale included."""
        go, chain = self.go, []
        for name in path.split('/'):
            go = self.g.child(go, name); chain.append(go)
        out = Xf()
        for c in reversed(chain):
            tr = self.g.comp(c, 'Transform').read()
            p, s = tr.m_LocalPosition, tr.m_LocalScale
            out = out.then(Xf(p.x, p.y, s.x, s.y, quat_z(tr.m_LocalRotation)))
        return out

    def obj(self, path): return self.g.child(self.go, path)

    def obj_fsms(self, path):
        out = {}
        for t, o in self.g.components(self.obj(path)):
            if t == 'PlayMakerFSM':
                d = self.g.mono(o)['fsm']; out[d['name']] = d
        return out

    def sprite_xf(self, path):
        """xf() with the object's own tk2dSprite _scale applied first."""
        o = self.g.comp(self.obj(path), 'tk2dSprite')
        x = self.xf(path)
        if o is not None:
            s = self.g.mono(o)['_scale']; x = Xf(x.x, x.y, x.sx * s['x'], x.sy * s['y'], x.rot)
        return x

    def animator(self, path):
        a = self.g.comp(self.obj(path), 'tk2dSpriteAnimator')
        if a is None: return None
        d = self.g.mono(a)
        lib = self.sp.library(d['library'], a)
        return lib, (lib['clips'][d['defaultClipId']] if 0 <= d['defaultClipId'] < len(lib['clips']) else None)

    def polys(self, path, base=None):
        """Polygon colliders (each a list of points) on an object, in the Knight's space."""
        o = self.obj(path)
        x = self.xf(path)
        out = []
        for t, c in self.g.components(o):
            if t == 'PolygonCollider2D':
                r = c.read_typetree(); off = r['m_Offset']
                for path_pts in r['m_Points']['m_Paths']:
                    out.append(('poly', [x.apply(p['x'] + off['x'], p['y'] + off['y']) for p in path_pts]))
            elif t == 'BoxCollider2D':
                r = c.read_typetree(); off, sz = r['m_Offset'], r['m_Size']
                a = x.apply(off['x'] - sz['x'] / 2, off['y'] - sz['y'] / 2); b = x.apply(off['x'] + sz['x'] / 2, off['y'] + sz['y'] / 2)
                out.append(('rect', min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
        return out

    def coll_of(self, owner):
        return lambda fr: self.sp.collection(fr['spriteCollection'], owner)

# --- moves ---------------------------------------------------------------------------------------------------------

def nail_damage_range():
    return '5–21'     # PlayerData.nailDamage: 5 for the Old Nail, +4 per upgrade, 21 for the Pure Nail

class Builder:
    def __init__(self, k):
        self.k, self.hc = k, k.hc
        self.moves, self.timelines = [], {}

    def add(self, mid, type_, grip, name, tl, total_s, hits, extra=None, cancels=None, iframes=(), damage=None,
            hit_count=None, desc=None):
        total = frame_of(total_s - 1e-6) if total_s > 0 else 1
        act = sorted({f for w in hits for f in frames_of(w)})
        active = windows(act)
        startup = active[0][0] if active else None
        dodge = (cancels or {}).get('dodge')
        last = active[-1][1] if active else None
        m = {'id': mid, 'class': 'knight', 'type': type_, 'grip': grip, 'name': name,
             'startup': startup, 'active': active, 'activeFrames': len(act), 'hits': hit_count or len(active),
             'recovery': max(dodge - last - 1, 0) if (dodge and last) else ((total - last) if last else None),
             'total': total, 'cancels': {k: v for k, v in (cancels or {}).items() if v},
             'armor': [], 'iframes': windows(sorted({f for w in iframes for f in frames_of(w)})),
             'parryable': None, 'damage': damage or {}, 'weapons': [], 'default': True}
        if extra: m['extra'] = extra
        if desc: m['desc'] = desc
        tl.total = max(tl.total, total_s)
        self.moves.append(m); self.timelines[mid] = tl
        return m

    def knight_layer(self, tl, clips, t1=None):
        k = self.k
        tl.sprite(k.coll_of(k.go), [(t, k.clips[c]) for t, c in clips], 0, t1 or 99, Xf(0, 0, *k.sprite_scale), z=0)

    def hurt(self, tl, total_s):
        for shp in self.k.polys('HeroBox'):
            tl.box('p', ('span', 0, total_s + 1), shp)

    # nail: Slash, AltSlash, UpSlash, DownSlash, WallSlash ---------------------------------------------------------
    def nail(self):
        hc, k = self.hc, self.k
        rows = [('Slash', 'slash', 'Slash', 'Slash', 'any', 'Side slash, the first of the two alternating swings'),
                ('AltSlash', 'altSlash', 'Alt Slash', 'SlashAlt', 'any', 'The second side swing; a slash within 0.5 s of the last alternates'),
                ('UpSlash', 'upSlash', 'Up Slash', 'UpSlash', 'any', 'Slash upward (up + attack)'),
                ('DownSlash', 'downSlash', 'Down Slash', 'DownSlash', 'air', 'Slash downward in the air; hitting something bounces the Knight up (pogo)'),
                ('WallSlash', 'wallSlash', 'Wall Slash', 'Wall Slash', 'wall', 'Slash away from the wall while wall sliding')]
        for obj, mid, name, kclip, grip, desc in rows:
            path = 'Attacks/' + obj
            ns = k.g.mono(k.g.comp(k.obj(path), 'NailSlash'))
            lib, _ = k.animator(path)
            eff = lib['byName'][ns['animName']]
            # NailSlash: collider on at physics step 1, off once step >= 5; the effect hides once its clip has
            # finished and the collider has been on for 2 steps
            hit_steps = [i * STEP for i in range(1, 5)]
            eff_end = max(math.ceil(len(eff['frames']) / eff['fps'] / STEP - 1e-9) * STEP, 2 * STEP)
            total_s = hc['ATTACK_COOLDOWN_TIME']
            tl = Timeline(total_s)
            self.knight_layer(tl, [(0, kclip)])
            tl.sprite(k.coll_of(k.obj(path)), [(0, eff)], 0, eff_end, k.sprite_xf(path), z=1)
            for shp in k.polys(path): tl.box('a', ('steps', hit_steps), shp)
            self.hurt(tl, total_s)
            self.add(f'knight.nail.{mid}', 'nail', grip, name, tl, total_s, [('steps', hit_steps)],
                     cancels={'dodge': frame_of(hc['ATTACK_RECOVERY_TIME']), 'attack': frame_of(hc['ATTACK_COOLDOWN_TIME'])},
                     damage={'amount': nail_damage_range()}, desc=desc,
                     extra={'Attack state': f"{hc['ATTACK_DURATION']:.2f} s ({hc['ATTACK_DURATION_CH']:.2f} s with Quick Slash)",
                            'Cooldown': f"{hc['ATTACK_COOLDOWN_TIME']:.2f} s ({hc['ATTACK_COOLDOWN_TIME_CH']:.2f} s with Quick Slash)",
                            'Knight animation': f"{kclip} ({len(k.clips[kclip]['frames'])} frames at {k.clips[kclip]['fps']:g} fps)"})

    # nail arts ------------------------------------------------------------------------------------------------------
    def nail_arts(self):
        hc, k = self.hc, self.k
        na = k.fsms['Nail Arts']
        charge = hc['NAIL_CHARGE_TIME_DEFAULT']
        def mult(path):
            for f in k.obj_fsms(path).values():
                if f['name'] == 'nailart_damage':
                    return hk_fsm.var(f, {'var': 'Multiplier'})
            return None
        # Great Slash: released after the charge; G Slash plays NA Big Slash, Stop Move waits for it to end
        for state, mid, name, path, effclip, desc in [
                ('G Slash', 'greatSlash', 'Great Slash', 'Attacks/Great Slash', 'NA Big Slash Effect', 'Hold attack to charge, release standing still'),
                ('Dash Slash', 'dashSlash', 'Dash Slash', 'Attacks/Dash Slash', 'NA Dash Slash Effect', 'Hold attack to charge, release while dashing; timed from the end of the dash')]:
            run = hk_fsm.simulate(na, state, k.clips, {})
            end = run.first('state', 'Regain Control') or run.end
            on = run.first('on', path.split('/')[-1]) if path.endswith('Dash Slash') else run.first('on', 'Great Slash Effect')
            on = on or 0.0
            cc = k.obj_fsms(path).get('Control Collider')
            k_on, k_off = hk_fsm.counter_windows(cc)
            steps = [on + i * STEP for i in range(k_on, k_off)]
            lib, _ = k.animator(path)
            eff = lib['byName'][effclip]
            total = max(end, steps[-1] + STEP, on + hk_fsm.clip_time(eff))
            tl = Timeline(total)
            self.knight_layer(tl, [(t, c) for t, c in run.all('clip')])
            tl.sprite(k.coll_of(k.obj(path)), [(on, eff)], on, total, k.sprite_xf(path), z=1, ends_with_clip=True)
            for shp in k.polys(path): tl.box('a', ('steps', steps), shp)
            self.hurt(tl, total)
            m = mult(path)
            self.add(f'knight.nailArt.{mid}', 'nailArt', 'ground' if mid == 'greatSlash' else 'any', name, tl, total, [('steps', steps)],
                     cancels={'dodge': frame_of(end) if end < total else None},
                     damage={'amount': f'{m:g}× nail' if m else None}, desc=desc,
                     extra={'Charge': f'{charge:.2f} s ({hc["NAIL_CHARGE_TIME_CHARM"]:.2f} s with Nailmaster\'s Glory)',
                            'Hitbox': f'physics steps {k_on}–{k_off - 1} after the slash appears (Control Collider FSM)'})
        # Cyclone Slash: spins until its timer runs out (Cyclone Spin ends at Timer 0.45 s without more presses)
        spin = None
        for a, p in hk_unity.actions({s['name']: s for s in na['states']}['Cyclone Spin']):
            if a == 'FloatCompare' and isinstance(p.get('float2'), float): spin = spin or p['float2']
        run = hk_fsm.simulate(na, 'Cyclone Start', k.clips, {'Cyclone Spin': ('END', spin)})
        end = run.first('state', 'Regain Control') or run.end
        on = run.first('on', 'Cyclone Slash'); off = run.first('state', 'Cyclone End')
        path = 'Attacks/Cyclone Slash'
        lib, defclip = k.animator(path)
        tl = Timeline(end)
        self.knight_layer(tl, [(t, c) for t, c in run.all('clip')])
        tl.sprite(k.coll_of(k.obj(path)), [(on, lib['byName']['Cyclone Effect']), (off, lib['byName']['Cyclone Effect End'])], on, end,
                  k.sprite_xf(path), z=1, ends_with_clip=True)
        for side in ('Hit L', 'Hit R'):
            for shp in k.polys(path + '/Hits/' + side): tl.box('a', ('span', on, off), shp)
        self.hurt(tl, end)
        m = mult(path + '/Hits/Hit L')
        self.add('knight.nailArt.cycloneSlash', 'nailArt', 'any', 'Cyclone Slash', tl, end, [('span', on, off)],
                 damage={'amount': f'{m:g}× nail per hit' if m else None}, desc='Hold attack to charge, release holding up or down; spins in place, more attack presses extend it',
                 extra={'Charge': f'{charge:.2f} s', 'Spin': f'{spin:.2f} s, extended by attack presses up to 1.2 s'})

    # spells ----------------------------------------------------------------------------------------------------------
    def child_hits(self, path, t_on, lib_clips=None, choose=None):
        """When a spell's hit children are out: its Hit Box Control FSM switches them on and off around its clip."""
        k = self.k
        fs = k.obj_fsms(path)
        hb = fs.get('Hit Box Control')
        lib, defclip = k.animator(path)
        if hb is None:      # no Hit Box Control (Abyss Shriek): the hits are out for the whole clip
            T = hk_fsm.clip_time(defclip)
            return t_on, t_on + T, t_on + T, defclip, lib
        run = hk_fsm.simulate(hb, hb['startState'], lib['byName'], {'Check Scale': 'POS', **(choose or {})}, owner_clip=defclip)
        ch = run.all('children')
        on = next((t for t, v in ch if v), None); off = next((t for t, v in ch if not v and on is not None and t >= on), None)
        end = run.end
        return t_on + (on or 0), t_on + (off if off is not None else end), t_on + end, defclip, lib

    def spells(self):
        hc, k = self.hc, self.k
        sc = k.fsms['Spell Control']
        lvl = lambda n: {'Level Check': n, 'Level Check 2': n, 'Level Check 3': n}
        def dmg(path):
            for f in k.obj_fsms(path).values():
                if f['name'] == 'Set Damage':
                    for s in f['states']:
                        for a, p in hk_unity.actions(s):
                            if a == 'SetFsmInt' and p.get('variableName') == 'damageDealt': return p.get('setValue')
            for f in k.obj_fsms(path).values():
                if f['name'] == 'damages_enemy': return hk_fsm.var(f, {'var': 'damageDealt'})
            return None
        f = k.g.files['resources.assets']
        # Vengeful Spirit / Shade Soul: the projectile flies at the FSM's Fire Speed for its 2 s life
        for level, mid, name, top in [('LEVEL 1', 'vengefulSpirit', 'Vengeful Spirit', 5396), ('LEVEL 2', 'shadeSoul', 'Shade Soul', 7224)]:
            run = hk_fsm.simulate(sc, 'Fireball Antic', k.clips, lvl(level))
            end = run.first('state', 'Spell End') or run.end
            t_cast = run.first('spawn')
            tl = Timeline(end)
            self.knight_layer(tl, [(t, c) for t, c in run.all('clip')])
            proj = self.fireball(f.objects[top])
            if proj:
                speed, ball_go, box, blast = proj
                mv = lambda t, t0=t_cast, v=speed: (-v * (t - t0), 0.0)
                bl, bdef = blast
                if bdef:
                    tl.sprite(self.k.coll_of(ball_go), [(t_cast, bdef)], t_cast, 99, Xf(0, 0, -1, 1), z=2, moving=mv)
                tl.box('a', ('span', t_cast, end + 1), box, moving=mv)
            self.hurt(tl, end)
            self.add(f'knight.spell.{mid}', 'spell', 'any', name, tl, end, [('span', t_cast, end)],
                     damage={'amount': self.fireball_damage(level)}, desc='Projectile spell (33 Soul); the startup is when the projectile spawns',
                     extra={'Projectile speed': f'{proj[0]:g} units/s' if proj else '—', 'Cast time': f"{hc['CAST_TIME']:.2f} s"})
        # Desolate Dive / Descending Dark from the ground: the dive lands at once
        for level, mid, name, slam in [('LEVEL 1', 'desolateDive', 'Desolate Dive', 'Spells/Q Slam'),
                                       ('LEVEL 2', 'descendingDark', 'Descending Dark', 'Spells/Q Slam 2')]:
            run = hk_fsm.simulate(sc, 'Quake Antic', k.clips, {**lvl(level), 'Quake1 Down': ('HERO LANDED', 0.0), 'Quake2 Down': ('HERO LANDED', 0.0)})
            end = run.first('state', 'Spell End') or run.end
            land = run.first('state', 'Quake1 Land' if level == 'LEVEL 1' else 'Q2 Land')
            tl = Timeline(end)
            self.knight_layer(tl, [(t, c) for t, c in run.all('clip')])
            hits = []
            for p in [slam] + (['Spells/Q Mega'] if level == 'LEVEL 2' else []):
                t_on = run.first('on', p.split('/')[-1])
                if t_on is None: continue
                h0, h1, gone, defclip, lib = self.child_hits(p, t_on)
                tl.sprite(k.coll_of(k.obj(p)), [(t_on, defclip)], t_on, gone, k.sprite_xf(p), z=1, ends_with_clip=True)
                for side in ('Hit L', 'Hit R'):
                    for shp in k.polys(p + '/' + side): tl.box('a', ('span', h0, h1), shp)
                hits.append(('span', h0, h1))
            for p in ['Spells/Q1 Pillar'] if level == 'LEVEL 1' else ['Spells/Q Pillar', 'Spells/Q Slam Lines']:
                t_on = run.first('on', p.split('/')[-1])
                an = k.animator(p)
                if t_on is not None and an and an[1]:
                    tl.sprite(k.coll_of(k.obj(p)), [(t_on, an[1])], t_on, end, k.sprite_xf(p), z=-1, ends_with_clip=True)
            # Q Fall Damage is out while diving (no time from the ground)
            iv = [('span', land, land + hc['INVUL_TIME_QUAKE'])]
            self.hurt(tl, end)
            dm = [dmg(slam + '/Hit L')] + ([dmg('Spells/Q Mega/Hit L')] if level == 'LEVEL 2' else [])
            self.add(f'knight.spell.{mid}', 'spell', 'any', name, tl, end, hits, iframes=iv,
                     damage={'amount': ' + '.join(str(d) for d in dm if d is not None) or None}, desc='Dive spell (33 Soul), cast from the ground; in the air the dive falls first and its body hits on the way down',
                     extra={'Dive body damage': str(dmg('Spells/Q Fall Damage')), 'I-frames': f"{hc['INVUL_TIME_QUAKE']:.2f} s from the landing"})
        # Howling Wraiths / Abyss Shriek
        for level, mid, name, heads in [('LEVEL 1', 'howlingWraiths', 'Howling Wraiths', 'Spells/Scr Heads'),
                                        ('LEVEL 2', 'abyssShriek', 'Abyss Shriek', 'Spells/Scr Heads 2')]:
            run = hk_fsm.simulate(sc, 'Level Check 3', k.clips, lvl(level))
            end = run.first('state', 'Spell End') or run.end
            t_on = [t for t, v in run.all('on') if v == heads.split('/')[-1]][-1]
            h0, h1, gone, defclip, lib = self.child_hits(heads, t_on)
            tl = Timeline(end)
            self.knight_layer(tl, [(t, c) for t, c in run.all('clip')])
            base = heads.replace('Heads', 'Base')
            an = k.animator(base)
            if an and an[1]:
                tl.sprite(k.coll_of(k.obj(base)), [(t_on, an[1])], t_on, end, k.sprite_xf(base), z=-1, ends_with_clip=True)
            tl.sprite(k.coll_of(k.obj(heads)), [(t_on, defclip)], t_on, max(gone, end), k.sprite_xf(heads), z=1, ends_with_clip=True)
            for side in ('Hit L', 'Hit R', 'Hit U'):
                for shp in k.polys(heads + '/' + side): tl.box('a', ('span', h0, h1), shp)
            total = max(end, h1)
            tl.total = total
            self.hurt(tl, total)
            d = dmg(heads + '/Hit L')
            self.add(f'knight.spell.{mid}', 'spell', 'ground', name, tl, total, [('span', h0, h1)],
                     cancels={'dodge': frame_of(end) if end < total else None},
                     damage={'amount': f'{d} × 3 hitboxes' if d else None}, desc='Shriek spell (33 Soul); three overlapping hitboxes (left, right, up) can each hit')

    def fireball(self, top):
        """(speed, fireball object, its box in Knight space at spawn, (lib, default clip)) of a fireball spawner."""
        g, k = self.k.g, self.k
        fsm = None
        for t, o in g.components(top):
            if t == 'PlayMakerFSM': fsm = g.mono(o)['fsm']
        if not fsm: return None
        speed, ball = None, None
        for s in fsm['states']:
            if s['name'] != 'Cast Right': continue
            for a, p in hk_unity.actions(s):
                if a == 'SpawnObjectFromGlobalPool' and isinstance(p.get('gameObject'), dict) and p['gameObject'].get('m_PathID'): ball = p['gameObject']['m_PathID']
                if a == 'SetVelocityAsAngle': speed = hk_fsm.var(fsm, p.get('speed'))
        if not ball: return None
        bo = top.assets_file.objects[ball]
        box = None
        for t, o in g.components(bo):
            if t == 'BoxCollider2D' and box is None:
                r = o.read_typetree(); off, sz = r['m_Offset'], r['m_Size']
                # the ball is spawned facing the cast direction; the Knight's art faces left, so mirror x
                box = ('rect', -(off['x'] + sz['x'] / 2), off['y'] - sz['y'] / 2, -(off['x'] - sz['x'] / 2), off['y'] + sz['y'] / 2)
        an = g.comp(bo, 'tk2dSpriteAnimator')
        lib, defclip = None, None
        if an is not None:
            d = g.mono(an); lib = k.sp.library(d['library'], an); defclip = lib['clips'][d['defaultClipId']]
        return speed or 0.0, bo, box, (lib, defclip)

    def fireball_damage(self, level):
        return {'LEVEL 1': 15, 'LEVEL 2': 30}[level]   # damages_enemy on the Fireball objects

    # movement ---------------------------------------------------------------------------------------------------------
    def movement(self):
        hc, k = self.hc, self.k
        G = 60.0 * hc['DEFAULT_GRAVITY']        # Physics2DSettings gravity -60 times the hero's gravity scale
        def dash(mid, name, clip, burst, t_dash, iframes, desc, burst_xf):
            tl = Timeline(t_dash)
            self.knight_layer(tl, [(0, clip)])
            if burst:
                lib, defclip = k.animator(burst)
                tl.sprite(k.coll_of(k.obj(burst)), [(0, defclip)], 0, 99, burst_xf, z=-1, ends_with_clip=True)
                tl.layers[-1]['follow'] = False
            self.hurt(tl, t_dash)
            speed = hc['DASH_SPEED']
            tl.pos = lambda t, v=speed, T=t_dash: (-v * min(t, T), 0.0)
            self.add(f'knight.movement.{mid}', 'movement', 'any', name, tl, t_dash, [], iframes=iframes, desc=desc,
                     cancels={'attack': frame_of(t_dash)},
                     extra={'Speed': f'{speed:g} units/s', 'Cooldown': f"{hc['DASH_COOLDOWN']:.2f} s ({hc['DASH_COOLDOWN_CH']:.2f} s with Dashmaster)"})
        # HeroController.HeroDash places the dash burst at (4.11, -0.55) and the shadow dash burst at (5.21, -0.58)
        bx = k.sprite_xf('Effects/Dash Burst'); bx = Xf(4.11, -0.55, -abs(bx.sx), abs(bx.sy), 0)
        dash('dash', 'Dash', 'Dash', 'Effects/Dash Burst', hc['DASH_TIME'], [], 'Mothwing Cloak dash', bx)
        sx = k.sprite_xf('Effects/Shadow Burst'); sx = Xf(5.21, -0.58, sx.sx, sx.sy, 0)
        dash('shadowDash', 'Shadow Dash', 'Shadow Dash', 'Effects/Shadow Burst', hc['SHADOW_DASH_TIME'], [('span', 0, hc['SHADOW_DASH_TIME'])],
             "Shade Cloak dash: passes through enemies and their attacks (not hazards)", sx)
        # jumps: full height, JUMP_STEPS physics steps at JUMP_SPEED, then gravity down to MAX_FALL_VELOCITY
        def arc(steps, v0):
            pts, y, v, t = [], 0.0, v0, 0.0
            n = 0
            while True:
                if n < steps: v = v0
                else: v = max(v - G * STEP, -hc['MAX_FALL_VELOCITY'])
                y += v * STEP; t += STEP; n += 1
                pts.append((t, y))
                if y <= 0 and n > steps: break
            return pts
        for mid, name, steps, clip, extra_obj, desc in [('jump', 'Jump', hc['JUMP_STEPS'], 'Airborne', None, 'Full-height jump from the ground (holding jump)'),
                                                        ('doubleJump', 'Double Jump', hc['DOUBLE_JUMP_STEPS'], 'Double Jump', 'Effects/Double J Wings', 'Monarch Wings jump in the air, shown from a standstill')]:
            pts = arc(steps, hc['JUMP_SPEED'])
            T = pts[-1][0]
            def pos(t, pts=pts):
                y = 0.0
                for tt, yy in pts:
                    if tt > t: break
                    y = yy
                return (0.0, max(y, 0.0))
            land = k.clips['Land']
            total = T + len(land['frames']) / land['fps']
            tl = Timeline(total)
            tl.pos = pos
            self.knight_layer(tl, [(0, clip)] + ([(len(k.clips[clip]['frames']) / k.clips[clip]['fps'], 'Airborne')] if clip != 'Airborne' else []) + [(T, 'Land')])
            if extra_obj:
                lib, defclip = k.animator(extra_obj)
                tl.sprite(k.coll_of(k.obj(extra_obj)), [(0, defclip)], 0, 99, k.sprite_xf(extra_obj), z=-1, ends_with_clip=True)
                tl.layers[-1]['follow'] = True
            self.hurt(tl, total)
            apex = max(y for _, y in pts)
            self.add(f'knight.movement.{mid}', 'movement', 'air' if mid == 'doubleJump' else 'ground', name, tl, total, [], desc=desc,
                     extra={'Height': f'{apex:.2f} units', 'Air time': f'{T:.2f} s',
                            'Rise': f"{steps} physics steps at {hc['JUMP_SPEED']:g} units/s, then gravity {G:g} units/s²"})
        # focus: Focus Start Time, then focusMP_amount (33) Soul drained at Time Per MP Drain UnCH each
        sc = k.fsms['Spell Control']
        start = hk_fsm.var(sc, {'var': 'Focus Start Time'}); per = hk_fsm.var(sc, {'var': 'Time Per MP Drain UnCH'})
        heal = start + 33 * per
        get, fin = k.clips['Focus Get Once'], k.clips['Focus End']
        total = heal + len(get['frames']) / get['fps'] + len(fin['frames']) / fin['fps']
        tl = Timeline(total)
        self.knight_layer(tl, [(0, 'Focus'), (heal, 'Focus Get Once'), (heal + len(get['frames']) / get['fps'], 'Focus End')])
        self.hurt(tl, total)
        self.add('knight.movement.focus', 'movement', 'ground', 'Focus', tl, total, [], desc='Focus to heal one mask (33 Soul); the mask heals at the marked frame',
                 extra={'Heal at': f'{heal:.3f} s (frame {frame_of(heal)})', 'With Quick Focus': f"{start + 33 * hk_fsm.var(sc, {'var': 'Time Per MP Drain CH'}):.3f} s"})
        # taking a hit: recoil, then i-frames (the hit also freezes the game for DAMAGE_FREEZE_WAIT)
        inv = hc['INVUL_TIME']
        tl = Timeline(inv)
        self.knight_layer(tl, [(0, 'Recoil'), (len(k.clips['Recoil']['frames']) / k.clips['Recoil']['fps'], 'Idle Hurt')])
        self.hurt(tl, inv)
        self.add('knight.movement.hit', 'movement', 'any', 'Take hit', tl, inv, [], iframes=[('span', 0, inv)],
                 cancels={'dodge': frame_of(hc['RECOIL_DURATION'])}, desc='Hit reaction: knocked back, then invulnerable',
                 extra={'Hit freeze': f"{hc['DAMAGE_FREEZE_WAIT']:.2f} s (not counted)", 'Recoil': f"{hc['RECOIL_DURATION']:.2f} s at {hc['RECOIL_VELOCITY']:g} units/s",
                        'I-frames': f"{inv:.2f} s ({hc['INVUL_TIME_STAL']:.2f} s with Stalwart Shell)"})
        for mid, name, clip, desc in [('hardLanding', 'Hard landing', 'HardLand', 'After a long fall the Knight is stuck on landing'),
                                      ('death', 'Death', 'Death', 'Death animation')]:
            c = k.clips[clip]; total = len(c['frames']) / c['fps']
            if mid == 'hardLanding': total = hc['HARD_LANDING_TIME']
            tl = Timeline(total)
            self.knight_layer(tl, [(0, clip)])
            self.hurt(tl, total)
            self.add(f'knight.movement.{mid}', 'movement', 'ground' if mid == 'hardLanding' else 'any', name, tl, total, [], desc=desc)

# --- output ----------------------------------------------------------------------------------------------------------

def icon(k, out_dir):
    from PIL import Image
    fr = k.clips['Idle']['frames'][0]
    img, _, _ = k.sp.sprite(k.sp.collection(fr['spriteCollection'], k.go), fr['spriteId'])
    img = img.transpose(Image.FLIP_LEFT_RIGHT)
    bb = img.getbbox(); img = img.crop(bb)
    s = 96 / max(img.size)
    img = img.resize((max(1, round(img.size[0] * s)), max(1, round(img.size[1] * s))), Image.LANCZOS)
    can = Image.new('RGBA', (96, 96), (0, 0, 0, 0)); can.alpha_composite(img, ((96 - img.size[0]) // 2, (96 - img.size[1]) // 2))
    os.makedirs(out_dir, exist_ok=True)
    can.save(os.path.join(out_dir, 'knight.webp'), lossless=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('game_dir')
    ap.add_argument('--no-sprites', action='store_true')
    ap.add_argument('only', nargs='*', help='move ids to render (default all)')
    a = ap.parse_args()
    g = hk_unity.Game(a.game_dir)
    k = Knight(g)
    b = Builder(k)
    b.nail(); b.nail_arts(); b.spells(); b.movement()
    data = {
        'schema': 'frame-data/1',
        'game': {'id': GAME_ID, 'name': 'Hollow Knight', 'fps': FPS, 'version': f'Steam build (Unity {hk_unity.unity_version(g.dir)})',
                 'frameNote': 'Hollow Knight times its moves in seconds and its nail hitboxes in 50 Hz physics steps, so frames here are 1/60 s, 1-based: frame N covers (N-1)/60 to N/60 s, and a hitbox counts for every frame it is out in. Startup is the first such frame.'},
        'source': {'name': 'Hollow Knight game files', 'url': 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_hk_game.py',
                   'author': 'Team Cherry', 'retrieved': __import__('datetime').date.today().isoformat(), 'method': 'import_hk_game.py',
                   'note': "Hollow Knight data is read straight from the game files: timings from the Knight's HeroController and PlayMaker FSMs (Spell Control, Nail Arts and each hit object's own FSM), hitboxes from the colliders on the Knight's attack and spell objects, sprites from its tk2d animations. Damage is per hit at base level; nail damage depends on the nail upgrade.",
                   'links': [{'name': 'Importer', 'url': 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_hk_game.py'}]},
        'labels': {'class': 'Character', 'classes': 'characters', 'allClasses': 'All characters', 'grip': 'Where', 'allFamilies': 'All characters',
                   'search': 'Search moves…', 'everyClass': 'Every character', 'patch': '',
                   'pickClass': 'Pick a character to see its moves by type.', 'classView': 'every move, by type.',
                   'recovery': 'Frames from the last active frame until you can dash'},
        'columns': ['name', 'class', 'grip', 'strip', 'startup', 'active', 'recovery', 'dodge', 'attack', 'total', 'dmg'],
        'columnNames': {'dodge': ['→ Dash', 'First frame you can dash, jump or cast'], 'attack': ['→ Attack', 'First frame you can attack again']},
        'families': [{'id': 'hero', 'name': 'The Knight'}],
        'classes': [{'id': 'knight', 'name': 'The Knight', 'family': 'hero', 'icon': 'The Knight', 'weapons': [], 'moves': len(b.moves)}],
        'moveTypes': [{'id': 'nail', 'name': 'Nail', 'description': 'Nail slashes'},
                      {'id': 'nailArt', 'name': 'Nail Arts', 'description': 'Charged nail attacks, timed from the release'},
                      {'id': 'spell', 'name': 'Spells', 'description': 'Spells, level 1 and 2'},
                      {'id': 'movement', 'name': 'Movement', 'description': 'Dashes, jumps, focus, hit reactions: length only'}],
        'grips': [{'id': 'any', 'name': 'Ground or air', 'short': 'Any'}, {'id': 'ground', 'name': 'Ground', 'short': 'Ground'},
                  {'id': 'air', 'name': 'Air', 'short': 'Air'}, {'id': 'wall', 'name': 'Wall', 'short': 'Wall'}],
        'moves': b.moves,
    }
    fd = os.path.join(ROOT, 'frame-data')
    with open(os.path.join(fd, f'{GAME_ID}.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    icons_dir = os.path.join(fd, 'icons', GAME_ID)
    icon(k, icons_dir)
    with open(os.path.join(icons_dir, 'icons.json'), 'w', encoding='utf-8') as f:
        json.dump({'lead': 'Icons are the game\'s own sprites', 'note': 'Sprites (c) Team Cherry.',
                   'icons': {'The Knight': {'file': 'knight.webp'}}}, f, indent=1)
    print(len(b.moves), 'moves')
    if a.no_sprites: return
    sdir = os.path.join(fd, 'sprites', GAME_ID)
    os.makedirs(os.path.join(sdir, 'sheets'), exist_ok=True); os.makedirs(os.path.join(sdir, 'moves'), exist_ok=True)
    mfile = os.path.join(sdir, 'moves', 'knight.json')
    out = json.load(open(mfile)) if (a.only and os.path.exists(mfile)) else {'moves': {}}
    for m in b.moves:
        if a.only and m['id'] not in a.only: continue
        tl = b.timelines[m['id']]
        tl.total = m['total'] / FPS
        frames, boxes, W, H, s = render(tl, k.sp, clip_box=(-14, -6, 4, 12))
        img, cols = sheet(frames, W, H)
        fn = f'sheets/{m["id"]}.webp'
        img.save(os.path.join(sdir, fn), quality=88, method=6)
        out['moves'][m['id']] = {'sheet': fn, 'w': W, 'h': H, 'cols': cols, 'frames': boxes}
        print(m['id'], len(frames), 'frames', W, 'x', H)
    with open(mfile, 'w') as f: json.dump(out, f, separators=(',', ':'))
    with open(os.path.join(sdir, 'sprites.json'), 'w') as f:
        json.dump({'fps': FPS, 'smooth': True,
                   'kinds': {'p': 'Hurtbox', 'a': 'Attack'},
                   'source': {'name': 'Hollow Knight game files', 'url': 'https://github.com/AtomechLLC/game-animation-library/blob/main/tools/frame_data/import_hk_game.py', 'author': 'Team Cherry'},
                   'classes': {'knight': {'file': 'moves/knight.json'}}}, f, indent=1)

if __name__ == '__main__':
    main()

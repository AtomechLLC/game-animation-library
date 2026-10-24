"""Hollow Knight: Silksong's Hornet, read from the installed game's Addressables bundles. Read-only. Used by
import_hk_game.py, which puts her in the Hollow Knight frame data as another character.

The hero prefab (Hero_Hornet, the GameObject with HeroController) is in heroloading_assets_all.bundle. Each crest
has its slash objects under Attacks/<crest>; this reads the Hunter crest (Attacks/Default), whose body animations
are the hero's own library (other crests swap in an override library their HeroControllerConfig names, and those
configs are not in the shipped bundles, nor are the crests' attack durations and cooldowns).

NailSlash.OnAnimationEventTriggered turns a slash's collider on at its effect clip's first trigger frame and off at
the second, so the hitbox windows below come from the clips. Downspike and DashStabNailAttack keep theirs on for
the effect clip (their exact times are config values).
"""
import hk_unity
from hk_render import Timeline, Xf, frame_of, FPS
import hk_fsm

BUNDLE = hk_unity.AA + '/heroloading_assets_all.bundle'

def find_hero(g):
    for f in g.files.values():
        for o in f.objects.values():
            if g.script(o) == 'HeroController':
                return f.objects[hk_unity.mono_header(o.get_raw_data())[0]], g.mono(o)
    raise KeyError('HeroController')

def triggers(clip):
    return [i / clip['fps'] for i, fr in enumerate(clip['frames']) if fr.get('triggerEvent') and fr.get('eventInfo') != 'Bounce']

def build(B, a, hc):
    """Add Hornet's moves to builder B (a Builder over actor a)."""
    k = a
    crest = 'Attacks/Default'
    def clip_len(name): c = k.clips[name]; return len(c['frames']) / c['fps']
    rows = [('Slash', 'slash', 'Slash', ['Slash'], 'any', 'Side slash, Hunter crest'),
            ('AltSlash', 'altSlash', 'Alt Slash', ['SlashAlt'], 'any', 'The second of the alternating side slashes'),
            ('UpSlash', 'upSlash', 'Up Slash', ['UpSlash'], 'any', 'Slash upward'),
            ('WallSlash', 'wallSlash', 'Wall Slash', ['Wall Slash'], 'wall', 'Slash away from the wall while clinging'),
            ('DownSlash', 'downSpike', 'Down Spike', ['DownSpike Antic', 'DownSpike'], 'air', 'Diagonal downward thrust in the air; a hit bounces Hornet up'),
            ('Dash Stab', 'dashStab', 'Dash Stab', ['Dash Attack Antic', 'Dash Attack', 'Dash Attack Recover'], 'ground', 'Attack while sprinting: a lunging stab')]
    for obj, mid, name, body, grip, desc in rows:
        path = crest + '/' + obj
        o = k.obj(path)
        ns = k.g.comp(o, 'NailSlash')
        lib, defclip = k.animator(path)
        eff = lib['byName'].get(k.g.mono(ns)['animName']) if ns is not None else defclip
        # the body plays its clips back to back; the slash starts with the last antic clip done
        seq, t = [], 0.0
        for c in body:
            seq.append((t, c)); t += clip_len(c)
        start = seq[1][0] if len(seq) > 1 and 'Antic' in body[0] else 0.0
        tr = triggers(eff)
        if ns is not None and len(tr) >= 2: h0, h1 = start + tr[0], start + tr[1]
        else: h0, h1 = start, start + hk_fsm.clip_time(eff)
        total = max(t, start + hk_fsm.clip_time(eff))
        tl = Timeline(total)
        B.knight_layer(tl, seq)
        tl.sprite(k.coll_of(o), [(start, eff)], start, start + hk_fsm.clip_time(eff), k.sprite_xf(path), z=1)
        for shp in k.polys(path): tl.box('a', ('span', h0, h1), shp)
        B.hurt(tl, total)
        B.add(f'silksong.hunter.{mid}', 'nail', grip, name, tl, total, [('span', h0, h1)], desc=desc,
              extra={'Hornet animation': ' → '.join(f"{c} ({len(k.clips[c]['frames'])} frames at {k.clips[c]['fps']:g} fps)" for c in body),
                     'Hitbox': f"{eff['name']} trigger frames" if ns is not None else f"{eff['name']}, whole clip"})
    # movement
    G = 60.0 * hc['DEFAULT_GRAVITY']
    def simple(mid, name, clips, total, grip, desc, iframes=(), extra=None, pos=None, cancels=None):
        tl = Timeline(total)
        if pos: tl.pos = pos
        B.knight_layer(tl, clips)
        B.hurt(tl, total)
        B.add(f'silksong.movement.{mid}', 'movement', grip, name, tl, total, [], iframes=iframes, desc=desc, extra=extra, cancels=cancels)
    dt = hc['DASH_TIME']
    simple('dash', 'Dash', [(0, 'Dash')], max(dt, clip_len('Dash')), 'any', 'Dash; held, it carries on into a sprint',
           extra={'Dash time': f'{dt:.2f} s at {hc["DASH_SPEED"]:g} units/s', 'Cooldown': f"{hc['DASH_COOLDOWN']:.3f} s"},
           pos=lambda t, v=hc['DASH_SPEED'], T=dt: (-v * min(t, T), 0.0))
    # full jump: JUMP_STEPS physics steps at JUMP_SPEED, then gravity
    pts, y, v, t, n = [], 0.0, 0.0, 0.0, 0
    while True:
        v = hc['JUMP_SPEED'] if n < hc['JUMP_STEPS'] else max(v - G * hk_fsm.STEP, -hc['MAX_FALL_VELOCITY'])
        y += v * hk_fsm.STEP; t += hk_fsm.STEP; n += 1; pts.append((t, y))
        if y <= 0 and n > hc['JUMP_STEPS']: break
    T = pts[-1][0]
    def pos(t, pts=pts):
        yy = 0.0
        for tt, py in pts:
            if tt > t: break
            yy = py
        return (0.0, max(yy, 0.0))
    land = 'Slash Land' if 'Land' not in k.clips else 'Land'
    simple('jump', 'Jump', [(0, 'Airborne' if 'Airborne' in k.clips else 'Double Jump'), (T, land)], T + clip_len(land), 'ground',
           'Full-height jump from the ground', pos=pos,
           extra={'Height': f'{max(p for _, p in pts):.2f} units', 'Air time': f'{T:.2f} s',
                  'Rise': f"{hc['JUMP_STEPS']} physics steps at {hc['JUMP_SPEED']:g} units/s, then gravity {G:g} units/s²"})
    simple('doubleJump', 'Double Jump', [(0, 'Double Jump')], clip_len('Double Jump'), 'air', 'Faydown Cloak double jump (animation)')
    inv = hc['INVUL_TIME']
    simple('hit', 'Take hit', [(0, 'Recoil'), (clip_len('Recoil'), 'Idle Hurt')], inv, 'any', 'Hit reaction: knocked back, then invulnerable',
           iframes=[('span', 0, inv)], cancels={'dodge': frame_of(hc['RECOIL_DURATION'])},
           extra={'I-frames': f'{inv:.2f} s', 'Recoil': f"{hc['RECOIL_DURATION']:.2f} s at {hc['RECOIL_VELOCITY']:g} units/s"})
    simple('death', 'Death', [(0, 'Death')], clip_len('Death'), 'any', 'Death animation')
    simple('bind', 'Bind (heal)', [(0, 'BindCharge Ground'), (clip_len('BindCharge Ground'), 'BindBurst Ground')],
           clip_len('BindCharge Ground') + clip_len('BindBurst Ground'), 'ground', 'Bind: spend silk to heal, on the ground')

"""Timing out of PlayMaker FSMs (Hollow Knight, Silksong). Read-only.

simulate() walks an FSM from a state the way the game would: a state ends on the first of its timed events (a Wait,
an animation it plays or watches reaching its end or its trigger frame, a frame counter reaching its target), or
at once on FINISHED when nothing in it waits. Branches the game decides at run time (button presses, facing, ground
checks) are taken from `choose`. The result is a list of what happened when, in seconds from entering the first
state: states entered, clips played on the owner, game objects switched on and off, colliders enabled.
"""
import math
from hk_unity import actions, transitions

STEP = 0.02          # Time.fixedDeltaTime (TimeManager: 2822399 / 141120000 s)

def var(fsm, v, kind='float'):
    """The value of an action parameter: a literal, or the FSM variable it names (its default)."""
    if isinstance(v, dict) and 'var' in v:
        name = v['var']
        if not name: return v.get('value')
        for lst in ('floatVariables', 'intVariables', 'boolVariables', 'stringVariables', 'gameObjectVariables'):
            for x in fsm['variables'].get(lst, []):
                if x['name'] == name: return x['value']
        return v.get('value')
    return v

def owner_target(p):
    """'' for the FSM's owner, else the game object variable a parameter names."""
    g = p.get('gameObject')
    if isinstance(g, dict) and 'ownerOption' in g:
        if g['ownerOption'] == 0: return ''
        gg = g['gameObject']
        return gg.get('name') if gg.get('useVariable') else ('#%d' % gg.get('value', {}).get('m_PathID', 0))
    if isinstance(g, dict) and 'var' in g: return g['var'] or ''
    return None

def clip_time(clip):
    return len(clip['frames']) / clip['fps'] if clip and clip['fps'] else 0.0

def trigger_time(clip, after=-1.0):
    """Time of the clip's first trigger frame later than `after` (seconds into the clip)."""
    for i, f in enumerate(clip['frames'] if clip else []):
        if f.get('triggerEvent') and i / clip['fps'] > after + 1e-9: return i / clip['fps']
    return None

class Run:
    def __init__(self):
        self.events = []          # (t, kind, value)
    def add(self, t, kind, value): self.events.append((round(t, 6), kind, value))
    def first(self, kind, value=None):
        return next((t for t, k, v in self.events if k == kind and (value is None or v == value)), None)
    def all(self, kind): return [(t, v) for t, k, v in self.events if k == kind]
    @property
    def end(self): return self.events[-1][0] if self.events else 0.0

def simulate(fsm, start, clips, choose=None, max_states=60, owner_clip=None, stop=None, max_time=8.0):
    """Walk fsm from state `start`. clips: name -> tk2d clip of the owner's animator. choose: state name -> event
    name, or -> (event, seconds after entering) for events the walk can't time itself, or -> None to stop there. stop(name, state) ends the walk before entering a state."""
    choose = choose or {}
    states = {s['name']: s for s in fsm['states']}
    run = Run()
    t = 0.0
    clip, clip_t0 = owner_clip, 0.0          # what the owner's animator is playing, and since when
    name = start
    for _ in range(max_states):
        s = states.get(name)
        if s is None or t > max_time: break
        if stop and name != start and stop(name, s): break
        run.add(t, 'state', name)
        trans = dict(transitions(s))
        timed = []                         # (time, event)
        for a, p in actions(s):
            tgt = owner_target(p)
            if a == 'Wait':
                timed.append((t + float(var(fsm, p.get('time')) or 0), p.get('finishEvent') or 'FINISHED'))
            elif a in ('Tk2dPlayAnimation', 'Tk2dPlayAnimationWithEvents', 'Tk2dPlayAnimationWithEventsV2') and tgt is not None:
                nm = var(fsm, p.get('clipName'))
                if tgt:
                    run.add(t, 'childclip', (tgt, nm))
                elif nm in clips:
                    clip, clip_t0 = clips[nm], t
                    run.add(t, 'clip', nm)
                if a != 'Tk2dPlayAnimation' and not tgt:
                    if p.get('animationCompleteEvent') and clip: timed.append((clip_t0 + clip_time(clip), p['animationCompleteEvent']))
                    tr = trigger_time(clip)
                    if p.get('animationTriggerEvent') and tr is not None: timed.append((clip_t0 + tr, p['animationTriggerEvent']))
            elif a in ('Tk2dWatchAnimationEvents',) and tgt == '' and clip:
                if p.get('animationCompleteEvent'): timed.append((max(t, clip_t0 + clip_time(clip)), p['animationCompleteEvent']))
                tr = trigger_time(clip, t - clip_t0)
                if p.get('animationTriggerEvent') and tr is not None: timed.append((clip_t0 + tr, p['animationTriggerEvent']))
            elif a == 'ActivateGameObject':
                run.add(t, 'on' if p.get('activate') else 'off', tgt if tgt is not None else '')
            elif a == 'ActivateAllChildren':
                run.add(t, 'children', bool(p.get('activate')))
            elif a == 'SetBoxCollider2DSizeVector' and owner_target({'gameObject': p.get('gameObject1')}) == '':
                sz, off = var(fsm, p.get('size')), var(fsm, p.get('offset'))
                if isinstance(sz, (tuple, list)) and isinstance(off, (tuple, list)): run.add(t, 'bodybox', (tuple(sz), tuple(off)))
            elif a in ('SetPolygonCollider', 'SetBoxCollider', 'SetCollider'):
                run.add(t, 'collider', (tgt or '', bool(p.get('active'))))
            elif a in ('SendMessage', 'SendMessageV2', 'CallMethodProper', 'CallMethod'):
                fn = (p.get('functionCall') or {}).get('FunctionName') or p.get('methodName')
                if fn: run.add(t, 'call', fn)
            elif a in ('SpawnObjectFromGlobalPool', 'CreateObject'):
                g = p.get('gameObject')
                run.add(t, 'spawn', g.get('m_PathID') if isinstance(g, dict) else None)
        pick = choose.get(name, '')
        if pick is None: break
        nxt = None
        if isinstance(pick, tuple):
            ev, dt = pick; nxt = trans.get(ev); t = t + dt
        elif pick:
            ev = pick
            # a chosen event that is also timed in this state waits for its time
            when = [tt for tt, e in timed if e == ev]
            if when: t = min(when)
            nxt = trans.get(ev)
        else:
            cands = sorted((tt, e) for tt, e in timed if e in trans)
            if cands:
                t, ev = cands[0]; nxt = trans[ev]
            elif 'FINISHED' in trans:
                nxt = trans['FINISHED']
        if not nxt: break
        name = nxt
    run.add(t, 'end', name)
    return run

def counter_windows(fsm):
    """Collider windows of a frame-counter FSM (Great Slash and Dash Slash's Control Collider): Check Start resets
    a counter that IntAddV2 raises on entering and on every physics step, Enable turns the collider on until the
    counter reaches its target. Returns (first step on, first step off) counted from activation, or None."""
    states = {s['name']: s for s in fsm['states']}
    def target(state):
        for a, p in actions(states[state]):
            if a == 'IntCompare': return int(var(fsm, p.get('integer2')) or 0)
        return 0
    if 'Check Start' not in states or 'Enable' not in states: return None
    on, off = target('Check Start'), target('Enable')
    # the counter is 1 on entering Check Start and k + 1 after k physics steps, and carries on through Enable
    k_on = max(on - 1, 0)
    k_off = max(off - 1, k_on + 1)
    return k_on, k_off

def steps_between(t0, t1):
    """Physics step times in [t0, t1) when steps run at multiples of STEP after t = 0."""
    k = math.ceil(t0 / STEP - 1e-9)
    out = []
    while k * STEP < t1 - 1e-9:
        out.append(round(k * STEP, 6)); k += 1
    return out

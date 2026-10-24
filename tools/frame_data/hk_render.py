"""Sprite sheets for the 2D preview from a move's timeline (Hollow Knight, Silksong).

A Timeline says, in seconds from the start of the move, what is drawn and which boxes are out: the character's
clips (and where it is, for jumps), effect objects with their own clips and transforms, attack polygons and boxes,
hurtboxes. render() samples it at the tab's 60 fps: frame N covers [(N-1)/60, N/60), sprites show what is on screen
at its start, and a box counts for a frame when it is out at any instant of it (hit windows that live on 50 Hz
physics steps are lists of instants). Coordinates are the character's local space in world units, y up; the
character's art faces left, so everything is mirrored to face right on the way out.
"""
import math
from PIL import Image

FPS = 60

def frame_of(t):
    """1-based tab frame that holds time t."""
    return int(math.floor(t * FPS + 1e-6)) + 1

def frames_of(window):
    """Tab frames a window touches: ('steps', [t...]) instants, or ('span', t0, t1) half open."""
    if window[0] == 'steps':
        # a collider stays on between the steps that can hit with it, so the run from the first to the last counts
        fs = [frame_of(t) for t in window[1]]
        return list(range(min(fs), max(fs) + 1)) if fs else []
    t0, t1 = window[1], window[2]
    if t1 <= t0: return []
    return list(range(frame_of(t0), frame_of(t1 - 1e-6) + 1))

def windows(frames):
    """[[s, e]] runs of consecutive frames."""
    out = []
    for f in sorted(set(frames)):
        if out and f == out[-1][1] + 1: out[-1][1] = f
        else: out.append([f, f])
    return out

class Xf:
    """2D transform: scale, rotation (radians), then translation."""
    def __init__(self, x=0.0, y=0.0, sx=1.0, sy=1.0, rot=0.0):
        self.x, self.y, self.sx, self.sy, self.rot = x, y, sx, sy, rot
    def apply(self, px, py):
        px, py = px * self.sx, py * self.sy
        c, s = math.cos(self.rot), math.sin(self.rot)
        return self.x + c * px - s * py, self.y + s * px + c * py
    def then(self, parent):
        """This transform inside `parent` (parent applied after)."""
        x, y = parent.apply(self.x, self.y)
        return Xf(x, y, self.sx * parent.sx, self.sy * parent.sy, self.rot + parent.rot)

def clip_frame(clip, dt):
    """Index of the clip frame shown dt seconds after it started (tk2d wrap modes)."""
    n = len(clip['frames'])
    if n == 0: return None
    i = int(math.floor(dt * clip['fps'] + 1e-6)) if clip['fps'] else 0
    w = clip['wrapMode']
    if w == 0: return i % n                                   # loop
    if w == 1:                                                # loop section
        ls = clip.get('loopStart', 0) or 0
        return i if i < n else ls + (i - ls) % max(n - ls, 1)
    if w == 4:                                                # ping pong
        if n == 1: return 0
        p = i % (2 * n - 2); return p if p < n else 2 * n - 2 - p
    if w in (5, 6): return 0                                  # single frame
    return min(i, n - 1)                                      # once

class Timeline:
    def __init__(self, total):
        self.total = total                       # seconds
        self.layers = []                         # draw order
        self.boxes = []                          # (kind, window, shape-fn(t) -> polygon or rect in local units)
        self.pos = lambda t: (0.0, 0.0)          # character offset (jumps)

    def sprite(self, coll_of, clips, t0, t1, xf, z=0, moving=None, ends_with_clip=False):
        """A sprite object playing `clips` [(start, clip)] between t0 and t1. coll_of(frame) -> collection.
        moving: t -> (dx, dy) extra offset (projectiles). The character layer follows self.pos."""
        self.layers.append(dict(coll_of=coll_of, clips=sorted(clips, key=lambda c: c[0]), t0=t0, t1=t1, xf=xf, z=z,
                                moving=moving, once=ends_with_clip))

    def box(self, kind, window, shape, follow=True, moving=None):
        """shape: ('poly', [(x, y)...]) or ('rect', x0, y0, x1, y1), already in character space."""
        self.boxes.append((kind, window, shape, follow, moving))

def _layer_at(L, t, sprites):
    if not (L['t0'] <= t < L['t1']): return None
    cur = None
    for st, clip in L['clips']:
        if st <= t: cur = (st, clip)
    if cur is None: return None
    st, clip = cur
    if L['once'] and clip['wrapMode'] == 2 and (t - st) * clip['fps'] >= len(clip['frames']): return None
    i = clip_frame(clip, t - st)
    if i is None: return None
    fr = clip['frames'][i]
    coll = L['coll_of'](fr)
    if coll is None: return None
    sd = coll['spriteDefinitions'][fr['spriteId']]
    if not sd.get('positions'): return None
    return sprites.sprite(coll, fr['spriteId'])

def render(tl, sprites, ppu=64, max_cell=420, clip_box=None, flip=True):
    """(frames as RGBA images, per frame [boxes], cell w, h, ppu used). clip_box: (x0, y0, x1, y1) in local units to
    crop to (projectiles flying off)."""
    N = max(1, frame_of(tl.total - 1e-6))
    samples = []
    for f in range(1, N + 1):
        t = (f - 1) / FPS
        cx, cy = tl.pos(t)
        items = []
        for L in sorted(tl.layers, key=lambda L: L['z']):
            got = _layer_at(L, t, sprites)
            if not got: continue
            img, (x0, y1), tex = got
            xf = L['xf']
            ox, oy = (cx, cy) if L.get('follow', True) else (0, 0)
            if L['moving']:
                mx, my = L['moving'](t); ox += mx; oy += my
            # sprite corners in object space -> character space
            w, h = img.size[0] * tex, img.size[1] * tex
            corners = [xf.apply(x0, y1), xf.apply(x0 + w, y1), xf.apply(x0, y1 - h), xf.apply(x0 + w, y1 - h)]
            corners = [(a + ox, b + oy) for a, b in corners]
            items.append((img, tex, xf, (x0, y1), (ox, oy), corners))
        bx = []
        for kind, window, shape, follow, moving in tl.boxes:
            if f not in window_frames(window): continue
            ox, oy = (cx, cy) if follow else (0, 0)
            if moving:
                mx, my = moving(t); ox += mx; oy += my
            if shape[0] == 'poly': pts = [(x + ox, y + oy) for x, y in shape[1]]
            else:
                _, a, b, c, d = shape; pts = [(a + ox, b + oy), (c + ox, b + oy), (c + ox, d + oy), (a + ox, d + oy)]
            bx.append((kind, shape[0], pts))
        samples.append((items, bx))
    # bounds over the whole move
    xs, ys = [], []
    for items, bx in samples:
        for it in items:
            for a, b in it[5]: xs.append(a); ys.append(b)
        for _, _, pts in bx:
            for a, b in pts: xs.append(a); ys.append(b)
    if not xs: xs, ys = [-0.5, 0.5], [-1, 1]
    X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)
    if clip_box:
        X0, Y0 = max(X0, clip_box[0]), max(Y0, clip_box[1]); X1, Y1 = min(X1, clip_box[2]), min(Y1, clip_box[3])
    pad = 0.15
    X0, X1, Y0, Y1 = X0 - pad, X1 + pad, Y0 - pad, Y1 + pad
    s = min(ppu, max_cell / max(X1 - X0, Y1 - Y0))
    W, H = int(math.ceil((X1 - X0) * s)), int(math.ceil((Y1 - Y0) * s))
    def px(a, b):
        x = (a - X0) * s
        if flip: x = W - x
        return x, (Y1 - b) * s
    frames, boxes = [], []
    for items, bx in samples:
        canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        for img, tex, xf, (x0, y1), (ox, oy), corners in items:
            k = s * tex
            sw, sh = abs(xf.sx) * k, abs(xf.sy) * k
            im = img
            tw, th = max(1, round(im.size[0] * sw)), max(1, round(im.size[1] * sh))
            im = im.resize((tw, th), Image.BILINEAR)
            if (xf.sx < 0) != flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
            if xf.sy < 0: im = im.transpose(Image.FLIP_TOP_BOTTOM)
            if abs(xf.rot) > 1e-3:
                deg = math.degrees(xf.rot) * (-1 if flip else 1)
                im = im.rotate(deg, resample=Image.BILINEAR, expand=True)
            # place by the centre of the sprite's corners
            cxw = sum(c[0] for c in corners) / 4; cyw = sum(c[1] for c in corners) / 4
            pcx, pcy = px(cxw, cyw)
            canvas.alpha_composite(im, (int(round(pcx - im.size[0] / 2)), int(round(pcy - im.size[1] / 2)))) if \
                _fits(canvas, im, pcx, pcy) else _paste_clipped(canvas, im, pcx, pcy)
        frames.append(canvas)
        out = []
        for kind, sh, pts in bx:
            P = [px(a, b) for a, b in pts]
            if sh == 'rect':
                xs_, ys_ = [p[0] for p in P], [p[1] for p in P]
                out.append([kind, round(min(xs_)), round(min(ys_)), round(max(xs_)) - 1, round(max(ys_)) - 1])
            else:
                out.append([kind, [round(v, 1) for p in P for v in p]])
        boxes.append(out)
    return frames, boxes, W, H, s

def window_frames(window):
    key = id(window)
    c = _wcache.get(key)
    if c is None or c[0] is not window:
        c = (window, set(frames_of(window))); _wcache[key] = c
    return c[1]
_wcache = {}

def _fits(canvas, im, cx, cy):
    x, y = int(round(cx - im.size[0] / 2)), int(round(cy - im.size[1] / 2))
    return x >= 0 and y >= 0 and x + im.size[0] <= canvas.size[0] and y + im.size[1] <= canvas.size[1]

def _paste_clipped(canvas, im, cx, cy):
    x, y = int(round(cx - im.size[0] / 2)), int(round(cy - im.size[1] / 2))
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.size[0], canvas.size[0] - x), min(im.size[1], canvas.size[1] - y)
    if r <= l or b <= t: return
    canvas.alpha_composite(im.crop((l, t, r, b)), (x + l, y + t))

def sheet(frames, W, H, max_w=4096):
    cols = max(1, min(len(frames), max_w // max(W, 1)))
    rows = math.ceil(len(frames) / cols)
    img = Image.new('RGBA', (cols * W, rows * H), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        img.paste(fr, ((i % cols) * W, (i // cols) * H))
    return img, cols

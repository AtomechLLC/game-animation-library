"""Reads the Havok 2018 tagfiles Elden Ring stores skeletons and animations in, and decompresses spline animations.

    read_tagfile(data, compendium=None)  any TAG0 file -> the root object as nested dicts and lists
    skeleton(root)                        -> bone names, parent indices, reference pose
    animation(root)                       -> per-frame local transforms per bone, plus root motion

Animation files in the .anibnd archives have no type section of their own (TCRF): their types are in the archive's
.compendium file (TCM0), which has to be passed in. Format notes follow soulstruct-havok by Grimrukh
(https://github.com/Grimrukh/soulstruct-havok): tagfile/unpacker.py and spline_compression.py.
"""
import math, struct
import numpy as np

# --- tagfile -------------------------------------------------------------------------------------------------------

def _sections(data, start, end):
    """Yields (magic, body start, body end) for each section in [start, end)."""
    p = start
    while p + 8 <= end:
        size = struct.unpack_from('>I', data, p)[0] & 0x3FFFFFFF
        yield data[p+4:p+8].decode('ascii'), p + 8, p + size
        p += size

def _varint(data, p):
    b = data[p]
    if not b & 0x80: return b, p + 1
    if b == 0xC3: return data[p+1] << 8 | data[p+2], p + 3
    m = b >> 3
    if 0x10 <= m < 0x18: return (b << 8 | data[p+1]) & 0x3FFF, p + 2
    if 0x18 <= m < 0x1C: return (b << 16 | data[p+1] << 8 | data[p+2]) & 0x1FFFFF, p + 3
    if m == 0x1C: return struct.unpack_from('>I', data, p)[0] & 0x7FFFFFF, p + 4
    raise ValueError(f'unsupported varint marker {b:#x}')

class Type:
    __slots__ = ('name', 'templates', 'parent', 'fmt', 'sub', 'ptr', 'size', 'align', 'members')
    def __init__(self, name):
        self.name, self.templates, self.parent = name, [], None
        self.fmt = self.sub = self.ptr = self.size = self.align = None
        self.members = []
    def find(self, attr):
        t = self
        while t is not None:
            v = getattr(t, attr)
            if v not in (None, []): return v
            t = t.parent
        return None
    def all_members(self):
        return (self.parent.all_members() if self.parent else []) + self.members
    def __repr__(self): return f'Type({self.name})'

def _read_types(data, start, end):
    sec = {m: (s, e) for m, s, e in _sections(data, start, end)}
    s, e = sec.get('TSTR') or sec['TST1']
    tnames = data[s:e].decode('utf-8').split('\0')
    s, e = sec.get('FSTR') or sec['FST1']
    fnames = data[s:e].decode('utf-8').split('\0')
    s, e = sec.get('TNAM') or sec['TNA1']
    n, p = _varint(data, s)
    types = [None]
    for _ in range(n - 1):
        ni, p = _varint(data, p); tc, p = _varint(data, p)
        t = Type(tnames[ni])
        for _ in range(tc):
            a, p = _varint(data, p); v, p = _varint(data, p)
            t.templates.append((tnames[a], v))
        types.append(t)
    s, e = sec.get('TBOD') or sec['TBDY']
    p = s
    while p < e:
        ti, p = _varint(data, p)
        if ti == 0: continue
        t = types[ti]
        pi, p = _varint(data, p)
        t.parent = types[pi] if pi else None
        t.fmt, p = _varint(data, p)
        if t.fmt & 0x01: t.sub, p = _varint(data, p)
        if t.fmt & 0x02 and (t.sub or 0) & 0xF >= 6:
            pt, p = _varint(data, p); t.ptr = types[pt] if pt else None
        if t.fmt & 0x04: _, p = _varint(data, p)
        if t.fmt & 0x08:
            t.size, p = _varint(data, p); t.align, p = _varint(data, p)
        if t.fmt & 0x10: _, p = _varint(data, p)
        if t.fmt & 0x20:
            mc, p = _varint(data, p)
            for _ in range(mc):
                mn, p = _varint(data, p); _, p = _varint(data, p); mo, p = _varint(data, p); mt, p = _varint(data, p)
                t.members.append((fnames[mn], mo, types[mt]))
        if t.fmt & 0x40:
            ic, p = _varint(data, p)
            for _ in range(ic * 2): _, p = _varint(data, p)
        if t.fmt & 0x80: raise ValueError(f'unknown type flag on {t.name}')
    return types

def read_compendium(data):
    """TCM0 compendium -> (ids, types)."""
    (magic, s, e), = list(_sections(data, 0, len(data)))
    assert magic == 'TCM0', magic
    ids, types = [], None
    for m, a, b in _sections(data, s, e):
        if m == 'TCID': ids = [data[i:i+8] for i in range(a, b, 8)]
        if m == 'TYPE': types = _read_types(data, a, b)
    return ids, types

class _Reader:
    def __init__(self, data, dstart, items):
        self.d, self.dstart, self.items = data, dstart, items
        self.cache = {}

    def value(self, t, off):
        sub = t.find('sub') or 0
        kind = sub & 0xF
        if kind == 0 or kind == 1: return None
        if kind == 2: return bool(self.d[off])
        if kind == 3: return self.string(off)
        if kind == 4:
            size = t.find('size')
            return int.from_bytes(self.d[off:off+size], 'little', signed=bool(sub & 0x200))
        if kind == 5:
            return struct.unpack_from('<f' if t.find('size') == 4 else '<d', self.d, off)[0]
        if kind == 6: return self.item(struct.unpack_from('<I', self.d, off)[0])
        if kind == 7: return self.record(t, off)
        if kind == 8:
            if sub & 0x20:  # fixed length T[N] stored inline
                et, n = t.find('ptr'), sub >> 8
                es = et.find('size')
                return self.elements(et, off, n, es)
            return self.item(struct.unpack_from('<I', self.d, off)[0])
        raise ValueError(f'unsupported kind {kind} for {t.name}')

    def record(self, t, off):
        members = t.all_members()
        if not members:  # opaque wrapper (e.g. hkHandle); read as its underlying value if any
            return None
        return {name: self.value(mt, off + mo) for name, mo, mt in members}

    def string(self, off):
        i = struct.unpack_from('<I', self.d, off)[0]
        if not i: return None
        t, o, n = self.items[i]
        return self.d[o:o+n].split(b'\0', 1)[0].decode('utf-8', 'replace')

    def elements(self, et, off, n, es):
        sub = et.find('sub') or 0
        kind = sub & 0xF
        if kind == 4 and es in (1, 2, 4, 8):
            code = {1: 'b', 2: 'h', 4: 'i', 8: 'q'}[es]
            if not sub & 0x200: code = code.upper()
            return np.frombuffer(self.d, dtype='<' + code, count=n, offset=off)
        if kind == 5 and es == 4:
            return np.frombuffer(self.d, dtype='<f4', count=n, offset=off)
        return [self.value(et, off + i * es) for i in range(n)]

    def item(self, i):
        if not i: return None
        if i in self.cache: return self.cache[i]
        t, o, n = self.items[i]
        es = t.find('size')
        kind = (t.find('sub') or 0) & 0xF
        self.cache[i] = None  # breaks cycles
        # pointer items (flag 0x10) hold one object; the rest are array contents
        v = self.record(t, o) if self.flags[i] & 0x10 else self.elements(t, o, n, es)
        self.cache[i] = v
        return v

def read_tagfile(data, compendium=None):
    """TAG0 -> root object (dicts keyed by member name; arrays of numbers as numpy arrays)."""
    (magic, s, e), = list(_sections(data, 0, len(data)))
    assert magic == 'TAG0', magic
    types, dstart, items, flags = None, None, None, None
    for m, a, b in _sections(data, s, e):
        if m == 'DATA': dstart = a
        elif m == 'TYPE': types = _read_types(data, a, b)
        elif m == 'TCRF':
            cid = data[a:a+8]
            if compendium is None or cid not in compendium[0]: raise ValueError('needs the matching .compendium')
            types = compendium[1]
        elif m == 'INDX':
            for mm, aa, bb in _sections(data, a, b):
                if mm != 'ITEM': continue
                items, flags = [], []
                for p in range(aa, bb, 12):
                    info, rel, n = struct.unpack_from('<III', data, p)
                    items.append((types[info & 0xFFFFFF], dstart + rel, n) if info else None)
                    flags.append(info >> 24)
    r = _Reader(data, dstart, items)
    r.flags = flags
    return r.item(1)

def named_variants(root):
    """hkRootLevelContainer -> {class name: object} for its named variants."""
    return {v['className']: v['variant'] for v in root['namedVariants']}

# --- skeleton ------------------------------------------------------------------------------------------------------

def find_objects(root, has):
    """All dicts reachable from root that have every key in `has`."""
    out, seen, stack = [], set(), [root]
    while stack:
        o = stack.pop()
        if id(o) in seen: continue
        seen.add(id(o))
        if isinstance(o, dict):
            if all(k in o for k in has): out.append(o)
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    return out

def skeleton(root):
    """-> (bone names, parent indices, reference pose as [(t xyz, q xyzw, s xyz)])."""
    sk = find_objects(root, ('bones', 'parentIndices', 'referencePose'))[0]
    names = [b['name'] for b in sk['bones']]
    parents = [int(p) for p in sk['parentIndices']]
    pose = [(tuple(map(float, q['translation'][:3])), tuple(map(float, q['rotation']['vec'][:4]
             if isinstance(q['rotation'], dict) else q['rotation'][:4])), tuple(map(float, q['scale'][:3])))
            for q in sk['referencePose']]
    return names, parents, pose

# --- spline animation ----------------------------------------------------------------------------------------------

_ROT_SIZE = {0: 4, 1: 5, 2: 6, 3: 3, 4: 2, 5: 16}
_ROT_ALIGN = {0: 4, 1: 1, 2: 2, 3: 1, 4: 2, 5: 4}
_TC40_START, _TC40_STEP = -math.sqrt(2) / 2, math.sqrt(2) / 4094

def _quat(b, kind):
    if kind == 1:
        c = int.from_bytes(b, 'little')
        q = [_TC40_START + ((c >> s) & 0xFFF) * _TC40_STEP for s in (0, 12, 24)]
        w = 1.0 - sum(v * v for v in q)
        w = math.sqrt(w) if w > 0 else 0.0
        if (c >> 38) & 1: w = -w
        q.insert((c >> 36) & 3, w)
        return q
    if kind == 2:
        x, y, z = struct.unpack('<hhh', b)
        shift = ((y >> 14) & 2) | ((x >> 15) & 1)
        neg = (z >> 15) & 1
        m = (1 << 15) - 1
        v = [((c & m) - (m >> 1)) * 0.000043161 for c in (x, y, z)]
        w = 1.0 - sum(a * a for a in v)
        w = (math.sqrt(w) if w > 0 else 0.0) * (-1 if neg else 1)
        v.insert(shift, w)
        return v
    if kind == 5: return list(struct.unpack('<4f', b))
    if kind == 0:
        c = int.from_bytes(b, 'little')
        rmask = (1 << 10) - 1
        r = ((c >> 18) & rmask) / rmask
        r = 1.0 - r * r
        pt = float(c & 0x3FFFF)
        phi = float(math.floor(math.sqrt(pt))); theta = 0.0
        if phi > 0:
            theta = (math.pi / 4) * (pt - phi * phi) / phi
            phi *= math.pi / 4 / 511.0
        mag = math.sqrt(max(0.0, 1.0 - r * r))
        q = [math.sin(phi) * math.cos(theta) * mag, math.sin(phi) * math.sin(theta) * mag, math.cos(phi) * mag, r]
        for i, bit in enumerate((0x10000000, 0x20000000, 0x40000000, 0x80000000)):
            if c & bit: q[i] = -q[i]
        return q
    raise ValueError(f'rotation quantization {kind} not supported')

def _basis(span, degree, t, knots):
    n = [1.0, 0.0, 0.0, 0.0, 0.0]
    for i in range(1, degree + 1):
        for j in range(i - 1, -1, -1):
            a = (t - knots[span - j]) / (knots[span + i - j] - knots[span - j])
            tmp = n[j] * a
            n[j + 1] += n[j] - tmp
            n[j] = tmp
    return n

def _span(degree, t, count, knots):
    if t >= knots[count]: return count - 1
    lo, hi = degree, count
    g = (lo + hi) // 2
    while t < knots[g] or t >= knots[g + 1]:
        if t < knots[g]: hi = g
        else: lo = g
        g = (lo + hi) // 2
    return g

class _Spline:
    """Control points (count x dims) on a shared knot vector, evaluated at frames."""
    def __init__(self, degree, knots, points):
        self.degree, self.knots, self.points = degree, knots, np.asarray(points, dtype=np.float64)
    def at(self, t):
        cnt = len(self.points)
        s = _span(self.degree, t, cnt, self.knots)
        n = _basis(s, self.degree, t, self.knots)
        return sum(self.points[s - i] * n[i] for i in range(self.degree + 1))

class _Buf:
    def __init__(self, b): self.b, self.p = b, 0
    def align(self, n): self.p = (self.p + n - 1) // n * n
    def take(self, n): v = self.b[self.p:self.p+n]; self.p += n; return v
    def u(self, fmt): v = struct.unpack_from('<' + fmt, self.b, self.p); self.p += struct.calcsize('<' + fmt); return v

def _header(r):
    cnt, = r.u('h'); deg, = r.u('B')
    knots = list(r.take(cnt + 1 + deg + 1))
    return cnt + 1, deg, knots

def _vector(r, flags, q, default):
    """Translation or scale track -> callable(frame) -> xyz."""
    spline = flags & 0x70
    hdr = None
    if spline:
        hdr = _header(r); r.align(4)
    vals, bounds = [default] * 3, [None] * 3
    for a in range(3):
        if flags & (0x10 << a): bounds[a] = r.u('ff')
        elif flags & (1 << a): vals[a], = r.u('f')
    if not hdr:
        v = np.array(vals); return lambda t: v
    cnt, deg, knots = hdr
    pts = np.tile(np.array(vals, dtype=np.float64), (cnt, 1))
    scale = 255.0 if q == 0 else 65535.0
    for c in range(cnt):
        for a in range(3):
            if bounds[a] is None: continue
            raw, = r.u('B' if q == 0 else 'H')
            lo, hi = bounds[a]
            pts[c, a] = lo + (hi - lo) * raw / scale
    sp = _Spline(deg, knots, pts)
    return sp.at

def _rotation(r, flags, q):
    size = _ROT_SIZE[q]
    if flags & 0xF0:
        cnt, deg, knots = _header(r)
        r.align(_ROT_ALIGN[q])
        pts = [_quat(r.take(size), q) for _ in range(cnt)]
        sp = _Spline(deg, knots, pts)
        def at(t):
            v = sp.at(t); return v / (np.linalg.norm(v) or 1.0)
        return at
    if flags & 0x0F:
        v = np.array(_quat(r.take(size), q)); return lambda t: v
    v = np.array([0.0, 0.0, 0.0, 1.0]); return lambda t: v

def _blocks(data, tracks, nblocks, block_offsets):
    out = []
    for bi in range(nblocks):
        r = _Buf(data); r.p = int(block_offsets[bi])
        heads = [r.u('BBBB') for _ in range(tracks)]
        r.align(4)
        block = []
        for qt, tf, rf, sf in heads:
            t = _vector(r, tf, qt & 3, 0.0); r.align(4)
            q = _rotation(r, rf, (qt >> 2) & 0xF); r.align(4)
            s = _vector(r, sf, (qt >> 6) & 3, 1.0); r.align(4)
            block.append((t, q, s))
        out.append(block)
    return out

def animation(root):
    """-> dict(frames, fps, bones: {bone index: (T [frames,3], R [frames,4] xyzw, S [frames,3])},
    root_motion: [frames, 4] (xyz, yaw) or None)."""
    anim = find_objects(root, ('maxFramesPerBlock', 'blockOffsets', 'data'))
    binding = find_objects(root, ('transformTrackToBoneIndices',))[0]
    if not anim:
        raise ValueError('not a spline-compressed animation')
    a = anim[0]
    data = bytes(np.asarray(a['data'], dtype=np.uint8))
    tracks, nframes, nblocks = a['numberOfTransformTracks'], a['numFrames'], a['numBlocks']
    mfpb = a['maxFramesPerBlock']
    blocks = _blocks(data, tracks, nblocks, a['blockOffsets'])
    T = np.zeros((nframes, tracks, 3)); R = np.zeros((nframes, tracks, 4)); S = np.ones((nframes, tracks, 3))
    for f in range(nframes):
        bi, t = divmod(f, mfpb - 1)
        if bi >= nblocks: bi = nblocks - 1; t = f - bi * (mfpb - 1)
        for k, (tt, rr, ss) in enumerate(blocks[bi]):
            T[f, k], R[f, k], S[f, k] = tt(float(t)), rr(float(t)), ss(float(t))
    # keep quaternions on one hemisphere so interpolation between frames takes the short way
    for f in range(1, nframes):
        flip = np.sum(R[f] * R[f - 1], axis=1) < 0
        R[f, flip] *= -1
    bones = {}
    for k, b in enumerate(binding['transformTrackToBoneIndices']):
        bones[int(b)] = (T[:, k], R[:, k], S[:, k])
    fps = round(1.0 / a['frameDuration']) if a.get('frameDuration') else 30
    motion = None
    rf = a.get('extractedMotion')
    if isinstance(rf, dict) and rf.get('referenceFrameSamples') is not None and len(rf['referenceFrameSamples']):
        motion = np.asarray(rf['referenceFrameSamples'], dtype=np.float64).reshape(-1, 4)
    return {'frames': nframes, 'fps': fps, 'duration': a['duration'], 'bones': bones, 'root_motion': motion}

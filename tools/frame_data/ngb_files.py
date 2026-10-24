"""Ninja Gaiden Black (Xbox, 2005) file formats, read-only. Used by import_ngb_game.py.

Everything here was worked out from the bytes and checked against the game's own code (default.xbe, disassembled
with the ngbrecomp toolkit); see frame-data/scouting-ninja-gaiden-black.md for the notes.

  AFS        CRI archive: "AFS\\0", count, (offset, size) pairs, then a name table of 48-byte records.
  chr_dat    container of .mtn (motions + timeline scripts) and .chr (collision, state table, input rules):
             magic(8), 0, size, n, n, 0x20, 0x20, then n section offsets.
  .mot       a weapon's motion bank (rm_kt.mot = Dragon Sword): a motion table of 1992 u32 and the motions.
  .kmd       a model: OBJINFO (objects, bind translations), HIERARC (parents) and an XPR0 block of meshes and
             textures (KMD below).
  .itm       an item's attack shapes and where it mounts on the body (itm_shapes, itm_mounts).
"""
import fnmatch, os, struct
import numpy as np

u32 = lambda d, o: struct.unpack_from('<I', d, o)[0]
f32 = lambda d, o: struct.unpack_from('<f', d, o)[0]


# ---------------------------------------------------------------- archives

def afs(data):
    """{name: bytes} of an AFS archive."""
    assert data[:4] == b'AFS\0', 'not an AFS archive'
    n = u32(data, 4)
    ents = [struct.unpack_from('<II', data, 8 + 8 * i) for i in range(n)]
    no, ns = struct.unpack_from('<II', data, 8 + 8 * n)
    out = {}
    for i, (o, s) in enumerate(ents):
        name = data[no + 48 * i: no + 48 * i + 32].split(b'\0')[0].decode('latin-1') if ns == n * 48 else str(i)
        out[name] = data[o:o + s]
    return out


class Disc:
    """The game files, from the disc image (.iso, XDVDFS) or from a folder holding the .afs files."""
    def __init__(self, path):
        self.path = path
        self.iso = os.path.isfile(path)
        if self.iso:
            import ngb_xiso
            with open(path, 'rb') as f:
                self.entries = {os.path.basename(p).lower(): (o, n) for p, o, n in ngb_xiso.files(f)}

    def read(self, name):
        if self.iso:
            o, n = self.entries[name.lower()]
            with open(self.path, 'rb') as f:
                f.seek(o)
                return f.read(n)
        for root, _, files in os.walk(self.path):
            for fn in files:
                if fn.lower() == name.lower():
                    return open(os.path.join(root, fn), 'rb').read()
        raise FileNotFoundError(name)


def sections(data):
    """Section offsets of a chr_dat / chr_dat2 container (plus the end)."""
    n = u32(data, 0x10)
    return [u32(data, 0x20 + 4 * i) for i in range(n)] + [len(data)]


# ---------------------------------------------------------------- timeline scripts

# Words per command, by opcode (the rest take 2). 0x04 ends a script.
OP_LEN = {0x04: 6, 0x13: 6, 0x15: 6, 0x17: 6, 0x23: 6, 0x14: 4, 0x21: 4, 0x0d: 3, 0x0e: 3, 0x18: 3, 0x1f: 3,
          0x07: 1, 0x08: 1, 0x11: 1, 0x1b: 1}


def scripts(mtn):
    """Section 1 of ryu.mtn: one timeline script per state script id, as lists of u16."""
    sec = sections(mtn)
    s, end = sec[1], sec[2]
    n = u32(mtn, s) // 4
    offs = [u32(mtn, s + 4 * i) for i in range(n)]
    out = []
    for i in range(n):
        later = [o for o in offs[i + 1:] if o > offs[i]]
        b = s + (later[0] if later else end - s)
        w = list(struct.unpack_from('<%dH' % ((b - s - offs[i]) // 2), mtn, s + offs[i]))
        if 0xffff in w:
            w = w[:len(w) - w[::-1].index(0xffff)]
        out.append(w)
    return out


def events(words):
    """(frame, command) pairs of a script; '0 <frame>' waits for that frame of the motion. None if it doesn't parse.
    words[0:3] are '3 <motion> <n>'; a motion id of 10000 + m is motion m of the equipped weapon's bank."""
    if not words or words[0] != 3:
        return None
    i, f, out = 3, 0, []
    while i < len(words):
        op = words[i]
        if op == 0xffff:
            return out
        n = OP_LEN.get(op, 2)
        cmd = tuple(words[i:i + n])
        if op == 0:
            f = cmd[1]
        else:
            out.append((f, cmd))
        if op == 4:
            return out
        i += n
    return None


def attack_windows(evs):
    """Hitbox windows from the 0x0d commands (slot, state): state 1 (or another non-zero code) turns the attack in that
    slot on, 0 or 4 turns it off. Slot 0 is the weapon, 0x0c and up are limbs (kicks). Returns [(slot, on, off)] with
    off None when the script ends with the attack still out (air attacks stay out until landing)."""
    out, open_ = [], {}
    for f, c in evs:
        if c[0] != 0x0d:
            continue
        slot, st = c[1], c[2]
        if st in (0, 4):
            if slot in open_:
                out.append((slot, open_.pop(slot), f))
        elif slot not in open_:
            open_[slot] = f
    out += [(s, f, None) for s, f in open_.items()]
    return sorted(out, key=lambda x: x[1])


def combo_windows(evs):
    """Windows of '9 x' commands: x != 0 opens the combo input window (player+0x27ac = 2, which the input rules'
    opcode 0x28 tests before chaining to the next attack), '9 0' closes it."""
    out, start = [], None
    for f, c in evs:
        if c[0] == 9:
            if c[1] and start is None:
                start = f
            elif not c[1] and start is not None:
                out.append((start, f)); start = None
    if start is not None:
        out.append((start, None))
    return out


# ---------------------------------------------------------------- motions

KEY_WORDS = {0: 2, 1: 2, 2: 3, 3: 4}     # by interpolation type (bits 0-1): types 2 and 3 carry 1 or 2 tangent words
CHANNELS = 44


class Bank:
    """A motion table: 1992 u32 offsets (relative to base); an entry equal to the table's empty value is unused.
    A motion is 44 track offsets (relative to base, the tracks lie before the header). A track is keys:
    word0 bits 0-1 interpolation (0 = last key), bits 2-11 duration in frames, bits 12-15 the value's top 4 bits;
    word1 the value's low 16 bits. Values are signed 20-bit, x 1e-4: metres or radians (decoder at xbe 0x190DE0)."""
    def __init__(self, data, base=0, end=None):
        self.d, self.base, self.end = data, base, end or len(data)
        self.tab = [u32(data, base + 4 * i) for i in range(1992)]
        self.empty = self.tab[0] if self.tab.count(self.tab[0]) > 100 else None

    def has(self, m):
        if not 0 <= m < len(self.tab):
            return False
        t = self.tab[m]
        return t != self.empty and t % 16 == 0 and self.base + t + 0xb0 < self.end

    def tracks(self, m):
        d, a, out = self.d, self.base + self.tab[m], []
        for k in range(CHANNELS):
            p, keys = self.base + u32(d, a + 4 * k), []
            while True:
                w0, w1 = struct.unpack_from('<HH', d, p)
                p += 2 * KEY_WORDS[w0 & 3]
                v = ((w0 >> 12) << 16) | w1
                if v & 0x80000:
                    v -= 0x100000
                keys.append(((w0 >> 2) & 0x3ff, v * 1e-4))
                if (w0 & 3) == 0 or (w0 & 0xfff) == 0:
                    break
            out.append(keys)
        return out

    def length(self, m):
        return max(sum(k[0] for k in t) for t in self.tracks(m))


def sample(track, f):
    """Linear sample of a track at frame f."""
    t = 0
    for i, (dur, v) in enumerate(track):
        if dur == 0 or i == len(track) - 1:
            return v
        if f < t + dur:
            return v + (f - t) / dur * (track[i + 1][1] - v)
        t += dur
    return track[-1][1]


# ---------------------------------------------------------------- skeleton

def kmd_skeleton(data):
    """Bind translations (OBJINFO 'OI' records, +0x30) and parents (HIERARC) of a KMD model."""
    B, H = 0xb0, data.index(b'HIERARC')
    n = u32(data, B + 0x10)
    T = [np.array([f32(data, B + u32(data, B + 0x20 + 4 * i) + 0x30 + 4 * k) for k in range(3)]) for i in range(n)]
    hn = u32(data, H + 0x10)
    parent = [struct.unpack_from('<Hh', data, H + u32(data, H + 0x30 + 4 * i))[1] for i in range(hn)]
    return T, parent


def _rot(axis, a):
    c, s = np.cos(a), np.sin(a)
    return {'x': np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
            'y': np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            'z': np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def euler(a):
    """Channel rotation (x, y, z radians), applied z, y, x."""
    return _rot('z', a[2]) @ _rot('y', a[1]) @ _rot('x', a[0])


def _ik(a, c, l1, l2, pole):
    v = c - a
    dist = min(np.linalg.norm(v), l1 + l2 - 1e-4)
    n = v / max(np.linalg.norm(v), 1e-6)
    x = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = np.sqrt(max(l1 * l1 - x * x, 0))
    p = pole - np.dot(pole, n) * n
    p = p / max(np.linalg.norm(p), 1e-6)
    return a + n * x + p * h, a + n * dist


# Limb blocks of 8 channels: IK end-effector position (3, character space), effector rotation (3), two angles.
# Order from the game's pose builder (xbe 0x18EEE0): right arm (bone 14 chain), left arm (8), right leg (12), left leg (6).
LIMBS = (('rarm', 12, 14), ('larm', 20, 8), ('rleg', 28, 12), ('lleg', 36, 6))
ARM, LEG = 0.26, 0.43            # link lengths of the KMD chains (8-4-5 / 14-10-11, 6-7-3 / 12-13-9)


def pose(T, tracks, f):
    """Joint positions at frame f. Channels 0-2 root translation, 3-5 root rotation, 6-8 spine (bone 0), 9-11 head
    (bone 1), then the four limb blocks, solved here as two-bone IK chains (the elbow/knee angles are not used;
    a pole in front for knees, behind for elbows). Character space: y up, +z forward, x to the left."""
    ch = [sample(t, f) for t in tracks]
    root = np.array(ch[0:3]); Rr = euler(ch[3:6])
    Rs = Rr @ euler(ch[6:9]); spine = root + Rr @ T[0]
    Rh = Rs @ euler(ch[9:12]); head = spine + Rs @ T[1]
    P = {'root': root, 'spine': spine, 'head': head, 'headtop': head + Rh @ np.array([0, 0.24, 0])}
    for name, s, bone in LIMBS:
        arm = name.endswith('arm')
        base = (spine + Rs @ T[bone]) if arm else (root + Rr @ T[bone])
        pole = Rr @ np.array([0, 0, -1.0 if arm else 1.0])
        mid, end = _ik(base, np.array(ch[s:s + 3]), *((ARM, ARM) if arm else (LEG, LEG)), pole)
        P[name] = (base, mid, end)
        P[name + 'Rot'] = euler(ch[s + 3:s + 6])
    return P


def blade(P, length=0.95):
    """The Dragon Sword along the right hand's -x axis (the effector rotation): from the hand to the tip.
    An approximation used by the 2D sheets; the 3D export mounts the sword as katana.itm says (itm_mounts)."""
    hand = P['rarm'][2]
    return hand, hand + P['rarmRot'] @ np.array([-length, 0, 0])


# ---------------------------------------------------------------- skinned pose (3D export)

# The 15 body bones of ryu.kmd (OBJINFO 0-14) and their parents. -x is Ryu's right: katana.itm mounts the sword on 11.
BONES = {2: 'Hips', 0: 'Spine', 1: 'Head', 8: 'L_UpperArm', 4: 'L_Forearm', 5: 'L_Hand', 14: 'R_UpperArm',
         10: 'R_Forearm', 11: 'R_Hand', 6: 'L_Thigh', 7: 'L_Calf', 3: 'L_Foot', 12: 'R_Thigh', 13: 'R_Calf', 9: 'R_Foot'}
# limb block (LIMBS) -> (upper, lower, end bone, side). The game sends each limb's last two channels as a direction,
# (cos a sin b, -sin a, cos a cos b) in character space (built at xbe 0x190217: (0, 0, 1) turned by b about y, then a
# about x): the elbow or knee hinge axis. The joint sits on side * (axis x limb direction) from the shoulder-hand line,
# mirrored between the two sides (the knees come out forward on every frame of the Dragon Sword moves this way).
CHAINS = {'rarm': (14, 10, 11, -1), 'larm': (8, 4, 5, 1), 'rleg': (12, 13, 9, -1), 'lleg': (6, 7, 3, 1)}
REST_HINGE = {'rarm': (0, 1, 0), 'larm': (0, 1, 0), 'rleg': (1, 0, 0), 'lleg': (-1, 0, 0)}


def _frame(a, h):
    """Rotation whose columns are a, the part of h normal to a, and their cross product."""
    a = a / np.linalg.norm(a)
    h = h - np.dot(h, a) * a
    n = np.linalg.norm(h)
    if n < 1e-6:
        h = np.cross(a, [0, 0, 1.0] if abs(a[2]) < 0.9 else [1.0, 0, 0]); n = np.linalg.norm(h)
    h = h / n
    return np.stack([a, h, np.cross(a, h)], 1)


def bone_pose(T, tracks, f):
    """World rotation and position (character space, metres) of the 15 body bones at frame f, from the motion's
    channels: root, spine and head rotations as they are, each limb solved from its end-effector position, its hinge
    axis and the KMD's bone lengths, the hand or foot turned by the effector rotation."""
    ch = [sample(t, f) for t in tracks]
    R, P = {}, {}
    R[2] = euler(ch[3:6]); P[2] = np.array(ch[0:3])
    R[0] = R[2] @ euler(ch[6:9]); P[0] = P[2] + R[2] @ T[0]
    R[1] = R[0] @ euler(ch[9:12]); P[1] = P[0] + R[0] @ T[1]
    for name, s, _ in LIMBS:
        up, lo, end, side = CHAINS[name]
        par = 0 if name.endswith('arm') else 2
        base = P[par] + R[par] @ T[up]
        l1, l2 = np.linalg.norm(T[lo]), np.linalg.norm(T[end])
        a, b = ch[s + 6], ch[s + 7]
        hinge = np.array([np.cos(a) * np.sin(b), -np.sin(a), np.cos(a) * np.cos(b)])
        v = np.array(ch[s:s + 3]) - base
        dist = min(max(np.linalg.norm(v), 1e-4), l1 + l2 - 1e-4)
        ax = v / max(np.linalg.norm(v), 1e-6)
        j = side * np.cross(hinge, ax)
        j -= np.dot(j, ax) * ax
        j = j / max(np.linalg.norm(j), 1e-6)
        x = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
        mid = base + ax * x + j * np.sqrt(max(l1 * l1 - x * x, 0))
        tip = base + ax * dist
        rest = _frame(T[lo], np.array(REST_HINGE[name], float))
        R[up] = _frame(mid - base, hinge) @ rest.T; P[up] = base
        R[lo] = _frame(tip - mid, hinge) @ rest.T; P[lo] = mid
        R[end] = euler(ch[s + 3:s + 6]); P[end] = tip
    return R, P


# ---------------------------------------------------------------- KMD meshes and textures

class KMD:
    """A KMD model: OBJINFO (one record per object: kind, flags, bind translation), HIERARC (each object's parent or,
    for parts, the bone it rides on) and an XPR0 block of Xbox D3D resources. In the XPR0 header after its counts,
    one mesh header per object: 0x80000000, size, 1, subsets, FVF, ?, ?, vertex count, stride, 1, 0, index count;
    each subset: (index, 0, textures, 0), (primitive, first byte, byte count, 1) into the object's indices,
    a material block when +0x20 is set, then per texture (name, texture index) and its stage states.
    Then the D3D resource headers: textures (0x00040001: data, lock, format, size), vertex buffers (0x00800001),
    index buffers (0x00010001) and push buffers (0x00020001), data offsets from the end of the XPR0 header.
    FVF 0x112 is position, normal, uv; 0x116 adds one blend weight (the object's bone and its parent: weight is the
    parent's); 0x42 is position and colour (shadow parts, not drawn here)."""

    def __init__(self, d):
        self.d = d
        X = d.index(b'XPR0'); data0 = X + u32(d, X + 8)
        x = X + 0x30
        self.meshes = []
        while u32(d, x) == 0x80000000 and u32(d, x + 8) == 1:
            m = {'fvf': u32(d, x + 16), 'nv': u32(d, x + 28), 'stride': u32(d, x + 32), 'ni': u32(d, x + 44), 'subs': []}
            y = x + 0x30
            for _ in range(u32(d, x + 12)):
                ntex, t0 = u32(d, y + 8), y + (0xb0 if u32(d, y + 0x20) else 0x60)
                m['subs'].append({'prim': u32(d, y + 0x10), 'start': u32(d, y + 0x14) // 2, 'count': u32(d, y + 0x18) // 2,
                                  'tex': [struct.unpack_from('<i', d, t0 + 4 + 0x40 * t)[0] for t in range(ntex)],
                                  'names': [d[t0 + 0x40 * t:t0 + 0x40 * t + 4].split(b'\0')[0].decode('latin-1') for t in range(ntex)]})
                y = t0 + 0x40 * ntex
            self.meshes.append(m)
            x = y
        while not (u32(d, x) == 0x00040001 and u32(d, x + 12) & 0xff == 0x29):
            x += 4
        self.tex, vb, ib, pb = [], [], [], []
        while u32(d, x) != 0xffffffff:
            c = u32(d, x)
            if c == 0x00040001: self.tex.append((data0 + u32(d, x + 4), u32(d, x + 12))); x += 20
            elif c == 0x00800001: vb.append(data0 + u32(d, x + 4)); x += 12
            elif c == 0x00010001: ib.append(data0 + u32(d, x + 4)); x += 12
            elif c == 0x00020001: pb.append(data0 + u32(d, x + 4)); x += 24
            else: raise ValueError('unknown XPR resource at 0x%x' % x)
        assert len(vb) == len(ib) == len(self.meshes)
        pbs = iter(pb)
        for m, v, i in zip(self.meshes, vb, ib):
            raw = np.frombuffer(d, np.uint8, m['nv'] * m['stride'], v).reshape(m['nv'], m['stride'])
            fl = lambda a, b: raw[:, a:b].copy().view('<f4')
            m['pos'] = fl(0, 12)
            if m['fvf'] in (0x112, 0x116):
                k = 16 if m['fvf'] == 0x116 else 12
                m['w'] = fl(12, 16)[:, 0] if m['fvf'] == 0x116 else None
                m['nrm'], m['uv'] = fl(k, k + 12), fl(k + 12, k + 20)
            idx = np.frombuffer(d, '<u2', m['ni'], i)
            for s in m['subs']:
                # primitive 2: a strip in the index buffer; 0: a strip in the next push buffer
                s['strip'] = idx[s['start']:s['start'] + s['count']] if s['prim'] == 2 else (
                    _pushbuffer_strip(d, next(pbs)) if s['prim'] == 0 else np.zeros(0, np.uint16))
        B = d.index(b'OBJINFO')
        self.obj = []
        for k in range(u32(d, B + 0x10)):
            o = B + u32(d, B + 0x20 + 4 * k)
            self.obj.append({'kind': u32(d, o + 0xc), 'flags': u32(d, o + 0x10),
                             'T': np.array(struct.unpack_from('<3f', d, o + 0x30))})
        H = d.index(b'HIERARC')
        self.parent = [struct.unpack_from('<Hh', d, H + u32(d, H + 0x30 + 4 * k))[1] for k in range(u32(d, H + 0x10))]

    def texture(self, k):
        """RGBA image of texture k (DXT1 or DXT4/5; Xbox compressed textures are not swizzled)."""
        import io
        from PIL import Image
        off, f = self.tex[k]
        fmt, w, h = (f >> 8) & 0xff, 1 << ((f >> 20) & 0xf), 1 << ((f >> 24) & 0xf)
        size = max(1, w // 4) * max(1, h // 4) * (8 if fmt == 0x0c else 16)
        four = {0x0c: b'DXT1', 0x0e: b'DXT3'}.get(fmt, b'DXT5')
        dds = struct.pack('<4sI6I44x8I5I', b'DDS ', 124, 0x81007, h, w, size, 0, 1,
                          32, 4, int.from_bytes(four, 'little'), 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
        return Image.open(io.BytesIO(dds + self.d[off:off + size])).convert('RGBA')


def _pushbuffer_strip(d, o):
    """Indices of an NV2A push buffer: SET_BEGIN_END (0x17fc) then ARRAY_ELEMENT16 (0x1800, two per word)."""
    out = []
    while True:
        h = u32(d, o); o += 4
        method, n = h & 0x1ffc, (h >> 18) & 0x7ff
        if method == 0x17fc:
            if u32(d, o) == 0: break
        elif method == 0x1800:
            w = np.frombuffer(d, '<u2', 2 * n, o); out.append(w)
        elif method == 0x1808:
            out.append(np.frombuffer(d, '<u4', n, o).astype(np.uint16))
        o += 4 * n
    return np.concatenate(out) if out else np.zeros(0, np.uint16)


def strip_triangles(ix):
    """Triangles of a strip with degenerate joins."""
    out = []
    for k in range(len(ix) - 2):
        a, b, c = int(ix[k]), int(ix[k + 1]), int(ix[k + 2])
        if a != b and b != c and a != c:
            out.append((a, b, c) if k % 2 == 0 else (b, a, c))
    return np.array(out, np.int64).reshape(-1, 3)


def itm_shapes(d):
    """Attack shapes of an itm_dat2 file: 0x91000001 sphere (bone, centre, radius), 0x91000002 capsule (bone, two
    points, two radii), in the item's own space."""
    out, o = [], 0
    while True:
        o = d.find(b'\x02\x00\x00\x91', o)
        if o < 0: return out
        bone = u32(d, o + 4)
        v = struct.unpack_from('<8f', d, o + 8)
        out.append({'bone': bone, 'a': v[0:3], 'b': v[3:6], 'r': v[6]})
        o += 4


def itm_mounts(d):
    """Where an item sits on the body, from the table after the shapes in itm_dat2 (katana.itm): records of
    (id, bone, x, y, z, rx, ry, rz) with the angles in degrees. For the Dragon Sword, id 2 is the right hand's grip
    (bone 11), id 1 the sheath on the back (bone 0), 4 the reverse grip, 5 and 6 the left hand."""
    out = {}
    s = u32(d, 0x24)                       # section 1; its records start after a 0x40-byte header
    o = s + u32(d, s)
    while o + 32 <= len(d) and 0 < u32(d, o) < 64 and u32(d, o + 4) < 64:
        v = struct.unpack_from('<6f', d, o + 8)
        out.setdefault(u32(d, o), {'bone': u32(d, o + 4), 'pos': v[0:3], 'rot': v[3:6]})
        o += 32
    return out

"""Ninja Gaiden Black (Xbox, 2005) file formats, read-only. Used by import_ngb_game.py.

Everything here was worked out from the bytes and checked against the game's own code (default.xbe, disassembled
with the ngbrecomp toolkit); see frame-data/scouting-ninja-gaiden-black.md for the notes.

  AFS        CRI archive: "AFS\\0", count, (offset, size) pairs, then a name table of 48-byte records.
  chr_dat    container of .mtn (motions + timeline scripts) and .chr (collision, state table, input rules):
             magic(8), 0, size, n, n, 0x20, 0x20, then n section offsets.
  .mot       a weapon's motion bank (rm_kt.mot = Dragon Sword): a motion table of 1992 u32 and the motions.
  .kmd       the model; only the OBJINFO bind translations and the HIERARC parents are read.
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
    An approximation: the sword's own mount (katana.itm, KMD weapon nodes) is not read."""
    hand = P['rarm'][2]
    return hand, hand + P['rarmRot'] @ np.array([-length, 0, 0])

"""Devil May Cry 3 (PS2, Special Edition) file readers: the AFS disc archives, PAC/PNST containers, MOD models with
their skeletons, MOT motions and TIM2 textures. Nothing here writes to the game folder.

Formats, as read from the European Special Edition (SLES-54186):

AFS (GData.afs): 'AFS\\0', u32 count, count x (u32 offset, u32 size), then (offset, size) of a name table of 48-byte
entries (32-byte name). `Game` reads files straight out of it, or out of a folder the archive was unpacked to.

PAC / PNST: a 4-byte tag, u32 count, count x u32 offsets (0 = empty slot); a slot runs to the next non-zero offset.
pl000.pac (Dante) holds his textures (slot 0), body MOD (1), the BASE / DAMAGE / TAUNTS motion packs (2-4), his
motion scripts (5, see below), a coat MOD (12) and the coat's cloth settings as text (13). pl000_00_<group>.pac is one motion pack per group (Rebellion is
group 3, see MOTION_GROUPS), each slot a MOT. plwp_<name>.pac (PNST) holds a weapon's MOD in slot 1.

MOD: 'MOD ', header to 0x30 (0x10 u8 object count, 0x1c u32 skeleton offset). Then per object 0x30 bytes: u16 tag
(0x8000 | sub-mesh count), u16 vertex count, u32 offset of its first sub-mesh header, ..., bounding sphere at +0x20.
A sub-mesh header (0x30 bytes, consecutive per object): u16 count, u16 texture slot, u32 x7 offsets of positions
(f32 x3), normals (f32 x3), UVs (i16 x2 / 4096), skin (u8 x4: 0, then three bone indices x4) and strip flags (u16 per
vertex: three 5-bit weights out of 31, bit 15 = no triangle ends here). Vertices are in model space on a skeleton
whose rest pose has no rotation. Triangles are strips: vertex i closes (i-2, i-1, i) unless flagged.
Skeleton (at the 0x1c offset): u32 offsets of the parent list, slot order, flags and transforms, u32 bone count; slot
j is bone order[j] with parent parents[j] (0xff = root); each bone's 0x20-byte transform starts with its offset.

MOT: u32 header size, 'MOT\\0', f32 start and end frames at 0x08 / 0x0c (60 fps; the move plays from start to end:
a combo part's motion carries the parts before it, which the game skips), u16 bone count at 0x1c and
one u16 channel mask per bone from 0x1e (bits 0-2 scale, 3-5 rotation XYZ in radians, 6-8 translation). Then u32
record count and one record per set mask bit, bone by bone: u16 size, u16 key count, u16 kind, u16 flags. Kind 3
(Hermite): three (base, range) f32 pairs for value, in-tangent and out-tangent, then keys of u16 frame + 0x8000,
value, in, out, each quantised as base + range * q / 65535, slopes per frame. Kind 2 (linear): one pair,
then keys of u16 frame + 0x8000 and value.

Motion scripts (pl000.pac slot 5): the game's code never names a motion file. An action plays a script by (group,
index), and the script picks the motion and times what happens during it. The slot holds two tables, each u16 0x0004,
u16 0xffff, then 34 u16 group offsets from the table's base (the byte after those four), each group a list of u16
offsets from the group's own start, one per index: scripts at 0x0a, and motion files at the u16 at 0x02 (+4). A
motion file entry is u8 count, u8, then count x 6 bytes (u8 body half, u8, u8, u8, u16 file id: file id / 100 is the
motion pack pl000_00_<n>, file id % 100 its slot; both halves name the same file for Dante). A script is bytecode:
  00 _ u16 frame u8 _       wait until the motion reaches frame (0x7fff: for good)
  01 a b c group index u16  play the motion of (group, index) from u16 (0x7fff: the motion's own start frame)
  02 _ s16                  jump back
  03 / 04 b0..b4            set the 5-byte state block 0 / 1 (03 at 0x5d, 04 at 0x62 of the motion controller); block
                            0's b4 is a signal to the action's code for that frame (a gun fires on it, for one)
  05 _                      clear both blocks
  06 n                      pick damage entry n of the action's attack table and start a new hit (targets already
                            struck can be struck again); 07 n picks only, 08 _ starts a new hit only
  10+k h u16 d u16 x (k+1)  switch on k+1 colliders (pl000.pac slot 6 ids) for d frames (0xffff: until switched off);
                            h is the body half whose controller runs it (both halves run the script)
  20 h m _                  switch off the colliders whose type has a bit of m;   24 h s16 id: switch off collider id
  21 _ / 22 _ u32 / 23 _    collision manager settings
Block 1's bytes set the next-action policy of an input slot: high nibble 3 = buffer, 1 = execute, 2 = ignore; low
nibble the slot (0 melee, 4 style action, 5 jump / roll, 6 Royalguard, 8 Trickster, 10 gun, 15 the action ends).
Colliders (pl000.pac slot 6): u32 per id, u8 type (bit 0: it deals damage; ids 0-1 are the body Dante is hit on),
u8 bone, u16 shape (slot 7). Slot 7: 0x50 bytes per shape, u32 kind (2 = sphere: f32 x4 centre in the bone's space at
+0x10, centimetres, then f32 radius at +0x20; 3 and 4 are boxes and planes, used by a few style moves).
Script frames are the motion's own frames (from 0, not from its start frame). One script runs on into the next
index's script when the action chains, so a script ends at its next 01.
"""
import math, os, struct
import numpy as np

# Motion groups of Dante (pl000_00_<group>.pac), from DDMK's MOTION_GROUP_DANTE
MOTION_GROUPS = ['BASE', 'DAMAGE', 'TAUNTS', 'REBELLION', 'CERBERUS', 'AGNI_RUDRA', 'NEVAN', 'BEOWULF', 'EBONY_IVORY',
                 'SHOTGUN', 'ARTEMIS', 'SPIRAL', 'KALINA_ANN', 'SWORDMASTER_REBELLION', 'SWORDMASTER_CERBERUS',
                 'SWORDMASTER_AGNI_RUDRA', 'SWORDMASTER_NEVAN', 'SWORDMASTER_BEOWULF', 'GUNSLINGER_EBONY_IVORY',
                 'GUNSLINGER_SHOTGUN', 'GUNSLINGER_ARTEMIS', 'GUNSLINGER_SPIRAL', 'GUNSLINGER_KALINA_ANN', 'TRICKSTER',
                 'ROYALGUARD', 'QUICKSILVER', 'DOPPELGANGER']


class Game:
    """Files by name from GData.afs in the game folder, or from a folder holding the unpacked files."""
    def __init__(self, path):
        self.path = path
        afs = os.path.join(path, 'GData.afs')
        self.index = None
        if os.path.exists(afs):
            self.afs = open(afs, 'rb')
            n = struct.unpack('<4sI', self.afs.read(8))[1]
            ents = [struct.unpack('<II', self.afs.read(8)) for _ in range(n)]
            first = min(o for o, s in ents if s)
            names = None
            for pos in (8 + 8 * n, first - 8):
                self.afs.seek(pos)
                no, ns = struct.unpack('<II', self.afs.read(8))
                if no and ns >= 48 * n:
                    self.afs.seek(no); t = self.afs.read(48 * n)
                    names = [t[48 * i:48 * i + 32].split(b'\0')[0].decode('latin1') for i in range(n)]
                    break
            self.index = {nm: e for nm, e in zip(names, ents)}
        elif os.path.isdir(os.path.join(path, 'GData')):
            self.path = os.path.join(path, 'GData')

    def read(self, name):
        if self.index is not None:
            o, s = self.index[name]
            self.afs.seek(o)
            return self.afs.read(s)
        with open(os.path.join(self.path, name), 'rb') as f:
            return f.read()


def subfiles(b):
    """PAC / PNST slots (None for empty ones)."""
    n = struct.unpack_from('<I', b, 4)[0]
    offs = struct.unpack_from('<%dI' % n, b, 8)
    valid = sorted(set(o for o in offs if o))
    out = []
    for o in offs:
        if not o:
            out.append(None); continue
        i = valid.index(o)
        out.append(b[o:valid[i + 1] if i + 1 < len(valid) else len(b)])
    return out


# --- models --------------------------------------------------------------------------------------------------------

def skeleton(m):
    """(parents, offsets) of a MOD's skeleton, by bone index."""
    base = struct.unpack_from('<I', m, 0x1c)[0]
    o_par, o_ord, _, o_xf = struct.unpack_from('<4I', m, base)
    nb = struct.unpack_from('<I', m, base + 0x10)[0]
    par, order = m[base + o_par: base + o_par + nb], m[base + o_ord: base + o_ord + nb]
    parents = [-1] * nb
    for j in range(nb):
        parents[order[j]] = -1 if par[j] == 0xff else par[j]
    offsets = np.array([struct.unpack_from('<3f', m, base + o_xf + 0x20 * i) for i in range(nb)])
    return parents, offsets


def meshes(m):
    """Every sub-mesh of a MOD: dict(obj, tex, pos, nrm, uv, joints[n,3], weights[n,3], tris[k,3])."""
    out = []
    for i in range(m[0x10]):
        tag, _, off = struct.unpack_from('<HHI', m, 0x30 + 0x30 * i)
        for j in range(tag & 0xff):
            h = off + 0x30 * j
            n, tex = struct.unpack_from('<HH', m, h)
            offs = struct.unpack_from('<7I', m, h + 4)
            pos = np.frombuffer(m, '<f4', n * 3, offs[2]).reshape(n, 3)
            nrm = np.frombuffer(m, '<f4', n * 3, offs[3]).reshape(n, 3)
            uv = np.frombuffer(m, '<i2', n * 2, offs[4]).reshape(n, 2) / 4096.0
            sk = np.frombuffer(m, 'u1', n * 4, offs[5]).reshape(n, 4)
            fl = np.frombuffer(m, '<u2', n, offs[6])
            joints = (sk[:, 1:4] // 4).astype(np.int32)
            w = np.stack([fl & 31, (fl >> 5) & 31, (fl >> 10) & 31], 1).astype(np.float32) / 31
            tris = [(i - 2, i - 1, i) if i % 2 == 0 else (i - 1, i - 2, i)
                    for i in range(2, n) if not fl[i] & 0x8000]
            out.append(dict(obj=i, tex=tex, pos=pos, nrm=nrm, uv=uv, joints=joints, weights=w,
                            tris=np.array(tris, np.int32).reshape(-1, 3)))
    return out


# --- motions -------------------------------------------------------------------------------------------------------

def motion(s):
    """dict(start, frames, masks, tracks {(bone, channel): [(frame, value, in, out)]}) of a MOT; frames is the end
    frame; channels as in the module doc."""
    hsz = struct.unpack_from('<I', s, 0)[0]
    start, frames = struct.unpack_from('<2f', s, 0x08)
    nb = struct.unpack_from('<H', s, 0x1c)[0]
    masks = struct.unpack_from('<%dH' % nb, s, 0x1e)
    p = hsz + 4
    tracks = {}
    for b, mk in enumerate(masks):
        for c in range(9):
            if not mk >> c & 1:
                continue
            size, nk, kind, _ = struct.unpack_from('<4H', s, p)
            keys = []
            if kind == 2:       # linear: one (base, range) pair, keys of u16 frame + u16 value
                base, rng = struct.unpack_from('<2f', s, p + 8)
                for i in range(nk):
                    f, q = struct.unpack_from('<2H', s, p + 16 + 4 * i)
                    keys.append((f - 0x8000, base + rng * q / 65535, None, None))
            else:
                pre = [struct.unpack_from('<2f', s, p + 8 + 8 * i) for i in range(3)]
                for i in range(nk):
                    q = struct.unpack_from('<4H', s, p + 32 + 8 * i)
                    keys.append((q[0] - 0x8000,) + tuple(pre[j][0] + pre[j][1] * q[j + 1] / 65535 for j in range(3)))
            tracks[(b, c)] = keys
            p += size
    return dict(start=start, frames=frames, masks=masks, tracks=tracks)


def sample(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (f0, v0, _, o0), (f1, v1, i1, _) in zip(keys, keys[1:]):
        if t <= f1:
            d = f1 - f0
            if d <= 0:
                return v1
            u = (t - f0) / d
            if o0 is None or i1 is None:
                return v0 + (v1 - v0) * u
            return ((2 * u ** 3 - 3 * u ** 2 + 1) * v0 + (u ** 3 - 2 * u ** 2 + u) * d * o0
                    + (-2 * u ** 3 + 3 * u ** 2) * v1 + (u ** 3 - u ** 2) * d * i1)
    return keys[-1][1]


def euler_xyz(rx, ry, rz):
    """Rotation matrix applying X, then Y, then Z."""
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    X = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Z @ Y @ X


def local_pose(offsets, mot, t):
    """Per bone (rotation 3x3, translation) at frame t; untracked channels keep the rest offset and no rotation."""
    out = []
    tr = mot['tracks']
    for b, off in enumerate(offsets):
        rot, pos, scl = [0.0, 0.0, 0.0], list(off), [1.0, 1.0, 1.0]
        for c in range(9):
            k = tr.get((b, c))
            if k is None:
                continue
            v = sample(k, t)
            if c < 3: scl[c] = v
            elif c < 6: rot[c - 3] = v
            else: pos[c - 6] = v
        out.append((euler_xyz(*rot) @ np.diag(scl), np.array(pos)))
    return out


def world(parents, local):
    W = []
    for b, (R, T) in enumerate(local):
        L = np.eye(4); L[:3, :3] = R; L[:3, 3] = T
        W.append(L if parents[b] < 0 else W[parents[b]] @ L)
    return W


# --- textures ------------------------------------------------------------------------------------------------------

def textures(s):
    """RGBA arrays of every TIM2 picture in a texture slot, in order (8 and 4 bit indexed)."""
    out = []
    i = s.find(b'TIM2')
    while i >= 0:
        cnt = struct.unpack_from('<H', s, i + 6)[0]
        p = i + (0x80 if s[i + 5] == 1 else 0x10)
        for _ in range(cnt):
            tot, pal, imsz, hs, _, _, _, ctype, itype = struct.unpack_from('<IIIHHBBBB', s, p)
            w, h = struct.unpack_from('<HH', s, p + 0x14)
            px = np.frombuffer(s, 'u1', imsz, p + hs)
            clut = np.frombuffer(s, 'u1', pal, p + hs + imsz).reshape(-1, 4).copy()
            if itype == 5:
                if not ctype & 0x80:       # CSM1: swap the 2nd and 3rd group of 8 in every 32 colours
                    for k in range(0, len(clut), 32):
                        clut[k + 8:k + 16], clut[k + 16:k + 24] = clut[k + 16:k + 24].copy(), clut[k + 8:k + 16].copy()
                idx = px.reshape(h, w)
            else:
                idx = np.stack([px & 15, px >> 4], 1).reshape(h, w)
            rgba = clut[idx].copy()
            rgba[..., 3] = np.minimum(255, rgba[..., 3].astype(np.int32) * 2)   # PS2 alpha: 0x80 = opaque
            out.append(rgba)
            p += tot
        i = s.find(b'TIM2', i + 4)
    return out


# --- motion scripts ------------------------------------------------------------------------------------------------

def colliders(pac):
    """Dante's colliders from pl000.pac's subfiles: [dict(type, bone, sphere=(x, y, z, r) in cm or None)] by id."""
    s6, s7 = pac[6], pac[7]
    out = []
    for i in range(len(s6) // 4):
        t, bone, shape = struct.unpack_from('<BBH', s6, 4 * i)
        o = shape * 0x50
        sphere = None
        if o + 0x50 <= len(s7) and struct.unpack_from('<I', s7, o)[0] == 2:
            x, y, z, _, r = struct.unpack_from('<5f', s7, o + 0x10)
            sphere = (x, y, z, r)
        out.append({'type': t, 'bone': bone, 'sphere': sphere})
    return out


SLOT_NAMES = {0: 'melee', 4: 'style', 5: 'jump', 6: 'royalguard', 8: 'trickster', 10: 'gun', 15: 'end'}
_OPLEN = {0: 6, 1: 8, 2: 4, 3: 6, 4: 6, 5: 2, 6: 2, 7: 2, 8: 2, 0x20: 4, 0x21: 2, 0x22: 6, 0x23: 2, 0x24: 4}


class Scripts:
    """Dante's motion scripts (pl000.pac slot 5): which motion a (group, index) plays and when its cancels and hits come."""
    def __init__(self, s):
        self.s = s
        u16 = lambda o: struct.unpack_from('<H', s, o)[0]
        self.u16 = u16
        self.base = (10, u16(2) + 4)
        self.groups = [[u16(b + 2 * g) for g in range(34)] for b in self.base]

    def _entry(self, table, group, index):
        b = self.base[table] + self.groups[table][group]
        return b + self.u16(b + 2 * index)

    def file(self, group, index):
        """(motion pack, slot) the motion (group, index) of a script's 01 loads."""
        o = self._entry(1, group, index)
        fid = self.u16(o + 6)
        return fid // 100, fid % 100

    def run(self, group, index):
        """One script: dict(motion=(pack, slot), start=frame or None, slots={slot: [(frame, 'buffer'|'go'|'off')]},
        hits=[(frame, 'wave', entry) | (frame, 'on', frames or None, [ids]) | (frame, 'off', ('mask'|'id', n))],
        signals=[(frame, n)] the frames block 0's last byte is set, which the action's code acts on), up to where it hands
        over to the next motion."""
        s, o = self.s, self._entry(0, group, index)
        out = {'motion': None, 'start': None, 'slots': {}, 'hits': [], 'signals': []}
        frame = 0
        for _ in range(1000):
            op = s[o]
            n = 4 + 2 * (op - 0xf) if 0x10 <= op <= 0x1f else _OPLEN[op]
            if op == 1:
                if out['motion']: break
                out['motion'] = self.file(s[o + 4], s[o + 5])
                st = self.u16(o + 6)
                out['start'] = None if st == 0x7fff else st
            elif op == 0:
                frame = self.u16(o + 2)
                if frame == 0x7fff: break
            elif op == 2:
                break
            elif op == 3 and s[o + 5]:
                out['signals'].append((frame, s[o + 5]))
            elif op == 4:
                for b in s[o + 1:o + 6]:
                    st = {0x30: 'buffer', 0x10: 'go', 0x20: 'off'}.get(b & 0xf0)
                    if st: out['slots'].setdefault(b & 0xf, []).append((frame, st))
            elif op in (6, 8):
                out['hits'].append((frame, 'wave', s[o + 1] if op == 6 else None))
            elif 0x10 <= op <= 0x1f:
                d = self.u16(o + 2)
                ids = [self.u16(o + 4 + 2 * k) for k in range(op - 0xf)]
                out['hits'].append((frame, 'on', None if d == 0xffff else d, sorted(set(ids))))
            elif op == 0x20:
                out['hits'].append((frame, 'off', ('mask', s[o + 2])))
            elif op == 0x24:
                out['hits'].append((frame, 'off', ('id', struct.unpack_from('<h', s, o + 2)[0])))
            o += n
        return out


class WeaponScripts(Scripts):
    """A weapon's own motion scripts, which Cerberus has (plwp_nunchaku.pac slot 5): the same bytecode, one list of u16
    offsets from 0x0a with a script per index; its 01 plays the weapon's own motion (group, index), here returned as is.
    Its colliders are ids of Dante's list (81-98 sit on the chain's bones)."""
    def __init__(self, s):
        self.s = s
        self.u16 = lambda o: struct.unpack_from('<H', s, o)[0]

    def _entry(self, table, group, index):
        return 10 + self.u16(10 + 2 * index)

    def file(self, group, index):
        return group, index

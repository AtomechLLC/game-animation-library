"""Exports what the Frame Data tab's 3D preview needs from Devil May Cry 3: Special Edition (PS2): Dante's model and
coat, his weapons and every move's motion, baked per frame. Same layout and animation format as export_er_models.py,
so frame-data/viewer3d.js plays it.

    python tools/frame_data/export_dmc3_models.py "<game folder with GData.afs>"      # or a folder of unpacked files

Reads only (dmc3_files.py); writes frame-data/models/devil-may-cry-3/:

    models.json         skeleton (bone names), the body, every weapon, per class its preview weapon and moves file
    dante.glb           Dante's body (pl000.pac slot 1) skinned to his 24-bone skeleton, plus his coat (slot 12). The game
                        moves the coat by cloth simulation, which isn't reproduced: it's skinned to the hips and legs
                        instead (coat_skin). Textures from slot 0. PS2 space (left-handed, centimetres) scaled to metres.
    weapon-<name>.glb   the weapon's MOD (plwp_*.pac slot 1), origin at the grip, attached to the right hand bone
                        as it is (Ebony & Ivory, Agni & Rudra: node R and node L)
    anim/<move>.bin     the move's motions (dmc3_moves.segments) played in a row, sampled at 60 fps ('FDA2', see
                        export_er_models.py); bone 0's translation is the root motion track
    moves/<class>.json  per move id its frames, preview weapon, animation file and hits (dmc3_moves.hits: each damaging
                        collider's frames, its id as `judge`), and the hit spheres (`attacks`, one variation 0 that every
                        weapon uses); models.json `body` places each collider id's sphere centre on its bone
"""
import io, json, math, os, struct, sys
import numpy as np
from PIL import Image
import dmc3_files as D
import dmc3_moves as M

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'frame-data', 'models', 'devil-may-cry-3')
FPS = 60
SCALE = 0.01            # centimetres -> metres

BONES = ['Root', 'Hips', 'UpperBody', 'Spine', 'Chest', 'Head', 'L_Clavicle', 'L_UpperArm', 'L_Forearm', 'L_Hand',
         'R_Clavicle', 'R_UpperArm', 'R_Forearm', 'R_Hand', 'LowerBody', 'L_Thigh', 'L_Calf', 'L_Foot', 'L_Toe',
         'R_Thigh', 'R_Calf', 'R_Foot', 'R_Toe', 'Hair']
COAT_PARENT = 1
LOWER_BODY = 14
COAT_FOLLOW = [1, 14, 15, 16, 17, 19, 20, 21]   # hips and legs


# glTF writer and quaternion packing as in export_er_models.py (copied: that module needs Python 3.14 for
# Elden Ring's zstd archives, this one doesn't)
QS = 1023 / math.sqrt(2)
OTHER = np.array([[j for j in range(4) if j != k] for k in range(4)])

class Gltf:
    def __init__(self):
        self.j = {'asset': {'version': '2.0', 'generator': 'export_dmc3_models.py'}, 'scene': 0, 'scenes': [{'nodes': []}],
                  'nodes': [], 'meshes': [], 'materials': [], 'accessors': [], 'bufferViews': [], 'buffers': [],
                  'images': [], 'textures': [], 'samplers': [{'magFilter': 9729, 'minFilter': 9987}]}
        self.bin = bytearray()

    def view(self, data, target=None, stride=None):
        while len(self.bin) % 4: self.bin.append(0)
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target: v['target'] = target
        if stride: v['byteStride'] = stride
        self.bin += data
        self.j['bufferViews'].append(v)
        return len(self.j['bufferViews']) - 1

    def accessor(self, arr, ctype, kind, target=None, normalized=False, minmax=False):
        arr = np.ascontiguousarray(arr)
        data, stride = arr.tobytes(), None
        if target == 34962 and arr.ndim == 2 and arr.itemsize * arr.shape[1] % 4:
            # vertex attributes need a 4-byte stride: pad each element (int8 / int16 VEC3)
            stride = (arr.itemsize * arr.shape[1] + 3) // 4 * 4
            pad = np.zeros((len(arr), stride), np.uint8); pad[:, :arr.itemsize * arr.shape[1]] = arr.view(np.uint8).reshape(len(arr), -1)
            data = pad.tobytes()
        a = {'bufferView': self.view(data, target, stride), 'componentType': ctype, 'count': len(arr), 'type': kind}
        if normalized: a['normalized'] = True
        if minmax:
            a['min'] = [float(v) for v in arr.min(axis=0)]; a['max'] = [float(v) for v in arr.max(axis=0)]
        self.j['accessors'].append(a)
        return len(self.j['accessors']) - 1

    def image(self, png_or_jpg, mime):
        self.j['images'].append({'bufferView': self.view(png_or_jpg), 'mimeType': mime})
        self.j['textures'].append({'sampler': 0, 'source': len(self.j['images']) - 1})
        return len(self.j['textures']) - 1

    def node(self, **kw):
        self.j['nodes'].append({k: v for k, v in kw.items() if v is not None})
        return len(self.j['nodes']) - 1

    def glb(self):
        while len(self.bin) % 4: self.bin.append(0)
        self.j['buffers'] = [{'byteLength': len(self.bin)}]
        j = {k: v for k, v in self.j.items() if v != []}
        js = json.dumps(j, separators=(',', ':')).encode()
        js += b' ' * (-len(js) % 4)
        return (struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(self.bin)) +
                struct.pack('<I4s', len(js), b'JSON') + js + struct.pack('<I4s', len(self.bin), b'BIN\0') + bytes(self.bin))


def pack_quats(q):
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    i = np.argmax(np.abs(q), axis=-1)
    q = q * np.where(np.take_along_axis(q, i[:, None], -1) < 0, -1, 1)
    c = np.take_along_axis(q, OTHER[i], -1)
    v = np.clip(np.round((c + 1 / math.sqrt(2)) * QS), 0, 1023).astype(np.uint32)
    return (i.astype(np.uint32) << 30) | (v[:, 0] << 20) | (v[:, 1] << 10) | v[:, 2]


def encode(rgba, size=256):
    im = Image.fromarray(rgba, 'RGBA')
    if max(im.size) > size:
        f = size / max(im.size)
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)
    alpha = im.getchannel('A').getextrema()[0] < 250
    buf = io.BytesIO()
    if alpha: im.save(buf, 'PNG', optimize=True); mime = 'image/png'
    else: im.convert('RGB').save(buf, 'JPEG', quality=85, optimize=True); mime = 'image/jpeg'
    return buf.getvalue(), mime, alpha


def add_meshes(g, subs, texs, joint_map, name, skinned=True):
    """MOD sub-meshes -> one glTF mesh, a primitive per sub-mesh; joint_map maps MOD bone -> skin joint."""
    mats = {}
    prims = []
    for s in subs:
        if not len(s['tris']): continue
        t = s['tex'] if s['tex'] < len(texs) else 0
        if t not in mats:
            mat = {'name': '%s-%d' % (name, t), 'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 0.85},
                   'doubleSided': True}
            if texs:
                data, mime, alpha = encode(texs[t])
                mat['pbrMetallicRoughness']['baseColorTexture'] = {'index': g.image(data, mime)}
                if alpha: mat.update(alphaMode='MASK', alphaCutoff=0.5)
            g.j['materials'].append(mat); mats[t] = len(g.j['materials']) - 1
        attrs = {'POSITION': g.accessor((s['pos'] * SCALE).astype(np.float32), 5126, 'VEC3', 34962, minmax=True)}
        n = s['nrm'] / np.maximum(np.linalg.norm(s['nrm'], axis=1, keepdims=True), 1e-6)
        attrs['NORMAL'] = g.accessor(n.astype(np.float32), 5126, 'VEC3', 34962)
        attrs['TEXCOORD_0'] = g.accessor(s['uv'].astype(np.float32), 5126, 'VEC2', 34962)
        if skinned:
            j = np.zeros((len(s['pos']), 4), np.uint16); w = np.zeros((len(s['pos']), 4), np.float32)
            k = s['joints'].shape[1]
            j[:, :k] = np.vectorize(lambda b: joint_map.get(int(b), 0))(s['joints']); w[:, :k] = s['weights']
            w /= np.maximum(w.sum(1, keepdims=True), 1e-6)
            attrs['JOINTS_0'] = g.accessor(j, 5123, 'VEC4', 34962)
            attrs['WEIGHTS_0'] = g.accessor(w, 5126, 'VEC4', 34962)
        prims.append({'attributes': attrs, 'material': mats[t],
                      'indices': g.accessor(s['tris'].reshape(-1).astype(np.uint16), 5123, 'SCALAR', 34963)})
    g.j['meshes'].append({'name': name, 'primitives': prims})
    return len(g.j['meshes']) - 1


def skin_nodes(g, parents, offsets, names, parent_node=None, root_world=np.zeros(3)):
    """Joint nodes for a rest pose made of offsets only; returns (node ids, inverse bind matrices)."""
    ids, worlds = [], []
    for b, p in enumerate(parents):
        nid = g.node(name=names[b], translation=[float(v) * SCALE for v in offsets[b]])
        ids.append(nid)
        w = (worlds[p] if p >= 0 else root_world) + offsets[b]
        worlds.append(w)
        par = ids[p] if p >= 0 else parent_node
        if par is None: g.j['scenes'][0]['nodes'].append(nid)
        else: g.j['nodes'][par].setdefault('children', []).append(nid)
    ibm = np.zeros((len(ids), 4, 4), np.float32)
    for k, w in enumerate(worlds):
        m = np.eye(4); m[:3, 3] = -w * SCALE; ibm[k] = m.T     # glTF matrices are column-major
    return ids, worlds, ibm


def coat_skin(pos, body, hip_y):
    """Skin the coat to the body, since the game moves it by cloth simulation (its own 33 bones carry no motion):
    each coat vertex takes the leg and hip weights of the nearest body vertex, blended with LowerBody from none at
    the waist to most of the weight at the hem, so the tails swing with the legs."""
    bp = np.concatenate([s['pos'] for s in body]); bj = np.concatenate([s['joints'] for s in body])
    bw = np.concatenate([s['weights'] for s in body]).astype(np.float64)
    bw /= np.maximum(bw.sum(1, keepdims=True), 1e-6)
    keep = np.isin(bj[np.arange(len(bj)), bw.argmax(1)], COAT_FOLLOW)
    bp, bj, bw = bp[keep], bj[keep], bw[keep]
    near = np.argmin(((pos[:, None, :] - bp[None, :, :]) ** 2).sum(2), 1)
    a = np.clip((hip_y - pos[:, 1]) / 80, 0, 1)[:, None] * 0.75
    joints = np.concatenate([bj[near], np.full((len(pos), 1), LOWER_BODY)], 1)
    weights = np.concatenate([bw[near] * a, 1 - a], 1)
    return joints, weights


def body_glb(game):
    pac = D.subfiles(game.read('pl000.pac'))
    texs = D.textures(pac[0])
    body, coat = pac[1], pac[12]
    g = Gltf()
    parents, offsets = D.skeleton(body)
    ids, worlds, ibm = skin_nodes(g, parents, offsets, BONES)
    skin = {'joints': ids, 'inverseBindMatrices': g.accessor(ibm.reshape(-1, 16), 5126, 'MAT4')}
    g.j['skins'] = [skin]
    bm = D.meshes(body)
    mb = add_meshes(g, bm, texs, {k: k for k in range(len(ids))}, 'dante')
    cm = D.meshes(coat)
    for s in cm:
        s['pos'] = s['pos'] + worlds[COAT_PARENT]
        s['joints'], s['weights'] = coat_skin(s['pos'], bm, worlds[COAT_PARENT][1])
    mc = add_meshes(g, cm, texs, {k: k for k in range(len(ids))}, 'coat')
    for m in (mb, mc):
        g.j['scenes'][0]['nodes'].append(g.node(name=g.j['meshes'][m]['name'], mesh=m, skin=0))
    return g.glb(), parents, offsets


def weapon_glb(game, pacname, slot=1):
    pac = D.subfiles(game.read(pacname))
    texs = D.textures(pac[0]) if pac[0] else []
    m = pac[slot]
    parents, offsets = D.skeleton(m)
    g = Gltf()
    root = g.node(name='weapon')
    g.j['scenes'][0]['nodes'].append(root)
    subs = D.meshes(m)
    # rigid pose: every vertex follows its first bone, whose rest frame is translation only
    worlds = []
    for b, p in enumerate(parents):
        worlds.append((worlds[p] if p >= 0 else np.zeros(3)) + offsets[b])
    mid = add_meshes(g, subs, texs, {}, os.path.splitext(pacname)[0], skinned=False)
    g.j['nodes'][root]['mesh'] = mid
    return g.glb()


def quat(R):
    """3x3 rotation -> quaternion (x, y, z, w)."""
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = math.sqrt(t + 1) * 2; return np.array([(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, s / 4])
    i = int(np.argmax([R[0, 0], R[1, 1], R[2, 2]]))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + R[i, i] - R[j, j] - R[k, k]) * 2
    q = np.zeros(4); q[i] = s / 4; q[j] = (R[j, i] + R[i, j]) / s; q[k] = (R[k, i] + R[i, k]) / s; q[3] = (R[k, j] - R[j, k]) / s
    return q


def bake(segs, offsets):
    """FDA2 bytes for motions played in a row, segs = [(motion, first frame, frame count)]: one pose per frame, bone 0's
    translation as root motion, carried on from one motion to the next."""
    N = sum(n for _, _, n in segs)
    nb = len(offsets)
    R = np.zeros((nb, N, 4)); T = np.zeros((nb, N, 3)); root = np.zeros((N, 3), np.float32)
    i = 0
    for mot, t0, n in segs:
        first = i
        for k in range(n):
            for b, (rot, pos) in enumerate(D.local_pose(offsets, mot, t0 + k)):
                q = quat(rot)
                if i and np.dot(q, R[b, i - 1]) < 0: q = -q
                R[b, i] = q
                T[b, i] = pos * SCALE
            root[i] = T[0, i]; T[0, i] = 0
            i += 1
        # each motion's root track starts where the previous one ended
        root[first:i] += (root[first - 1] if first else 0) - root[first]
    flags, body = [], []
    for b in range(nb):
        f = (1 if np.ptp(R[b], axis=0).max() > 2e-4 else 0) | (2 if np.ptp(T[b], axis=0).max() > 1e-4 else 0)
        flags.append(f)
        body.append(pack_quats(R[b] if f & 1 else R[b, :1]).astype('<u4').tobytes())
        body.append(np.clip(np.round((T[b] if f & 2 else T[b, :1]) * 1000), -32768, 32767).astype('<i2').tobytes())
    out = b'FDA2' + struct.pack('<HHBB', nb, N, 1, 1) + np.arange(nb, dtype='<u2').tobytes() + bytes(flags) + b''.join(body)
    return out + root.astype('<f4').tobytes()


def main(game_dir, out=OUT):
    game = D.Game(game_dir)
    pac = D.subfiles(game.read('pl000.pac'))
    scripts, cols = D.Scripts(pac[5]), D.colliders(pac)
    os.makedirs(os.path.join(out, 'anim'), exist_ok=True)
    os.makedirs(os.path.join(out, 'moves'), exist_ok=True)
    data, parents, offsets = body_glb(game)
    open(os.path.join(out, 'dante.glb'), 'wb').write(data)
    weapons = {}
    for cid, (name, fam, pacname, hand) in M.CLASSES.items():
        if pacname and name not in weapons:
            fn = 'weapon-%s.glb' % cid
            open(os.path.join(out, fn), 'wb').write(weapon_glb(game, pacname))
            weapons[name] = {'model': pacname, 'file': fn, 'variation': 0}
    weapons['None'] = {'model': None, 'file': None, 'variation': 0}
    used = set()
    per_class = {cid: {} for cid in M.CLASSES}
    for mv in M.moves():
        segs = M.segments(game, scripts, mv)
        anim = mv['id'].replace('.', '-')
        open(os.path.join(out, 'anim', anim + '.bin'), 'wb').write(
            bake([(s['mot'], s['start'], max(s['end'] - s['start'], 1)) for s in segs], offsets))
        cid = mv['class']
        wname = M.CLASSES[cid][0] if M.CLASSES[cid][2] else 'None'
        hs = [{'start': h['start'], 'end': h['end'], 'judge': h['id']} for h in M.hits(segs, cols) if cols[h['id']]['sphere']]
        per_class[cid][mv['id']] = {'frames': M.timing(segs)[0], 'weapon': wname, 'anim': anim, 'hits': hs}
    classes = {}
    for cid, moves in per_class.items():
        if not moves: continue
        fn = 'moves/%s.json' % cid
        ids = sorted({h['judge'] for m in moves.values() for h in m['hits']})
        used.update(ids)
        attacks = {'0': {str(i): [{'a': i, 'r': round(cols[i]['sphere'][3] * SCALE, 4)}] for i in ids}}
        json.dump({'class': cid, 'moves': moves, 'attacks': attacks}, open(os.path.join(out, fn), 'w'),
                  separators=(',', ':'))
        classes[cid] = {'file': fn, 'weapon': M.CLASSES[cid][0] if M.CLASSES[cid][2] else 'None', 'hand': M.CLASSES[cid][3]}
    man = {'schema': 'frame-data-models/2', 'game': 'devil-may-cry-3', 'version': 'PS2 Special Edition (SLES-54186)',
           'fps': FPS, 'weaponTurn': False,
           'skeleton': {'weaponBone': 'R_Hand', 'leftWeaponBone': 'L_Hand', 'rootBone': 'Root', 'follow': 'Hips',
                        'fit': ['Head', 'L_Toe', 'R_Toe', 'L_Hand', 'R_Hand'], 'bones': BONES},
           'armor': {'name': 'Dante', 'file': 'dante.glb'}, 'weapons': weapons,
           'body': {str(i): [BONES[cols[i]['bone']]] + [round(v * SCALE, 4) for v in cols[i]['sphere'][:3]] for i in sorted(used)},
           'classes': classes}
    json.dump(man, open(os.path.join(out, 'models.json'), 'w'), indent=1)


if __name__ == '__main__':
    args = sys.argv[1:]
    out = os.environ.get('DMC3_OUT', OUT)
    main(args[0], out)

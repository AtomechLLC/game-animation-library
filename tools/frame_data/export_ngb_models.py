"""Exports what Move Explorer's 3D preview needs from Ninja Gaiden Black (Xbox): Ryu's model, the Dragon Sword and
every Dragon Sword move's motion, baked per frame. Same layout and animation format as export_dmc3_models.py, so
frame-data/viewer3d.js plays it.

    python tools/frame_data/export_ngb_models.py "C:/Games/Ninja Gaiden Black.iso"
    python tools/frame_data/export_ngb_models.py <folder with cmn.afs and chr_ryu.afs>

Reads only (ngb_files.py); writes frame-data/models/ninja-gaiden-black/:

    models.json             skeleton (Ryu's 15 body bones), the body, the sword and its mount, foot points for kicks
    ryu.glb                 chr_ryu.afs/ryu.kmd: the body parts (OBJINFO kind 1), each rigid on its bone, and the
                            joint fillers (kind 4) blended between their bone and its parent by the vertex weight.
                            Overlay passes (a second subset on the same vertices: the red eyes, the Dark Dragon veins)
                            and the scarf, which the game moves by cloth simulation, are left out. 256 px textures.
    weapon-dragon-sword.glb cmn.afs/katana.kmd object 0, placed as katana.itm's grip 2 puts it on the right hand
                            (bone 11): the root node carries that offset, and its extras.dummies the two ends of the
                            blade capsule from the same file (ids 1 and 2)
    anim/<move>.bin         the move's motion sampled once per tab frame (FDA2): root, spine and head as they are,
                            the arms and legs solved from the motion's end-effectors and hinge axes (ngb_files.bone_pose);
                            the hips' ground position is the root motion track
    moves/dragonSword.json  per move its frames, animation and hits (the script's attack windows: the sword capsule,
                            or a sphere on the kicking foot for slots 0x0c and 0x0d)
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import ngb_files as nf
import import_ngb_game as G
from export_dmc3_models import Gltf, pack_quats, encode, quat

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'frame-data', 'models', 'ninja-gaiden-black')
FPS = 60
ORDER = [2, 0, 1, 8, 4, 5, 14, 10, 11, 6, 7, 3, 12, 13, 9]          # KMD bone ids, parents first
NAMES = [nf.BONES[b] for b in ORDER]
SCARF = 'ki_o'                  # texture of the scarf tails (cloth)
GRIP = 2                        # katana.itm mount: the Dragon Sword in the right hand
FEET = {0x0c: ('foot-r', 101), 0x0d: ('foot-l', 100)}               # attack slot -> judge, body point
FOOT = {100: ['L_Foot', 0.0, -0.06, 0.08], 101: ['R_Foot', 0.0, -0.06, 0.08]}
FOOT_R = 0.15                   # no shape for the feet was found in the files: a sphere around the toes
FLOOR = 0.11                    # foot bone height when standing (the sole is on the floor)
AIR_START = 1.8                 # hips height air moves start from (their motions are relative to the jump)


def rest_world(kmd):
    W = {}
    def w(b):
        if b not in W:
            W[b] = kmd.obj[b]['T'] + (w(kmd.parent[b]) if kmd.parent[b] >= 0 else 0)
        return W[b]
    return [w(b) for b in range(15)]


def add_mesh(g, kmd, objs, name, skin=None):
    """One glTF mesh for the given objects, a primitive per subset; skin = (joint index per bone, rest world)."""
    mats, prims = {}, []
    for i in objs:
        m, ob = kmd.meshes[i], kmd.obj[i]
        if skin:
            jmap, W = skin
            if ob['kind'] == 1:
                pos = m['pos'] + W[i]
                joints = np.zeros((m['nv'], 4), np.uint16); joints[:, 0] = jmap[i]
                weights = np.zeros((m['nv'], 4), np.float32); weights[:, 0] = 1
            else:                                   # filler: its bone and the bone's parent
                b = kmd.parent[i]; p = kmd.parent[b]
                pos = m['pos'] + W[b]
                joints = np.zeros((m['nv'], 4), np.uint16); joints[:, 0] = jmap[b]; joints[:, 1] = jmap[p]
                weights = np.zeros((m['nv'], 4), np.float32); weights[:, 0] = 1 - m['w']; weights[:, 1] = m['w']
        else:
            pos = m['pos']
        seen = set()
        for s in m['subs']:
            key = bytes(np.unique(s['strip']))
            if not len(s['strip']) or key in seen or (s['names'] and s['names'][0] == SCARF):
                continue
            seen.add(key)
            tris = nf.strip_triangles(s['strip'])
            if not len(tris):
                continue
            used, inv = np.unique(tris, return_inverse=True)
            t = s['tex'][0] if s['tex'] and s['tex'][0] >= 0 else None
            if t not in mats:
                mat = {'name': '%s-%s' % (name, t), 'doubleSided': True,
                       'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 0.8}}
                if t is not None:
                    data, mime, alpha = encode(np.asarray(kmd.texture(t)))
                    mat['pbrMetallicRoughness']['baseColorTexture'] = {'index': g.image(data, mime)}
                    if alpha: mat.update(alphaMode='MASK', alphaCutoff=0.5)
                g.j['materials'].append(mat); mats[t] = len(g.j['materials']) - 1
            nrm = m['nrm'][used] / np.maximum(np.linalg.norm(m['nrm'][used], axis=1, keepdims=True), 1e-6)
            attrs = {'POSITION': g.accessor(pos[used].astype(np.float32), 5126, 'VEC3', 34962, minmax=True),
                     'NORMAL': g.accessor(nrm.astype(np.float32), 5126, 'VEC3', 34962),
                     'TEXCOORD_0': g.accessor(m['uv'][used].astype(np.float32), 5126, 'VEC2', 34962)}
            if skin:
                attrs['JOINTS_0'] = g.accessor(joints[used], 5123, 'VEC4', 34962)
                attrs['WEIGHTS_0'] = g.accessor(weights[used], 5126, 'VEC4', 34962)
            prims.append({'attributes': attrs, 'material': mats[t],
                          'indices': g.accessor(inv.reshape(-1).astype(np.uint16), 5123, 'SCALAR', 34963)})
    g.j['meshes'].append({'name': name, 'primitives': prims})
    return len(g.j['meshes']) - 1


def body_glb(kmd):
    g = Gltf()
    g.j['asset']['generator'] = 'export_ngb_models.py'
    W = rest_world(kmd)
    ids = []
    for k, b in enumerate(ORDER):
        p = kmd.parent[b]
        nid = g.node(name=NAMES[k], translation=[float(v) for v in kmd.obj[b]['T']])
        ids.append(nid)
        if p < 0: g.j['scenes'][0]['nodes'].append(nid)
        else: g.j['nodes'][ids[ORDER.index(p)]].setdefault('children', []).append(nid)
    ibm = np.zeros((len(ORDER), 4, 4), np.float32)
    for k, b in enumerate(ORDER):
        mtx = np.eye(4); mtx[:3, 3] = -W[b]; ibm[k] = mtx.T
    g.j['skins'] = [{'joints': ids, 'inverseBindMatrices': g.accessor(ibm.reshape(-1, 16), 5126, 'MAT4')}]
    objs = [i for i, o in enumerate(kmd.obj) if o['kind'] in (1, 4) and i < len(kmd.meshes)]
    mid = add_mesh(g, kmd, objs, 'ryu', ({b: ORDER.index(b) for b in ORDER}, W))
    g.j['scenes'][0]['nodes'].append(g.node(name='ryu', mesh=mid, skin=0))
    return g.glb()


def weapon_glb(kmd, mount, shape):
    g = Gltf()
    g.j['asset']['generator'] = 'export_ngb_models.py'
    mid = add_mesh(g, kmd, [0], 'dragon-sword')
    q = quat(nf.euler(np.radians(mount['rot'])))
    root = g.node(name='weapon', mesh=mid, translation=[float(v) for v in mount['pos']], rotation=[float(v) for v in q],
                  extras={'dummies': {'1': [float(v) for v in shape['a']], '2': [float(v) for v in shape['b']]}})
    g.j['scenes'][0]['nodes'].append(root)
    return g.glb()


def bake(T, parent, tracks, frames, air=False):
    """FDA2 bytes: one pose per tab frame (frame F is the motion at F, as in the 2D sheets); the hips' x/z is root
    motion, their height stays on the bone. The game's jump and gravity move Ryu in the air, not the motion, and air
    motions keep falling until the game sees the floor: here air moves start with the hips AIR_START up, and no frame
    goes below the floor."""
    nb, N = len(ORDER), frames
    Q = np.zeros((nb, N, 4)); P = np.zeros((nb, N, 3)); root = np.zeros((N, 3), np.float32)
    lift = None
    for i in range(N):
        R, X = nf.bone_pose(T, tracks, i + 1)
        if lift is None:
            lift = AIR_START - X[2][1] if air else 0.0
        X[2][1] += max(lift, FLOOR - min(X[3][1], X[9][1]))
        for k, b in enumerate(ORDER):
            local = R[b] if k == 0 else R[parent[b]].T @ R[b]
            q = quat(local)
            if i and np.dot(q, Q[k, i - 1]) < 0: q = -q
            Q[k, i] = q
            P[k, i] = T[b] if k else (0, X[b][1], 0)
        root[i] = (X[2][0], 0, X[2][2])
    flags, body = [], []
    for k in range(nb):
        f = (1 if np.ptp(Q[k], axis=0).max() > 2e-4 else 0) | (2 if np.ptp(P[k], axis=0).max() > 1e-4 else 0)
        flags.append(f)
        body.append(pack_quats(Q[k] if f & 1 else Q[k, :1]).astype('<u4').tobytes())
        body.append(np.clip(np.round((P[k] if f & 2 else P[k, :1]) * 1000), -32768, 32767).astype('<i2').tobytes())
    out = b'FDA2' + struct.pack('<HHBB', nb, N, 1, 1) + np.arange(nb, dtype='<u2').tobytes() + bytes(flags) + b''.join(body)
    return out + root.astype('<f4').tobytes()


def main(source, out=OUT):
    disc = nf.Disc(source)
    cmn = nf.afs(disc.read('cmn.afs'))
    kmd = nf.KMD(nf.afs(disc.read('chr_ryu.afs'))['ryu.kmd'])
    T = [o['T'] for o in kmd.obj]
    itm = cmn['katana.itm']
    mount, blade = nf.itm_mounts(itm)[GRIP], nf.itm_shapes(itm)[0]
    assert mount['bone'] == 11, mount
    os.makedirs(os.path.join(out, 'anim'), exist_ok=True)
    os.makedirs(os.path.join(out, 'moves'), exist_ok=True)
    open(os.path.join(out, 'ryu.glb'), 'wb').write(body_glb(kmd))
    open(os.path.join(out, 'weapon-dragon-sword.glb'), 'wb').write(weapon_glb(nf.KMD(cmn['katana.kmd']), mount, blade))
    mtn = cmn['ryu.mtn']
    sec = nf.sections(mtn)
    rows = G.frame_data(nf.scripts(mtn), nf.Bank(cmn['rm_kt.mot']), nf.Bank(mtn, sec[0], sec[1]))
    moves, baked = {}, {}
    for r, sid, bank, m, wins in rows:
        if not bank.has(m):
            continue
        key = (id(bank), m, r['total'], r['grip'])
        if key not in baked:
            baked[key] = r['id'].replace('.', '-')
            open(os.path.join(out, 'anim', baked[key] + '.bin'), 'wb').write(bake(T, kmd.parent, bank.tracks(m), r['total'], r['grip'] == 'air'))
        hits = [{'start': a, 'end': b, 'judge': 'sword' if slot == 0 else FEET[slot][0]} for slot, a, b in wins
                if slot == 0 or slot in FEET]
        moves[r['id']] = {'frames': r['total'], 'weapon': 'Dragon Sword', 'anim': baked[key], 'hits': hits}
    attacks = {'dragonSword': {'sword': [{'a': 10001, 'b': 10002, 'r': blade['r']}],
                               **{j: [{'a': pt, 'r': FOOT_R}] for j, pt in FEET.values()}}}
    json.dump({'class': 'dragonSword', 'moves': moves, 'attacks': attacks},
              open(os.path.join(out, 'moves', 'dragonSword.json'), 'w'), separators=(',', ':'))
    man = {'schema': 'frame-data-models/2', 'game': G.GAME_ID, 'version': 'Xbox, USA (5443000D)', 'fps': FPS,
           'weaponTurn': False, 'mirror': False,
           'skeleton': {'weaponBone': 'R_Hand', 'leftWeaponBone': 'L_Hand', 'rootBone': 'Hips', 'follow': 'Hips',
                        'fit': ['Head', 'L_Foot', 'R_Foot', 'L_Hand', 'R_Hand'], 'bones': NAMES},
           'armor': {'name': 'Ryu Hayabusa', 'file': 'ryu.glb'},
           'weapons': {'Dragon Sword': {'model': 'katana.kmd', 'file': 'weapon-dragon-sword.glb', 'variation': 'dragonSword'}},
           'body': {str(k): v for k, v in FOOT.items()},
           'classes': {'dragonSword': {'file': 'moves/dragonSword.json', 'weapon': 'Dragon Sword', 'hand': 'R'}}}
    json.dump(man, open(os.path.join(out, 'models.json'), 'w'), indent=1)
    print('%d moves, %d animations' % (len(moves), len(baked)))


if __name__ == '__main__':
    main(sys.argv[1], os.environ.get('NGB_OUT', OUT))

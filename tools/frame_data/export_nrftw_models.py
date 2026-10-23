"""Exports what the Frame Data tab's 3D preview needs from a No Rest for the Wicked install: the player skeleton wearing
one armor set, weapon models, each move's animation and its per-frame hitboxes. Same output layout and animation
format as export_er_models.py, so frame-data/viewer3d.js plays both.

    python tools/frame_data/export_nrftw_models.py "Z:/SteamLibrary/steamapps/common/NoRestForTheWicked"
    python tools/frame_data/export_nrftw_models.py "<install>" greatSwords doubleDaggers      # only these classes

Reads only (nrftw_files.py for the gameplay database, nrftw_unity.py for prefabs, meshes and clips); writes
frame-data/models/no-rest-for-the-wicked/:

    models.json             skeleton (playerRig.fbx transforms), armor, every weapon (model file), per class its preview
                            weapon and moves file
    moves/<class>.json      per move id its frames, preview weapon, animation file and hits; per weapon its hitbox
                            shapes (the weapon's ColliderData boxes, by collider id)
    armor-<set>.glb         the armor set's skinned meshes on the playerRig skeleton (rest pose = playerRig.fbx),
                            albedo textures at 512 px. Unity space (left-handed): the viewer mirrors X at the root.
    weapon-<name>.glb       the weapon's view prefab: node R (weaponRoot / weaponRootRight) and, for dual weapons, node L,
                            each at the grip; 256 px textures, int16 positions, int8 normals
    anim/<action>.bin       the action's animation clips baked at 60 fps (the tab's frames), packed as in
                            export_er_models.py ('FDA2'), bone poses every 2nd frame (STEP); root_JNT's translation
                            becomes the per-frame root motion track; bones the armor doesn't skin are left out

Hitboxes: each WeaponColliders entry of an action gives the frames a collider is out and its socket's baked path
(Moon's fixed-point curve ext types 13 and 14, in root_JNT space), and
the weapon's ColliderData gives the box (half extents, offset and rotation in socket space) for that collider id. The
viewer puts the box on the hand socket: where the clip's timing can be fitted to the baked path (see warp), the two are
identical, rotation included. On the other half of the moves the baked path doesn't follow the visual clip at any
timing, so drawing it would leave the box away from the weapon; anchoring to the socket keeps it on the blade.
"""
import io, json, math, os, re, struct, sys
import numpy as np
from PIL import Image
import nrftw_files as N
import nrftw_unity as U
from export_er_models import Gltf, pack_quats

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'frame-data', 'models', 'no-rest-for-the-wicked')
FPS = 60

EXPORT = {
    'armor': ('knight', 'Male'),             # quantumPrefabs/hero/armors/<set>/hero<Male|Female><Set><Part>.prefab
    'preview': {'greatSwords': 'Claymore'},  # class -> weapon shown when none is picked (default: the class's first)
}
ARMOR_PARTS = ('BodyArmor', 'Gloves', 'Helmet', 'Pants')
RIG = 'Assets/models/player/playerRig.fbx'
TEX_SIZE = 512
WEAPON_TEX_SIZE = 256
LEFT_HAND = {'bows'}

# --- glTF helpers --------------------------------------------------------------------------------------------------

def encode(im, size):
    im = im.convert('RGBA')
    if max(im.size) > size:
        f = size / max(im.size)
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)
    alpha = im.getchannel('A').getextrema()[0] < 250
    buf = io.BytesIO()
    if alpha: im.save(buf, 'PNG', optimize=True); mime = 'image/png'
    else: im.convert('RGB').save(buf, 'JPEG', quality=82, optimize=True); mime = 'image/jpeg'
    return buf.getvalue(), mime, alpha

def add_mesh(g, md, image, name, tex_size, quant=False, joints=None, textures=None):
    """One Unity mesh (nrftw_unity.mesh_data) -> glTF mesh, one primitive per submesh, sharing one texture. joints
    maps the mesh's bone indices to skin joint indices. quant stores int16 positions; returns (mesh, offset, scale)."""
    pos = md['pos']
    attrs = {}
    off, scale = None, None
    if quant:
        g.j.setdefault('extensionsUsed', ['KHR_mesh_quantization']); g.j['extensionsRequired'] = ['KHR_mesh_quantization']
        lo, hi = pos.min(axis=0), pos.max(axis=0)
        off = (lo + hi) / 2; scale = max(float((hi - lo).max()) / 65534, 1e-6)
        attrs['POSITION'] = g.accessor(np.round((pos - off) / scale).astype(np.int16), 5122, 'VEC3', 34962, minmax=True)
    else:
        attrs['POSITION'] = g.accessor(pos, 5126, 'VEC3', 34962, minmax=True)
    if md['normal'] is not None:
        n = md['normal'] / np.maximum(np.linalg.norm(md['normal'], axis=1, keepdims=True), 1e-6)
        attrs['NORMAL'] = g.accessor(np.round(n * 127).astype(np.int8), 5120, 'VEC3', 34962, normalized=True)
    if md['uv'] is not None:
        uv = md['uv'].copy(); uv[:, 1] = 1 - uv[:, 1]       # Unity's v runs up, glTF's down
        attrs['TEXCOORD_0'] = g.accessor(uv.astype(np.float32), 5126, 'VEC2', 34962)
    if joints is not None:
        j = np.vectorize(lambda k: joints.get(int(k), 0))(md['joints']).astype(np.uint16) if md['joints'] is not None \
            else np.zeros((len(pos), 4), np.uint16)
        w = md['weights'] if md['weights'] is not None else np.tile([1, 0, 0, 0], (len(pos), 1)).astype(np.float32)
        w = w / np.maximum(w.sum(axis=1, keepdims=True), 1e-6)
        attrs['JOINTS_0'] = g.accessor(j, 5123, 'VEC4', 34962)
        attrs['WEIGHTS_0'] = g.accessor(w.astype(np.float32), 5126, 'VEC4', 34962)
    material = {'name': name, 'pbrMetallicRoughness': {'metallicFactor': 0.1, 'roughnessFactor': 0.8}, 'doubleSided': True}
    if image is not None:
        # image: a PIL image, or a Texture2D shared by several meshes (stored once, via textures)
        key = getattr(image, 'm_Name', None)
        if textures is not None and key in textures: idx, alpha = textures[key]
        else:
            data, mime, alpha = encode(image.image if key else image, tex_size)
            idx = g.image(data, mime)
            if textures is not None and key: textures[key] = (idx, alpha)
        material['pbrMetallicRoughness']['baseColorTexture'] = {'index': idx}
        if alpha: material.update(alphaMode='MASK', alphaCutoff=0.5)
    g.j['materials'].append(material)
    mat = len(g.j['materials']) - 1
    prims = []
    for tri in md['tris']:
        if not len(tri): continue
        small = len(pos) < 65536
        prims.append({'attributes': attrs, 'material': mat,
                      'indices': g.accessor(tri.reshape(-1).astype(np.uint16 if small else np.uint32), 5123 if small else 5125, 'SCALAR', 34963)})
    g.j['meshes'].append({'name': name, 'primitives': prims})
    return len(g.j['meshes']) - 1, off, scale

def mat4(m):
    """UnityPy Matrix4x4f -> numpy (row-major)."""
    return np.array([[getattr(m, f'e{r}{c}') for c in range(4)] for r in range(4)], np.float64)

# --- baked curves (Moon's ext 13 / 14 / 15) ------------------------------------------------------------------------

def fp_curve(ext, dims):
    """[(time, values)] from a baked fixed-point curve: per key an int64 time then dims int64 values, 16.16 fixed."""
    if not isinstance(ext, tuple) or not ext[2]: return None
    b = ext[2]
    v = np.frombuffer(b[:len(b) // 8 * 8], '<i8').astype(np.float64) / 65536
    v = v[:len(v) // (dims + 1) * (dims + 1)].reshape(-1, dims + 1)
    return v

def sample_curve(c, t):
    """Linear interpolation of a baked curve at times t."""
    return np.stack([np.interp(t, c[:, 0], c[:, k]) for k in range(1, c.shape[1])], axis=-1)

# --- animation -----------------------------------------------------------------------------------------------------

STEP = 2   # bone poses every 2nd frame (the viewer interpolates); root motion and hitboxes stay per frame

def bake(tracks, frames, bone_index, root, step=STEP):
    """FDA2: tracks {bone name: (T[frames,3], R[frames,4])}; root: [frames,3] or None. Layout in export_er_models.py,
    with the header's spare byte holding the step: per-frame tracks then hold ceil(frames / step) poses, for frames
    0, step, 2 step... (Elden Ring files have 0 there: every frame)."""
    bones = sorted(bone_index[b] for b in tracks)
    names = {bone_index[b]: b for b in tracks}
    keep = np.arange(0, frames, step)
    flags, body = [], []
    for bi in bones:
        T, R = tracks[names[bi]]
        T, R = T[keep], R[keep]
        f = (1 if np.ptp(R, axis=0).max() > 2e-4 else 0) | (2 if np.ptp(T, axis=0).max() > 1e-4 else 0)
        flags.append(f)
        body.append(pack_quats(R if f & 1 else R[:1]).astype('<u4').tobytes())
        mm = np.round((T if f & 2 else T[:1]) * 1000)
        body.append(np.clip(mm, -32768, 32767).astype('<i2').tobytes())
    out = b'FDA2' + struct.pack('<HHBB', len(bones), frames, root is not None, step)
    out += np.array(bones, '<u2').tobytes() + bytes(flags) + b''.join(body)
    return out + (root.astype('<f4').tobytes() if root is not None else b'')

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

class Exporter:
    def __init__(self, game_dir):
        self.g = N.Game(game_dir)
        print('loading bundles...')
        self.A = U.Assets(game_dir)
        rig = next(go for go in self.A.all(RIG, 'GameObject') if not U.transform(go).m_Father.m_PathID)
        self.nodes = U.walk(U.transform(rig))          # (transform, parent, path)
        self.bones = [p.rsplit('/', 1)[-1] if p else 'playerRig' for _, _, p in self.nodes]
        self.bone_index = {b: i for i, b in enumerate(self.bones)}
        self.by_hash = {}
        for i, (_, _, p) in enumerate(self.nodes):
            self.by_hash[U.path_hash(p)] = i
            self.by_hash.setdefault(U.path_hash(p.rsplit('/', 1)[-1]), i)
        self.rest = [U.local_trs(t) for t, _, _ in self.nodes]
        self.lut = self.g.asset('Assets/worldlut.asset')
        self.clips = {}
        self.skinned = set()

    def needed(self):
        """Bones worth animating: the armor's skin joints, the weapon sockets and root_JNT, with their ancestors."""
        keep = set(self.skinned) | {self.bone_index[b] for b in ('root_JNT', 'armR1_hand_weapon_socket', 'armL1_hand_weapon_socket')}
        for b in list(keep):
            while b >= 0: keep.add(b); b = self.nodes[b][1]
        return {self.bones[b] for b in keep}

    # -- armor --
    def armor(self, set_name, sex):
        g = Gltf(); g.j['asset']['generator'] = 'export_nrftw_models.py'
        for i, (b, (t, q, s)) in enumerate(zip(self.bones, self.rest)):
            g.node(name=b, translation=t.tolist(), rotation=q.tolist(), scale=s.tolist() if np.abs(s - 1).max() > 1e-6 else None)
        for i, (_, parent, _) in enumerate(self.nodes):
            if parent >= 0: g.j['nodes'][parent].setdefault('children', []).append(i)
        g.j['scenes'][0]['nodes'] = [0]
        meshes, textures = 0, {}
        for part in ARMOR_PARTS:
            path = f'Assets/AddressableAssets/quantumPrefabs/hero/armors/{set_name}/hero{sex}{set_name[0].upper()}{set_name[1:]}{part}.prefab'
            go = self.A.get(path, 'GameObject')
            if go is None: print('  no prefab', path); continue
            for smr in self._smrs(go):
                mats = [m.read() for m in smr.m_Materials if m.m_PathID]
                if not mats or mats[0].m_Shader.read().m_ParsedForm.m_Name.endswith('baseSimple'): continue
                mesh = smr.m_Mesh.read()
                md = U.mesh_data(mesh)
                hashes = list(mesh.m_BoneNameHashes)
                fallback = self.by_hash.get(mesh.m_RootBoneNameHash, 0)
                jn = [self.by_hash.get(h, fallback) for h in hashes]
                self.skinned.update(jn)
                binds = [mat4(m) for m in mesh.m_BindPose]
                ibm = np.stack([b.T for b in binds]).astype(np.float32)    # glTF wants column-major
                g.j.setdefault('skins', []).append({'joints': jn, 'inverseBindMatrices': g.accessor(ibm.reshape(-1, 16), 5126, 'MAT4')})
                skin = len(g.j['skins']) - 1
                mi, _, _ = add_mesh(g, md, U.albedo(mats[0]), mesh.m_Name, TEX_SIZE, joints={k: k for k in range(len(jn))},
                                    textures=textures)
                n = g.node(name=mesh.m_Name, mesh=mi, skin=skin)
                g.j['nodes'][0].setdefault('children', []).append(n)
                meshes += 1
        print(f'  armor {set_name}: {meshes} meshes')
        return g.glb(), {'name': f'{set_name[0].upper()}{set_name[1:]} set', 'file': f'armor-{slug(set_name)}.glb'}

    def _smrs(self, go, out=None):
        out = [] if out is None else out
        out += U.comps(go, 'SkinnedMeshRenderer')
        for ch in U.transform(go).m_Children: self._smrs(ch.read().m_GameObject.read(), out)
        return out

    # -- weapons --
    def weapon(self, arm):
        """glb of a weapon's view prefab: a node per weapon root (R, L), meshes under it with their local transforms."""
        addr = arm['ViewAssets'][0]['Address'] if arm.get('ViewAssets') else None
        go = addr and self.A.get('Assets/armaments/' + addr, 'GameObject')
        if go is None: return None
        g = Gltf(); g.j['asset']['generator'] = 'export_nrftw_models.py'
        top = g.node(name='weapon'); g.j['scenes'][0]['nodes'] = [top]
        textures = {}
        def add(tr, parent):
            go = tr.m_GameObject.read()
            t, q, s = U.local_trs(tr)
            kw = {}
            name = go.m_Name
            if parent == top:
                name = 'L' if name.endswith('Left') else 'R'     # weaponRoot / weaponRootRight / weaponRootLeft
            else:
                kw = dict(translation=t.tolist() if np.abs(t).max() > 1e-6 else None,
                          rotation=q.tolist() if np.abs(q[:3]).max() > 1e-6 else None,
                          scale=s.tolist() if np.abs(s - 1).max() > 1e-6 else None)
            mf, mr = U.comps(go, 'MeshFilter'), U.comps(go, 'MeshRenderer')
            n = g.node(name=name, **kw)
            g.j['nodes'][parent].setdefault('children', []).append(n)
            mesh = mats = None
            if mf and mr and mf[0].m_Mesh.m_PathID and mr[0].m_Enabled:
                mats = [m.read() for m in mr[0].m_Materials if m.m_PathID]
                mesh = mf[0].m_Mesh.read()
            for smr in U.comps(go, 'SkinnedMeshRenderer'):
                # bows and some spears and staves are rigged: shown rigid, in their bind pose
                ms = [m.read() for m in smr.m_Materials if m.m_PathID]
                if smr.m_Mesh.m_PathID and smr.m_Enabled and ms and not ms[0].m_Shader.read().m_ParsedForm.m_Name.endswith('baseSimple'):
                    mats, mesh = ms, smr.m_Mesh.read()
            if mesh is not None:
                mi, off, scale = add_mesh(g, U.mesh_data(mesh), U.albedo(mats[0]) if mats else None, mesh.m_Name,
                                          WEAPON_TEX_SIZE, quant=True, textures=textures)
                g.node(name=mesh.m_Name + '_q', mesh=mi, translation=off.tolist(), scale=[scale] * 3)
                g.j['nodes'][n].setdefault('children', []).append(len(g.j['nodes']) - 1)
            for ch in tr.m_Children: add(ch.read(), n)
        for ch in U.transform(go).m_Children:
            c = ch.read()
            if c.m_GameObject.read().m_Name.startswith('weaponRoot'): add(c, top)
        return g.glb()

    # -- animation --
    def clip(self, qanim_guid):
        """The AnimationClip behind a .qanim (qanim -> SourceAnim wrapper -> Clip)."""
        if qanim_guid in self.clips: return self.clips[qanim_guid]
        c = None
        path = self.g.path.get(qanim_guid)
        mb = path and self.A.get(path)
        if mb is not None:
            src = getattr(mb, 'SourceAnim', None)
            if src is not None and src.m_PathID:
                w = src.read()
                c = w.read() if hasattr(w, 'm_MuscleClip') else (w.Clip.read() if getattr(w, 'Clip', None) and w.Clip.m_PathID else None)
                if c is not None and not hasattr(c, 'm_MuscleClip'): c = None
        self.clips[qanim_guid] = c
        return c

    def move_anim(self, action):
        """Bone tracks and root motion of an action, one pose per 60 fps frame over its Duration."""
        T = action['TimelineData']
        frames = max(1, int(round(N_fx(T['Duration']) * FPS)))
        tracks, root = {}, None
        for seg in sorted(action.get('Animations', []), key=lambda a: a['StartFrame']):
            clip = self.clip(seg['Animation']['Id']['Value'])
            if clip is None: continue
            a, n = seg['StartFrame'], seg['FrameCount']
            if a >= frames: continue
            idx = np.arange(a, frames if seg is action['Animations'][-1] else min(frames, a + n))
            times = np.clip((idx - a) / FPS, 0, U.clip_length(clip))
            warp = self.warp(action, clip) if len(action['Animations']) == 1 and a == 0 else None
            if warp is not None:
                k = min(len(warp), len(times))
                times[:k] = warp[:k]
                if len(times) > k: times[k:] = np.clip(warp[-1] + np.arange(1, len(times) - k + 1) / FPS, 0, U.clip_length(clip))
            s = U.sample_clip(clip, times)
            for (h, attr), v in s.items():
                bi = self.by_hash.get(h)
                if bi is None or attr not in (1, 2): continue
                name = self.bones[bi]
                if name not in self.keep: continue
                if name not in tracks:
                    t0, q0, _ = self.rest[bi]
                    tracks[name] = (np.tile(t0, (frames, 1)), np.tile(q0, (frames, 1)))
                tracks[name][0 if attr == 1 else 1][idx] = v
        if not tracks: return None
        if 'root_JNT' in tracks:
            Tr, Rr = tracks['root_JNT']
            root = Tr - Tr[0]                     # clips can start away from the origin
            tracks['root_JNT'] = (np.tile(self.rest[self.bone_index['root_JNT']][0], (frames, 1)), Rr)
        # keep quaternions on one hemisphere frame to frame
        for name, (Tt, R) in tracks.items():
            for i in range(1, len(R)):
                if np.dot(R[i], R[i - 1]) < 0: R[i] = -R[i]
        return frames, bake(tracks, frames, self.bone_index, root)

    # -- timing --
    def socket_track(self, clip, times, sock):
        """Positions of a socket relative to root_JNT at clip times (forward kinematics of the clip)."""
        root = self.bone_index['root_JNT']
        tr = {}
        for (h, attr), v in U.sample_clip(clip, times).items():
            bi = self.by_hash.get(h)
            if bi is not None and attr in (1, 2): tr.setdefault(bi, {})[attr] = v
        chain, b = [], sock
        while b != root and b >= 0: chain.append(b); b = self.nodes[b][1]
        n = len(times)
        P, Rm = np.zeros((n, 3)), np.tile(np.eye(3), (n, 1, 1))
        for b in reversed(chain):
            t0, q0, _ = self.rest[b]
            t = tr.get(b, {}).get(1, np.tile(t0, (n, 1))); q = tr.get(b, {}).get(2, np.tile(q0, (n, 1)))
            x, y, z, w = q.T
            M = np.stack([np.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], -1),
                          np.stack([2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], -1),
                          np.stack([2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)], -1)], -2)
            P = P + np.einsum('nij,nj->ni', Rm, t); Rm = Rm @ M
        return P

    def warp(self, action, clip, grid_hz=120, max_step=10, tolerance=0.08):
        """Clip time per action frame, or None. The game retimes clips (segment RetimingFrames, Animations
        FrameCount shorter than the clip), and its baked collider track records where the weapon socket really is each
        frame. Dynamic time warping of the clip's own socket path onto that track recovers the timing; it is used only
        when the fitted path stays within `tolerance` metres of the track while the hitbox is out (about half the
        moves; the rest keep the clip's own speed)."""
        wcs = [w for w in action['TimelineData'].get('WeaponColliders', []) if fp_curve(w['PositionCurve']['Keys'], 3) is not None]
        if not wcs: return None
        wc = wcs[0]; pc = fp_curve(wc['PositionCurve']['Keys'], 3)
        s = int(round(N_fx(wc['StartTime']) * FPS)); e = int(round(N_fx(wc['EndTime']) * FPS))
        L = U.clip_length(clip)
        grid = np.arange(0, L + 1e-9, 1 / grid_hz)
        F = int(round(pc[-1, 0] * FPS)) + 1
        target = sample_curve(pc, np.arange(F) / FPS)
        best = None
        for sock in ('armR1_hand_weapon_socket', 'armL1_hand_weapon_socket'):
            P = self.socket_track(clip, grid, self.bone_index[sock])
            cost = np.linalg.norm(P[None] - target[:, None], axis=2)
            G, nat = len(grid), grid_hz / FPS
            D = cost[0] + 0.02 * np.arange(G) / grid_hz
            back = np.zeros((F, G), int)
            for f in range(1, F):
                bestc = np.full(G, np.inf); arg = np.zeros(G, int)
                for k in range(max_step + 1):
                    prev = np.full(G, np.inf); prev[k:] = D[:G - k] if k else D
                    cand = prev + 0.002 * abs(k - nat)
                    m = cand < bestc; bestc[m] = cand[m]; arg[m] = (np.arange(G) - k)[m]
                D = bestc + cost[f]; back[f] = arg
            j = int(np.argmin(D)); path = [j]
            for f in range(F - 1, 0, -1): j = back[f][j]; path.append(j)
            path = path[::-1]
            err = cost[np.arange(F), path][s:e + 1].max() if e < F else np.inf
            if best is None or err < best[0]: best = (err, grid[path])
        return best[1] if best[0] < tolerance else None

    # -- hitboxes --
    def hits(self, action):
        """Hitbox windows and the collider each one uses; the viewer puts the weapon's box for that collider on the
        hand socket (the baked collider tracks are that socket's path, rotation included)."""
        out = []
        for wc in action['TimelineData'].get('WeaponColliders', []):
            s = int(round(N_fx(wc['StartTime']) * FPS)) + 1
            e = max(s, int(round(N_fx(wc['EndTime']) * FPS)))
            out.append({'start': s, 'end': e, 'collider': str(wc['ColliderIdRef']['Id']['Value'])})
        return out

    def colliders(self, arm, filt):
        """{collider id: {e: half extents, o: offset, r: rotation}} from the weapon's ColliderData, over its class's."""
        out = {}
        for ref in (filt.get('WeaponCollider'), arm.get('WeaponCollider')):
            cd = ref and ref['Id']['Value'] and self.g.asset(ref)
            for c in (cd or {}).get('Colliders', []):
                fx = lambda v: [round(N_fx(v[k]), 4) for k in ('X', 'Y', 'Z', 'W') if k in v]
                e, o = fx(c['Extents']), fx(c['Offset'])
                # The box runs from Offset along the socket's +Y (the blade) for twice Extents.Y, centred on X and Z:
                # that is where every weapon's own trail markers put its blade
                box = {'e': e, 'o': [o[0], round(o[1] + e[1], 4), o[2]], 'r': fx(c['RotOffset'])}
                if 'left' in c['Name'].lower(): box['hand'] = 'L'      # dual weapons: leftBlade / leftFist...
                out[str(c['ColliderID']['Id']['Value'])] = box
        return out

def N_fx(v):
    return v['RawValue'] / 65536 if isinstance(v, dict) else v

def main(game_dir, only=None):
    ex = Exporter(game_dir)
    g = ex.g
    fd = json.load(open(os.path.join(ROOT, 'frame-data', 'no-rest-for-the-wicked.json'), encoding='utf-8'))
    for d in ('anim', 'moves'): os.makedirs(os.path.join(OUT, d), exist_ok=True)
    glb, armor = ex.armor(*EXPORT['armor'])
    ex.keep = ex.needed()
    print(f'  animating {len(ex.keep)} of {len(ex.bones)} bones')
    open(os.path.join(OUT, armor['file']), 'wb').write(glb)
    print('armor', armor['file'], len(glb) // 1024, 'KB')
    manifest = {'schema': 'frame-data-models/2', 'game': 'no-rest-for-the-wicked', 'version': fd['game']['version'],
                'fps': FPS, 'weaponTurn': False,
                'skeleton': {'weaponBone': 'armR1_hand_weapon_socket', 'leftWeaponBone': 'armL1_hand_weapon_socket',
                             'rootBone': 'root_JNT', 'follow': 'spineC1_mainJoint1_JNT',
                             'fit': ['headC1_base1_JNT', 'footL1_toesJoint_JNT', 'footR1_toesJoint_JNT', 'armL1_hand_weapon_socket', 'armR1_hand_weapon_socket'],
                             'bones': ex.bones},
                'armor': armor, 'body': {}, 'weapons': {}, 'classes': {}}
    # weapon name -> armament, from the same lookup the frame data importer used
    arms = {}
    for arm in ex.lut['Armaments']:
        item = g.path.get(arm['Weapons'][0]['Id']['Value']) if arm['Weapons'] else None
        if item: arms[g.english(item)] = arm
    filters = {f['Data']['Id']['Value']: f for f in ex.lut['ArmamentFilters']}
    classes = [c for c in fd['classes'] if not only or c['id'] in only]
    wsize = 0
    for c in classes:
        for name in c['weapons']:
            arm = arms.get(name)
            if arm is None: print('  no armament for', name); continue
            file = f'weapon-{slug(name)}.glb'
            glb = ex.weapon(arm)
            if glb is None: print('  no view prefab for', name); continue
            open(os.path.join(OUT, file), 'wb').write(glb); wsize += len(glb)
            manifest['weapons'][name] = {'file': file}
    print(f'weapons: {len(manifest["weapons"])} models, {wsize / 1e6:.1f} MB')
    asize, baked = 0, {}
    action_of = {p.rsplit('/', 1)[-1][:-len('.action')]: gid for gid, p in g.path.items() if p.endswith('.action')}
    for c in classes:
        cls, names = c['id'], c['weapons']
        preferred = EXPORT['preview'].get(cls, names[0])
        moves, shapes, size = {}, {}, 0
        for m in fd['moves']:
            if m['class'] != cls: continue
            gid = action_of.get(m['action'])
            action = g.asset(gid) if gid else None
            if action is None: continue
            if m['action'] not in baked:
                r = ex.move_anim(action)
                if r is None: print('  no animation for', cls, m['id']); baked[m['action']] = None; continue
                frames, data = r
                open(os.path.join(OUT, 'anim', f"{m['action']}.bin"), 'wb').write(data)
                size += len(data); baked[m['action']] = frames
            if baked[m['action']] is None: continue
            users = [names[i] for i in m['weapons']] or names
            users = [u for u in users if u in manifest['weapons']] or [u for u in names if u in manifest['weapons']]
            if not users: continue
            moves[m['id']] = {'frames': baked[m['action']], 'anim': m['action'],
                              'weapon': preferred if preferred in users else users[0], 'hits': ex.hits(action)}
            for wn in users:
                if wn not in shapes:
                    arm = arms[wn]
                    shapes[wn] = ex.colliders(arm, filters.get(arm['Filter']['Id']['Value'], {}))
        file = f'moves/{slug(cls)}.json'
        with open(os.path.join(OUT, file), 'w', encoding='utf-8') as f:
            json.dump({'class': cls, 'moves': moves, 'boxes': shapes}, f, ensure_ascii=False, separators=(',', ':'))
        manifest['classes'][cls] = {'file': file, 'weapon': preferred if preferred in manifest['weapons'] else next((w for w in names if w in manifest['weapons']), None),
                                    **({'hand': 'L'} if cls in LEFT_HAND else {})}
        asize += size
        print(f'  {cls}: {len(moves)} moves, {size // 1024} KB of animation')
    with open(os.path.join(OUT, 'models.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(',', ':'))
    print(f'animation: {asize / 1e6:.1f} MB')

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1], set(sys.argv[2:]) or None)

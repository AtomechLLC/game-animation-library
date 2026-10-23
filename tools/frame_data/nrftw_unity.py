"""Unity side of No Rest for the Wicked: prefabs, skinned meshes, textures and Mecanim animation clips, read with UnityPy
from the Addressables bundles. Read-only.

    bundles      StreamingAssets/aa/StandaloneWindows64/*.bundle; prefabs live in pooled_prefabs, meshes and clips in
                 duplicateassetisolation, textures spread over the rest. Everything except the scene bundles is loaded
                 into one UnityPy environment so cross-bundle references resolve (~20 s).
    clips        AnimationClip.m_MuscleClip.m_Clip: a streamed clip (cubic Hermite keys), a dense clip (sampled
                 frames) and a constant clip, in that curve order. m_ClipBindingConstant.genericBindings name each
                 curve group: path = CRC32 of the transform path under the animated root, attribute 1 position (3
                 curves), 2 rotation quaternion (4), 3 scale (3), 4 euler (3), anything else one float curve.
Unity is left-handed (x right, y up, z forward); everything here stays in Unity space.
"""
import os, struct, zlib
import numpy as np

DATA = 'NoRestForTheWicked_Data/StreamingAssets/aa/StandaloneWindows64'
SKIP = ('world_scenes_', 'static_scenes_')

class Assets:
    def __init__(self, game_dir):
        import UnityPy
        folder = os.path.join(game_dir, DATA)
        self.env = UnityPy.load(*[os.path.join(folder, f) for f in sorted(os.listdir(folder))
                                  if f.endswith('.bundle') and not f.startswith(SKIP)])
        # every asset an Addressables path names (a .fbx names its GameObject, meshes, avatar and clips)
        self.paths = {}
        for o in self.env.objects:
            if o.type.name != 'AssetBundle': continue
            ab = o.read()
            for k, v in ab.m_Container:
                self.paths.setdefault(k, []).append(v.asset)

    def get(self, path, type_name=None):
        """The first object an Addressables path names (of a type), read."""
        for p in self.paths.get(path, []):
            if p.m_PathID and (type_name is None or p.type.name == type_name): return p.read()
        return None

    def all(self, path, type_name):
        return [p.read() for p in self.paths.get(path, []) if p.m_PathID and p.type.name == type_name]

# --- hierarchy -----------------------------------------------------------------------------------------------------

def comps(go, type_name):
    out = []
    for c in go.m_Component:
        p = c.component if hasattr(c, 'component') else c
        if p.m_PathID and p.type.name == type_name: out.append(p.read())
    return out

def transform(go):
    return comps(go, 'Transform')[0]

def walk(tr, parent=-1, out=None, path=''):
    """Transforms under tr, depth first: [(transform, parent index, path from tr's children)]."""
    out = [] if out is None else out
    name = tr.m_GameObject.read().m_Name
    me = len(out)
    out.append((tr, parent, path))
    for ch in tr.m_Children:
        c = ch.read()
        walk(c, me, out, (path + '/' if path else '') + c.m_GameObject.read().m_Name)
    return out

def local_trs(tr):
    p, q, s = tr.m_LocalPosition, tr.m_LocalRotation, tr.m_LocalScale
    return np.array([p.x, p.y, p.z]), np.array([q.x, q.y, q.z, q.w]), np.array([s.x, s.y, s.z])

# --- meshes --------------------------------------------------------------------------------------------------------

def mesh_data(mesh):
    """Positions, normals, uv0, bone indices/weights (or None) and one triangle array per submesh."""
    from UnityPy.helpers.MeshHelper import MeshHandler
    h = MeshHandler(mesh); h.process()
    n = h.m_VertexCount
    # channels can carry a padding component (half4 positions): keep the first 3 (2 for uv)
    cols = lambda v, k: np.array(v, np.float32).reshape(n, -1)[:, :k] if v else None
    pos, nrm, uv = cols(h.m_Vertices, 3), cols(h.m_Normals, 3), cols(h.m_UV0, 2)
    def four(v, dtype):
        """Per-vertex skin channels come with 1 to 4 components (weights as UNorm8 or floats): pad to 4."""
        if not v: return None
        a = np.array(v, dtype).reshape(len(pos), -1)
        return np.pad(a, ((0, 0), (0, 4 - a.shape[1]))) if a.shape[1] < 4 else a[:, :4]
    bi = four(h.m_BoneIndices, np.int64)
    bw = four(h.m_BoneWeights, np.float32)
    tris = [np.array(t, np.uint32).reshape(-1, 3) for t in h.get_triangles()]
    return {'pos': pos, 'normal': nrm, 'uv': uv, 'joints': bi, 'weights': bw, 'tris': tris}

ALBEDO = ('_Color', '_MainTex', '_BaseMap', '_Diffuse')

def albedo(mat):
    """The material's albedo texture (Texture2D), or None."""
    envs = dict((k, t) for k, t in mat.m_SavedProperties.m_TexEnvs)
    for k in ALBEDO:
        t = envs.get(k)
        if t is not None and t.m_Texture.m_PathID:
            tex = t.m_Texture.read()
            if tex.__class__.__name__ == 'Texture2D': return tex
    return None

def texture_image(mat):
    """The material's albedo texture as a PIL image, or None."""
    tex = albedo(mat)
    return tex.image if tex is not None else None

# --- animation clips -----------------------------------------------------------------------------------------------

def path_hash(path):
    return zlib.crc32(path.encode('utf-8')) & 0xffffffff

def _streamed(data, count):
    """Streamed clip -> per curve list of (time, coeffs[4])."""
    b = np.array(data, np.uint32).tobytes()
    keys = [[] for _ in range(count)]
    o = 0
    while o < len(b):
        t, n = struct.unpack_from('<fi', b, o); o += 8
        for _ in range(n):
            i, c0, c1, c2, c3 = struct.unpack_from('<i4f', b, o); o += 20
            if 0 <= i < count: keys[i].append((t, (c0, c1, c2, c3)))
    return keys

def _eval_streamed(keys, times):
    """Hermite segments: value(t) = ((c0*dt + c1)*dt + c2)*dt + c3 from the last key at or before t."""
    out = np.zeros(len(times), np.float64)
    if not keys: return out
    kt = np.array([k[0] for k in keys]); kc = np.array([k[1] for k in keys])
    # Unity writes a sentinel key at -inf / +inf; drop non-finite times
    ok = np.isfinite(kt); kt, kc = kt[ok], kc[ok]
    if not len(kt): return out
    i = np.clip(np.searchsorted(kt, times, side='right') - 1, 0, len(kt) - 1)
    dt = times - kt[i]
    c = kc[i]
    return ((c[:, 0] * dt + c[:, 1]) * dt + c[:, 2]) * dt + c[:, 3]

def sample_clip(clip, times):
    """{(path hash, attribute): array[len(times), dims]} for every binding of a Mecanim clip."""
    mc = clip.m_MuscleClip.m_Clip.data
    sc, dc, cc = mc.m_StreamedClip, mc.m_DenseClip, mc.m_ConstantClip
    ns, nd, nc = sc.curveCount, dc.m_CurveCount, len(cc.data)
    curves = np.zeros((ns + nd + nc, len(times)))
    if ns:
        for k, keys in enumerate(_streamed(sc.data, ns)): curves[k] = _eval_streamed(keys, times)
    if nd:
        arr = np.array(dc.m_SampleArray, np.float64).reshape(-1, nd)
        f = np.clip((times - dc.m_BeginTime) * dc.m_SampleRate, 0, len(arr) - 1)
        f0 = np.floor(f).astype(int); f1 = np.minimum(f0 + 1, len(arr) - 1); u = (f - f0)[:, None]
        curves[ns:ns + nd] = (arr[f0] * (1 - u) + arr[f1] * u).T
    if nc: curves[ns + nd:] = np.array(cc.data, np.float64)[:, None]
    out, k = {}, 0
    for b in clip.m_ClipBindingConstant.genericBindings:
        dims = {1: 3, 2: 4, 3: 3, 4: 3}.get(b.attribute, 1) if b.typeID == 4 else 1
        out[(b.path, b.attribute if b.typeID == 4 else ('float', b.typeID, b.attribute))] = curves[k:k + dims].T
        k += dims
    return out

def clip_length(clip):
    mc = clip.m_MuscleClip
    return mc.m_StopTime - mc.m_StartTime

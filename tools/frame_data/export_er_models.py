"""Exports what the Frame Data tab's 3D preview needs from an Elden Ring install: the player skeleton wearing one armor
set (glTF), weapon models (glTF), each move's animation and its hitboxes.

    python tools/frame_data/export_er_models.py "D:/SteamLibrary/steamapps/common/ELDEN RING"

Reads only (see import_er_game.py for the archive, param and TAE readers); writes frame-data/models/elden-ring/:

    models.json                 skeleton, armor set, every weapon (model file, behavior variation), body anchor
                                points, and per class its preview weapon and moves file
    moves/<class>.json          the class's moves (frames, preview weapon, hits) and hitbox shapes per variation
    armor-<set>.glb             skinned armor on the c0000 skeleton (Havok reference pose), low-res albedo textures
    weapon-<model>.glb          weapon model, origin at the grip; its hitbox anchor points in the node's extras
    anim/<move id>.bin          the move baked to the tab's frames (30 fps real time): packed bone rotations and
                                translations, root motion (format in frame-data/README.md, "3D preview")

Every class and weapon in frame-data/elden-ring.json is exported; EXPORT below picks the armor set and, where it
matters, the weapon a class previews when no weapon is picked. Moves are the ones the frame data lists for each class,
so their ids match the tab's.
"""
import io, json, math, os, re, struct, sys
import numpy as np
from PIL import Image
import import_er_game as G
import er_files as F
import er_havok as H
import er_flver as V

ROOT = G.ROOT
OUT = os.path.join(ROOT, 'frame-data', 'models', 'elden-ring')
G.REFS['EquipParamProtector.xml'] = 'https://raw.githubusercontent.com/soulsmods/Paramdex/master/ER/Defs/EquipParamProtector.xml'

EXPORT = {
    'armor': 'Raging Wolf',          # set name prefix: <name> Helm / Armor / Gauntlets / Greaves
    'preview': {'Katana': 'Moonveil'},  # class -> weapon shown when none is picked (default: the class's first)
}
TEX_SIZE = 1024                      # armor
WEAPON_TEX_SIZE = 256                # weapons are small in the preview, and there are 450 of them
LEFT_HAND = {'Light Bow', 'Bow', 'Greatbow'}  # classes whose moves hold the weapon in the left hand

# --- small math ----------------------------------------------------------------------------------------------------

def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
                     [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
                     [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]])

def trs(t, q, s):
    m = np.eye(4); m[:3, :3] = quat_mat(q) * np.array(s); m[:3, 3] = t
    return m

def euler_xzy(r):
    """FLVER node rotation (radians, applied X then Z then Y)."""
    rx, ry, rz = r
    X = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    Y = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    Z = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    return Y @ Z @ X

def flver_world(nodes):
    out = []
    for n in nodes:
        m = np.eye(4); m[:3, :3] = euler_xzy(n['r']) * np.array(n['s']); m[:3, 3] = n['t']
        out.append(out[n['parent']] @ m if 0 <= n['parent'] < len(out) else m)
    return out

# --- glTF ----------------------------------------------------------------------------------------------------------

class Gltf:
    def __init__(self):
        self.j = {'asset': {'version': '2.0', 'generator': 'export_er_models.py'}, 'scene': 0, 'scenes': [{'nodes': []}],
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

def dds_image(dds):
    """DDS -> PIL image. Pillow reads DX10 BC1 (formats 71/72) only through the legacy DXT1 header, so rewrite it."""
    if dds[84:88] == b'DX10' and struct.unpack_from('<I', dds, 128)[0] in (71, 72):
        hdr = bytearray(dds[:128])
        hdr[84:88] = b'DXT1'
        dds = bytes(hdr) + dds[148:]
    im = Image.open(io.BytesIO(dds)); im.load()
    return im

def encode_texture(im, size=TEX_SIZE):
    im = im.convert('RGBA')
    if max(im.size) > size:
        f = size / max(im.size)
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)
    alpha = im.getchannel('A')
    has_alpha = alpha.getextrema()[0] < 250
    buf = io.BytesIO()
    if has_alpha: im.save(buf, 'PNG', optimize=True); mime = 'image/png'
    else: im.convert('RGB').save(buf, 'JPEG', quality=85, optimize=True); mime = 'image/jpeg'
    return buf.getvalue(), mime, has_alpha

def part_texture_name(mtd):
    """'...P[BD_M_1350]_Metal.matxml' -> 'BD_M_1350'."""
    m = re.search(r'P\[([^\]]+)\]', mtd)
    return m.group(1) if m else None

def albedo_name(mat):
    """Materials whose matxml names no texture: the albedo map's path, '...\\WP_A_0912_a.tif' -> 'WP_A_0912'."""
    p = next((t['path'] for t in mat.get('textures', []) if 'albedo' in t['type'].lower() and t['path']), None)
    return re.sub(r'(_a)?\.\w+$', '', re.split(r'[\\/]', p)[-1], flags=re.I) if p else None

def add_mesh(g, flver, tpf, joint_of_node=None, hidden_masks=(), name='', tex_size=TEX_SIZE, quant=None):
    """FLVER meshes -> one glTF mesh (a primitive per FLVER mesh). joint_of_node maps FLVER node -> skin joint index;
    None exports rigid geometry. quant=(offset, scale) stores positions as int16 (pos = offset + q * scale)."""
    g.j.setdefault('extensionsUsed', ['KHR_mesh_quantization']); g.j['extensionsRequired'] = ['KHR_mesh_quantization']
    textures, prims = {}, []
    for mi, m in enumerate(flver['meshes']):
        mat = flver['materials'][m['material']]
        mask = re.match(r'#(\d+)#', mat['name'])
        if mask and int(mask.group(1)) in hidden_masks: continue
        if 'Collidable' in mat['name'] or len(m['triangles']) == 0: continue
        at = m['attrs']
        pos = at[(0, 0)].astype(np.float32)
        if quant is not None:  # int16 positions; the mesh's node scales them back (KHR_mesh_quantization)
            a = {'POSITION': g.accessor(np.round((pos - quant[0]) / quant[1]).astype(np.int16), 5122, 'VEC3', 34962, minmax=True)}
        else:
            a = {'POSITION': g.accessor(pos, 5126, 'VEC3', 34962, minmax=True)}
        if (3, 0) in at:
            n = at[(3, 0)][:, :3].astype(np.float32)
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
            a['NORMAL'] = g.accessor(np.round(n * 127).astype(np.int8), 5120, 'VEC3', 34962, normalized=True)
        if (5, 0) in at: a['TEXCOORD_0'] = g.accessor(at[(5, 0)].astype(np.float32), 5126, 'VEC2', 34962)
        if joint_of_node is not None:
            idx = at[(2, 0)].astype(np.int64)
            w = at[(1, 0)].astype(np.float32) if (1, 0) in at else np.zeros((len(pos), 4), np.float32)
            if m['bones']: idx = np.array(m['bones'])[idx]
            if not m['weighted'] or w.sum() == 0:  # rigid mesh: follows its node
                idx = np.zeros_like(idx); idx[:, 0] = m['node'] if m['node'] >= 0 else idx[:, 0]
                w = np.zeros_like(w); w[:, 0] = 1
            j = np.vectorize(lambda k: joint_of_node(int(k)))(idx).astype(np.uint16)
            w = w / np.maximum(w.sum(axis=1, keepdims=True), 1e-6)
            a['JOINTS_0'] = g.accessor(j, 5123, 'VEC4', 34962)
            a['WEIGHTS_0'] = g.accessor(w.astype(np.float32), 5126, 'VEC4', 34962)
        small = len(pos) < 65536
        tri = m['triangles'].astype(np.uint16 if small else np.uint32)
        p = {'attributes': a, 'indices': g.accessor(tri.reshape(-1), 5123 if small else 5125, 'SCALAR', 34963)}
        tex = part_texture_name(mat['mtd']) or albedo_name(mat)
        if tex not in textures:
            dds = tex and next((d for k, (d, _) in tpf.items() if k.lower() in (tex.lower() + '_a', tex.lower() + '_a_l')), None)
            textures[tex] = encode_texture(dds_image(dds), tex_size) if dds else None
        material = {'name': mat['name'], 'pbrMetallicRoughness': {'metallicFactor': 0.1, 'roughnessFactor': 0.8},
                    'doubleSided': True}
        if textures[tex]:
            data, mime, alpha = textures[tex]
            if 'tex' not in textures.setdefault(('idx', tex), {}):
                textures[('idx', tex)]['tex'] = g.image(data, mime)
            material['pbrMetallicRoughness']['baseColorTexture'] = {'index': textures[('idx', tex)]['tex']}
            if alpha: material.update(alphaMode='MASK', alphaCutoff=0.5)
        g.j['materials'].append(material)
        p['material'] = len(g.j['materials']) - 1
        prims.append(p)
    g.j['meshes'].append({'name': name, 'primitives': prims})
    return len(g.j['meshes']) - 1

# --- exporter ------------------------------------------------------------------------------------------------------

class Game:
    def __init__(self, game):
        self.game = game
        reg = F.read_bnd4(F.decrypt_regulation(open(os.path.join(game, 'regulation.bin'), 'rb').read()))
        self.weapons = F.read_param(reg['EquipParamWeapon.param'], G.fetch('EquipParamWeapon.xml'))
        self.protectors = F.read_param(reg['EquipParamProtector.param'], G.fetch('EquipParamProtector.xml'))
        self.behaviors = F.read_param(reg['BehaviorParam_PC.param'], G.fetch('BehaviorParam.xml'))
        self.attacks = F.read_param(reg['AtkParam_Pc.param'], G.fetch('AtkParam.xml'))
        self.arc = G.Archives(game)
        msg = F.read_bnd4(self.arc.read('/msg/engus/item_dlc02.msgbnd.dcx'))
        self.weapon_names, self.protector_names = {}, {}
        for f, d in msg.items():
            if re.match(r'WeaponName(_dlc0\d)?\.fmg', f): self.weapon_names.update(F.read_fmg(d))
            if re.match(r'ProtectorName(_dlc0\d)?\.fmg', f): self.protector_names.update(F.read_fmg(d))
        anibnd = F.read_bnd4(self.arc.read('/chr/c0000.anibnd.dcx'))
        self.taes, self.hkx_src = {}, {}
        for f, d in anibnd.items():
            if f.endswith('.tae'):
                sec, anims = F.read_tae(d); self.taes[sec] = anims
                for aid, src in F.read_tae_hkx(d).items(): self.hkx_src[(sec, aid)] = src
        self.bones, self.parents, self.pose = H.skeleton(H.read_tagfile(anibnd['Skeleton.hkx']))
        self.bone_index = {n: i for i, n in enumerate(self.bones)}
        self.world = []
        for i, (t, q, s) in enumerate(self.pose):
            m = trs(t, q, s)
            self.world.append(self.world[self.parents[i]] @ m if self.parents[i] >= 0 else m)
        self.body = V.read_flver(F.read_bnd4(self.arc.read('/chr/c0000.chrbnd.dcx'))['c0000.flver'])
        self._bundles = {}

    def parts(self, name, low=True):
        """'bd_m_1350' -> {file name: bytes}; low=True prefers the _l bundle with low-res textures."""
        for n in ([name + '_l'] if low else []) + [name]:
            p = f'/parts/{n}.partsbnd.dcx'
            if F.path_hash(p) in self.arc.index: return F.read_bnd4(self.arc.read(p))
        raise KeyError(name)

    def hkx(self, sec, aid):
        """Animation file for TAE section + anim id, from the split .anibnd bundles (the DLCs' in their own two)."""
        name = f'a{sec:03d}_{aid:06d}.hkx'
        group = 'a00_hi' if sec == 0 else f'a{sec // 10}x' if sec < 60 else 'a6x' if sec == 69 else 'a9x'
        for group in (group, 'dlc02', 'dlc01'):
            if group not in self._bundles:
                b = F.read_bnd4(self.arc.read(f'/chr/c0000_{group}.anibnd.dcx'))
                comp = next(v for k, v in b.items() if k.endswith('.compendium'))
                self._bundles[group] = (b, H.read_compendium(comp))
            b, comp = self._bundles[group]
            if name in b: return H.read_tagfile(b[name], comp)
        return None

    def find_hkx(self, sec, aid, depth=0):
        """The motion an animation plays: its own .hkx, else the one its TAE header borrows (ImportsHKX), else the one
        of the animation it imports wholesale."""
        root = self.hkx(sec, aid)
        if root is not None or depth > 4: return root
        for full in (self.hkx_src.get((sec, aid)), (self.taes.get(sec, {}).get(aid) or (None, None))[1]):
            if full:
                root = self.find_hkx(full // 1000000, full % 1000000, depth + 1)
                if root is not None: return root
        return None

    def skeleton_joint(self, flver):
        """FLVER node index -> skeleton bone index (nodes missing from the skeleton follow their nearest ancestor)."""
        nodes = flver['nodes']
        def f(i):
            seen = 0
            while i >= 0 and seen < 64:
                n = nodes[i]['name']
                if n in self.bone_index: return self.bone_index[n]
                i = nodes[i]['parent']; seen += 1
            return self.bone_index.get('Spine1', 0)
        cache = {}
        return lambda i: cache.setdefault(i, f(i))

    # --- armor

    def armor(self, set_name):
        pieces = {}
        for pid, n in self.protector_names.items():
            if not n or pid not in self.protectors: continue
            for part, word in (('hd', 'Helm'), ('bd', 'Armor'), ('am', 'Gauntlets'), ('lg', 'Greaves')):
                if n == f'{set_name} {word}': pieces[part] = (pid, n)
        hidden = set()
        for pid, _ in pieces.values():
            hidden |= {int(k[-2:]) for k, v in self.protectors[pid].items() if 'nvisibleFlag' in k and v}
        g = Gltf()
        # skeleton nodes in Havok order, reference pose as rest pose
        first = len(g.j['nodes'])
        for i, (t, q, s) in enumerate(self.pose):
            g.node(name=self.bones[i], translation=list(t), rotation=list(q), scale=list(s))
        for i, p in enumerate(self.parents):
            if p >= 0: g.j['nodes'][first + p].setdefault('children', []).append(first + i)
        roots = [first + i for i, p in enumerate(self.parents) if p < 0]
        ibm = np.array([np.linalg.inv(w).T.reshape(-1) for w in self.world], np.float32)
        g.j['skins'] = [{'joints': list(range(first, first + len(self.bones))), 'skeleton': roots[0],
                         'inverseBindMatrices': g.accessor(ibm, 5126, 'MAT4')}]
        meshes = []
        for part, (pid, n) in sorted(pieces.items()):
            model = f"{part}_m_{self.protectors[pid]['equipModelId']:04d}"
            files = self.parts(model)
            fl = next(v for k, v in files.items() if k.lower().endswith('.flver'))
            tpf = V.read_tpf(next(v for k, v in files.items() if k.lower().endswith('.tpf')))
            flver = V.read_flver(fl)
            mi = add_mesh(g, flver, tpf, self.skeleton_joint(flver), hidden, model)
            meshes.append(g.node(name=model, mesh=mi, skin=0))
        g.j['scenes'][0]['nodes'] = roots + meshes
        return g.glb(), {'name': f'{set_name} Set', 'pieces': [n for _, n in sorted(pieces.values())]}

    # --- weapons

    def weapon(self, name):
        wid = next(k for k, v in self.weapon_names.items() if v == name and k in self.weapons)
        w = self.weapons[wid]
        model = f"wp_a_{w['equipModelId']:04d}"
        files = self.parts(model)
        tpf = V.read_tpf(next(v for k, v in files.items() if k.lower().endswith('.tpf')))
        main = next(v for k, v in files.items() if re.fullmatch(rf'{model}(_l)?\.flver', k.lower()))
        flver = V.read_flver(main)
        wn = flver_world(flver['nodes'])
        dummies = {}
        for d in flver['dummies']:
            p = np.array([*d['pos'], 1.0])
            if 0 <= d['parent'] < len(wn): p = wn[d['parent']] @ p
            dummies.setdefault(str(d['id']), [round(float(v), 4) for v in p[:3]])
        g = Gltf()
        pts = np.concatenate([m['attrs'][(0, 0)][:, :3] for m in flver['meshes'] if len(m['triangles'])])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        mid, scale = (lo + hi) / 2, float(max(hi - lo)) / 65000 or 1.0
        mi = add_mesh(g, flver, tpf, None, (), model, WEAPON_TEX_SIZE, (mid, scale))
        # the mesh node undoes the int16 quantization; the root stays in model space, where the hitbox anchor points
        # are (three.js puts extras in userData)
        mesh = g.node(name=model + '_mesh', mesh=mi, translation=[float(v) for v in mid], scale=[scale] * 3)
        g.j['scenes'][0]['nodes'] = [g.node(name=model, children=[mesh], extras={'dummies': dummies})]
        return g.glb(), {'id': wid, 'name': name, 'model': model, 'variation': w['behaviorVariationId']}

    def body_dummies(self):
        """c0000 dummy points -> {id: [bone name, x, y, z in that bone's space]} from the Havok reference pose."""
        nodes, out = self.body['nodes'], {}
        fw = flver_world(nodes)
        for d in self.body['dummies']:
            attach = d['attach'] if d['attach'] >= 0 else d['parent']
            ref = d['parent']
            if not (0 <= attach < len(nodes)): continue
            an, rn = nodes[attach]['name'], nodes[ref]['name'] if 0 <= ref < len(nodes) else None
            if an not in self.bone_index: continue
            rw = self.world[self.bone_index[rn]] if rn in self.bone_index else (fw[ref] if rn else np.eye(4))
            p = rw @ np.array([*d['pos'], 1.0])
            local = np.linalg.inv(self.world[self.bone_index[an]]) @ p
            out.setdefault(str(d['id']), [an] + [round(float(v), 4) for v in local[:3]])
        return out

    # --- moves

    def move(self, move_id):
        """-> (baked animation bytes, frames, hits), or (None, 0, None) when the game has no motion for it. Hits are
        {start, end, judge[, hand]}: tab frames, the behavior judge id, and 'R'/'L' when the event names the hand."""
        sec, aid = int(move_id[1:4]), int(move_id[5:])
        evs, imp = self.taes[sec][aid]
        if imp is not None and imp // 1000000 in self.taes and imp % 1000000 in self.taes[imp // 1000000]:
            evs = evs + self.taes[imp // 1000000][imp % 1000000][0]
        root = self.find_hkx(sec, aid)
        if root is None and aid % 1000 // 100 == 6 and aid % 100 < 40:
            # War Cry / Barbaric Roar heavies play the plain charged heavy animations (0305x0 / 0305x5)
            root = self.find_hkx(sec, aid - 100 - (20 if aid % 100 >= 20 else 0))
        if root is None: return None, 0, None
        a = H.animation(root)
        frame, clock = F.frame_clock(evs, G.FPS), F.real_clock(evs)
        # tab frame -> animation time: invert the speed-change clock on a fine grid
        dur = a['duration']
        ts = np.linspace(0, dur, max(2, int(dur * G.FPS * 8) + 1))
        real = np.array([clock(t) for t in ts]) * G.FPS
        total = max(1, int(math.ceil(real[-1] - 1e-6)))
        times = np.interp(np.arange(total), real, ts)          # the pose at tab frame f is the animation at times[f-1]
        hits = []
        for t, s, e, p in evs:
            if t not in (1, 304) or e >= 1e6 or frame(e) <= frame(s): continue
            judge = struct.unpack_from('<i', p, 8 if t == 1 else 4)[0]
            h = {'start': frame(s) + 1, 'end': frame(e), 'judge': judge}
            if t == 1 and p[13] in (1, 2): h['hand'] = 'RL'[p[13] - 1]   # powerstance: which weapon swings
            hits.append(h)
        return bake(a, times), total, hits

    def hit_shapes(self, judge, variation):
        if judge >= 1000: return []
        v = variation
        b = self.behaviors.get(100000000 + v * 1000 + judge) or self.behaviors.get(100000000 + v // 100 * 100 * 1000 + judge)
        if not b or b['refType'] != 0 or b['refId'] not in self.attacks: return []
        atk = self.attacks[b['refId']]
        shapes = []
        for i in range(16):
            a, c, r = atk.get(f'hit{i}_DmyPoly1', -1), atk.get(f'hit{i}_DmyPoly2', -1), atk.get(f'hit{i}_Radius', 0)
            if a is None or a < 0 or not r: continue
            shapes.append({'a': a, 'b': c if c is not None and c >= 0 else None, 'r': round(float(r), 4),
                           'type': atk.get(f'hit{i}_hitType', 0)})
        return shapes

# --- baked animation -----------------------------------------------------------------------------------------------
# One pose per tab frame, so the page never resamples. Little-endian, unaligned:
#   'FDA2', u16 bones, u16 frames, u8 has root motion, u8 0
#   u16[bones]  skeleton index (models.json skeleton.bones)
#   u8[bones]   flags: 1 rotation changes per frame, 2 translation changes per frame (else one value for the move)
#   per bone    rotation u32 x (frames or 1): smallest-three quaternion, the dropped component's index in the top 2
#               bits, then three 10-bit components over [-1/sqrt2, 1/sqrt2]; translation i16 x 3 x (frames or 1), mm
#   root motion f32 x 3 x frames (metres), if present

QS = 1023 / math.sqrt(2)
OTHER = np.array([[j for j in range(4) if j != k] for k in range(4)])

def pack_quats(q):
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    i = np.argmax(np.abs(q), axis=-1)
    q = q * np.where(np.take_along_axis(q, i[:, None], -1) < 0, -1, 1)
    c = np.take_along_axis(q, OTHER[i], -1)
    v = np.clip(np.round((c + 1 / math.sqrt(2)) * QS), 0, 1023).astype(np.uint32)
    return (i.astype(np.uint32) << 30) | (v[:, 0] << 20) | (v[:, 1] << 10) | v[:, 2]

def bake(a, times):
    t = np.clip(times * a['fps'], 0, a['frames'] - 1)
    i0 = np.floor(t).astype(int); i1 = np.minimum(i0 + 1, a['frames'] - 1); u = (t - i0)[:, None]
    bones = sorted(a['bones'])
    flags, body = [], []
    for b in bones:
        T, R, _ = a['bones'][b]
        r = R[i0] * (1 - u) + R[i1] * u                     # frames share a hemisphere, so nlerp is enough
        p = T[i0] * (1 - u) + T[i1] * u
        f = (1 if np.ptp(r, axis=0).max() > 2e-4 else 0) | (2 if np.ptp(p, axis=0).max() > 1e-4 else 0)
        flags.append(f)
        body.append(pack_quats(r if f & 1 else r[:1]).astype('<u4').tobytes())
        mm = np.round((p if f & 2 else p[:1]) * 1000)
        if np.abs(mm).max() > 32767: print('    translation out of range on bone', b)
        body.append(np.clip(mm, -32768, 32767).astype('<i2').tobytes())
    root = None
    if a['root_motion'] is not None and len(a['root_motion']):
        rm = a['root_motion']; k = len(rm)
        rt = np.clip(t / max(a['frames'] - 1, 1) * (k - 1), 0, k - 1)
        r0 = np.floor(rt).astype(int); r1 = np.minimum(r0 + 1, k - 1); ru = (rt - r0)[:, None]
        root = (rm[r0, :3] * (1 - ru) + rm[r1, :3] * ru).astype('<f4')
    out = b'FDA2' + struct.pack('<HHBB', len(bones), len(times), root is not None, 0)
    out += np.array(bones, '<u2').tobytes() + bytes(flags) + b''.join(body)
    return out + (root.tobytes() if root is not None else b'')

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def main(game_dir, only=None):
    gm = Game(game_dir)
    fd = json.load(open(os.path.join(ROOT, 'frame-data', 'elden-ring.json'), encoding='utf-8'))
    for d in ('anim', 'moves'): os.makedirs(os.path.join(OUT, d), exist_ok=True)
    glb, armor = gm.armor(EXPORT['armor'])
    armor['file'] = f"armor-{slug(EXPORT['armor'])}.glb"
    open(os.path.join(OUT, armor['file']), 'wb').write(glb)
    print('armor', armor['file'], len(glb) // 1024, 'KB')
    manifest = {'schema': 'frame-data-models/2', 'game': 'elden-ring', 'version': fd['game']['version'],
                'skeleton': {'weaponBone': 'R_Weapon', 'leftWeaponBone': 'L_Weapon', 'rootBone': 'Master', 'bones': gm.bones},
                'armor': armor, 'body': gm.body_dummies(), 'weapons': {}, 'classes': {}}
    classes = [c for c in fd['classes'] if not only or c['id'] in only]
    files, wsize = {}, 0                                        # weapons sharing a model share its file
    for c in classes:
        for name in c['weapons']:
            wid = next(k for k, v in gm.weapon_names.items() if v == name and k in gm.weapons)
            model = f"wp_a_{gm.weapons[wid]['equipModelId']:04d}"
            if model not in files:
                glb, _ = gm.weapon(name)
                files[model] = f'weapon-{model}.glb'
                open(os.path.join(OUT, files[model]), 'wb').write(glb)
                wsize += len(glb)
            manifest['weapons'][name] = {'id': wid, 'model': model, 'file': files[model],
                                         'variation': gm.weapons[wid]['behaviorVariationId']}
    print(f'weapons: {len(files)} models, {wsize / 1e6:.1f} MB')
    baked, asize = {}, 0                                        # move id -> (frames, hits); a few ids recur across classes
    for c in classes:
        cls, names = c['id'], c['weapons']
        preferred = EXPORT['preview'].get(cls, names[0])
        moves, attacks, size, total = {}, {}, 0, 0
        for m in fd['moves']:
            if m['class'] != cls: continue
            total += 1
            if m['id'] not in baked:
                data, frames, hits = gm.move(m['id'])
                if data is None: print('  no animation for', cls, m['id']); baked[m['id']] = None; continue
                open(os.path.join(OUT, 'anim', f"{m['id']}.bin"), 'wb').write(data)
                size += len(data); baked[m['id']] = (frames, hits)
            if baked[m['id']] is None: continue
            frames, hits = baked[m['id']]
            users = [names[i] for i in m['weapons']] or names
            moves[m['id']] = {'frames': frames, 'weapon': preferred if preferred in users else users[0], 'hits': hits}
            for wn in users:
                v = str(manifest['weapons'][wn]['variation'])
                for h in hits:
                    j = str(h['judge'])
                    if j not in attacks.setdefault(v, {}): attacks[v][j] = gm.hit_shapes(h['judge'], int(v))
        attacks = {v: {j: s for j, s in a.items() if s} for v, a in attacks.items()}
        file = f'moves/{slug(cls)}.json'
        with open(os.path.join(OUT, file), 'w', encoding='utf-8') as f:
            json.dump({'class': cls, 'moves': moves, 'attacks': {v: a for v, a in attacks.items() if a}}, f,
                      ensure_ascii=False, separators=(',', ':'))
        manifest['classes'][cls] = {'file': file, 'weapon': preferred, **({'hand': 'L'} if cls in LEFT_HAND else {})}
        asize += size
        print(f'  {cls}: {len(moves)} of {total} moves, {size // 1024} KB of animation')
    with open(os.path.join(OUT, 'models.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(',', ':'))
    print(f'animation: {asize / 1e6:.1f} MB')

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(G.game_dir(sys.argv[1]), set(sys.argv[2:]) or None)

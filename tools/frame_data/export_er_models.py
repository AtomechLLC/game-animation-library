"""Exports what the Frame Data tab's 3D preview needs from an Elden Ring install: the player skeleton wearing one armor
set (glTF), weapon models (glTF), each move's animation and its hitboxes.

    python tools/frame_data/export_er_models.py "D:/SteamLibrary/steamapps/common/ELDEN RING"

Reads only (see import_er_game.py for the archive, param and TAE readers); writes frame-data/models/elden-ring/:

    models.json                 armor set, weapons (model, hitbox anchor points), body anchor points, moves
    armor-<set>.glb             skinned armor on the c0000 skeleton (Havok reference pose), low-res albedo textures
    weapon-<name>.glb           weapon model, origin at the grip (attached to the R_Weapon bone)
    anim/<move id>.json         local bone rotations/translations per frame, root motion, frame -> animation time

Which weapons, classes and armor set are exported is set in EXPORT below. Moves are the ones frame-data/elden-ring.json
lists for each class, so their ids match the tab's.
"""
import base64, io, json, math, os, re, struct, sys
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
    'classes': {'Katana': 'Moonveil'},  # class -> weapon shown in the preview
}
TEX_SIZE = 1024

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

    def view(self, data, target=None):
        while len(self.bin) % 4: self.bin.append(0)
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target: v['target'] = target
        self.bin += data
        self.j['bufferViews'].append(v)
        return len(self.j['bufferViews']) - 1

    def accessor(self, arr, ctype, kind, target=None, normalized=False, minmax=False):
        arr = np.ascontiguousarray(arr)
        a = {'bufferView': self.view(arr.tobytes(), target), 'componentType': ctype, 'count': len(arr), 'type': kind}
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

def encode_texture(im):
    im = im.convert('RGBA')
    if max(im.size) > TEX_SIZE:
        f = TEX_SIZE / max(im.size)
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

def add_mesh(g, flver, tpf, joint_of_node=None, hidden_masks=(), name=''):
    """FLVER meshes -> one glTF mesh (a primitive per FLVER mesh). joint_of_node maps FLVER node -> skin joint index;
    None exports rigid geometry."""
    textures, prims = {}, []
    for mi, m in enumerate(flver['meshes']):
        mat = flver['materials'][m['material']]
        mask = re.match(r'#(\d+)#', mat['name'])
        if mask and int(mask.group(1)) in hidden_masks: continue
        if 'Collidable' in mat['name'] or len(m['triangles']) == 0: continue
        at = m['attrs']
        pos = at[(0, 0)].astype(np.float32)
        a = {'POSITION': g.accessor(pos, 5126, 'VEC3', 34962, minmax=True)}
        if (3, 0) in at:
            n = at[(3, 0)][:, :3].astype(np.float32)
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
            a['NORMAL'] = g.accessor(n, 5126, 'VEC3', 34962)
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
        tri = m['triangles'].astype(np.uint32)
        p = {'attributes': a, 'indices': g.accessor(tri.reshape(-1), 5125, 'SCALAR', 34963)}
        tex = part_texture_name(mat['mtd'])
        key = (tex, mat['name'])
        if tex not in textures:
            dds = next((d for k, (d, _) in tpf.items() if k.lower() in (tex.lower() + '_a', tex.lower() + '_a_l')), None)
            textures[tex] = encode_texture(dds_image(dds)) if dds else None
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
        self.taes = {}
        for f, d in anibnd.items():
            if f.endswith('.tae'):
                sec, anims = F.read_tae(d); self.taes[sec] = anims
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
        """Animation file for TAE section + anim id, from the split .anibnd bundles."""
        name = f'a{sec:03d}_{aid:06d}.hkx'
        group = 'a00_hi' if sec == 0 else f'a{sec // 10}x' if sec < 60 else 'a6x' if sec == 69 else 'a9x'
        if group not in self._bundles:
            b = F.read_bnd4(self.arc.read(f'/chr/c0000_{group}.anibnd.dcx'))
            comp = next(v for k, v in b.items() if k.endswith('.compendium'))
            self._bundles[group] = (b, H.read_compendium(comp))
        b, comp = self._bundles[group]
        return H.read_tagfile(b[name], comp) if name in b else None

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
        g = Gltf()
        mi = add_mesh(g, flver, tpf, None, (), model)
        g.j['scenes'][0]['nodes'] = [g.node(name=model, mesh=mi)]
        wn = flver_world(flver['nodes'])
        dummies = {}
        for d in flver['dummies']:
            p = np.array([*d['pos'], 1.0])
            if 0 <= d['parent'] < len(wn): p = wn[d['parent']] @ p
            dummies.setdefault(str(d['id']), [round(float(v), 4) for v in p[:3]])
        return g.glb(), {'id': wid, 'name': name, 'model': model, 'dummies': dummies, 'behavior': w['behaviorVariationId']}

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

    def move(self, move_id, weapon):
        sec, aid = int(move_id[1:4]), int(move_id[5:])
        evs, imp = self.taes[sec][aid]
        if imp is not None and imp // 1000000 in self.taes and imp % 1000000 in self.taes[imp // 1000000]:
            evs = evs + self.taes[imp // 1000000][imp % 1000000][0]
        root = self.hkx(sec, aid)
        if root is None and imp is not None: root = self.hkx(imp // 1000000, imp % 1000000)
        if root is None and aid % 1000 // 100 == 6 and aid % 100 < 40:
            # War Cry / Barbaric Roar heavies play the plain charged heavy animations (0305x0 / 0305x5)
            root = self.hkx(sec, aid - 100 - (20 if aid % 100 >= 20 else 0))
        if root is None: return None, None
        a = H.animation(root)
        frame, clock = F.frame_clock(evs, G.FPS), F.real_clock(evs)
        # real frame -> animation time: invert the speed-change clock on a fine grid
        dur = a['duration']
        ts = np.linspace(0, dur, max(2, int(dur * G.FPS * 8) + 1))
        real = np.array([clock(t) for t in ts]) * G.FPS
        total = int(math.ceil(real[-1] - 1e-6))
        times = np.interp(np.arange(total + 1), real, ts)
        hits = []
        for t, s, e, p in evs:
            if t not in (1, 304) or e >= 1e6 or frame(e) <= frame(s): continue
            judge = struct.unpack_from('<i', p, 8 if t == 1 else 4)[0]
            shapes = self.hit_shapes(judge, weapon)
            hits.append({'start': frame(s) + 1, 'end': frame(e), 'judge': judge, 'shapes': shapes})
        bones = sorted(a['bones'])
        n = a['frames']
        R = np.stack([a['bones'][b][1] for b in bones], axis=1)            # frames x bones x 4
        T = np.stack([a['bones'][b][0] for b in bones], axis=1)            # frames x bones x 3
        moving = [k for k in range(len(bones)) if np.ptp(T[:, k], axis=0).max() > 1e-4]
        anim = {
            'id': move_id, 'fps': a['fps'], 'frames': n, 'duration': round(float(dur), 5),
            'bones': [self.bones[b] for b in bones],
            'rot': b64(np.round(R * 32767).astype('<i2')),
            'pos': {self.bones[bones[k]]: b64(T[:, k].astype('<f4')) for k in moving},
            'rest': {self.bones[bones[k]]: [round(float(v), 5) for v in T[0, k]] for k in range(len(bones)) if k not in moving},
            'root': b64(a['root_motion'].astype('<f4')) if a['root_motion'] is not None else None,
            'time': [round(float(v), 4) for v in times],
        }
        return anim, hits

    def hit_shapes(self, judge, weapon):
        if judge >= 1000: return []
        v = weapon['behavior']
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

def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode('ascii')

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def main(game_dir):
    gm = Game(game_dir)
    fd = json.load(open(os.path.join(ROOT, 'frame-data', 'elden-ring.json'), encoding='utf-8'))
    os.makedirs(os.path.join(OUT, 'anim'), exist_ok=True)
    glb, armor = gm.armor(EXPORT['armor'])
    armor['file'] = f"armor-{slug(EXPORT['armor'])}.glb"
    open(os.path.join(OUT, armor['file']), 'wb').write(glb)
    print('armor', armor['file'], len(glb) // 1024, 'KB')
    manifest = {'schema': 'frame-data-models/1', 'game': 'elden-ring', 'version': fd['game']['version'],
                'skeleton': {'weaponBone': 'R_Weapon', 'rootBone': 'Master'},
                'armor': armor, 'body': gm.body_dummies(), 'weapons': {}, 'classes': {}, 'moves': {}}
    weapons = {}
    def weapon(name):
        if name not in weapons:
            glb, w = gm.weapon(name)
            w['file'] = f'weapon-{slug(name)}.glb'
            open(os.path.join(OUT, w['file']), 'wb').write(glb)
            print('weapon', w['file'], len(glb) // 1024, 'KB')
            weapons[name] = w
            manifest['weapons'][name] = {k: v for k, v in w.items() if k != 'behavior'}
        return weapons[name]
    for cls, preferred in EXPORT['classes'].items():
        manifest['classes'][cls] = preferred
        names = next(c['weapons'] for c in fd['classes'] if c['id'] == cls)
        size, count = 0, 0
        for m in fd['moves']:
            if m['class'] != cls: continue
            # the class's preview weapon when it plays this move, else the first weapon that does
            users = [names[i] for i in m['weapons']] or names
            w = weapon(preferred if preferred in users else users[0])
            anim, hits = gm.move(m['id'], w)
            if anim is None: print('  no animation for', m['id']); continue
            data = json.dumps(anim, separators=(',', ':'))
            open(os.path.join(OUT, 'anim', f"{m['id']}.json"), 'w').write(data)
            size += len(data); count += 1
            manifest['moves'][f"{cls}|{m['id']}"] = {'weapon': w['name'], 'hits': hits, 'frames': len(anim['time']) - 1}
        print(' ', cls, count, 'moves', size // 1024, 'KB of animation')
    with open(os.path.join(OUT, 'models.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(',', ':'))

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(G.game_dir(sys.argv[1]))

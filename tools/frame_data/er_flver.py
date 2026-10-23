"""Reads Elden Ring FLVER2 models and TPF texture packs. Read-only, numpy only.

    read_flver(data) -> dict(nodes, dummies, materials, meshes)
    read_tpf(data)   -> {texture name: (dds bytes, format byte)}

Layout follows SoulsFormats (https://github.com/soulsmods/SoulsFormats): Formats/FLVER/FLVER2, Formats/TPF.
"""
import struct
import numpy as np

def _str(data, off, unicode):
    if unicode:
        end = off
        while data[end:end+2] != b'\0\0': end += 2
        return data[off:end].decode('utf-16-le')
    return data[off:data.index(b'\0', off)].decode('shift_jis')

# LayoutType -> (byte size, numpy dtype, components)
_LTYPES = {0: (4, '<f4', 1), 1: (8, '<f4', 2), 2: (12, '<f4', 3), 3: (16, '<f4', 4), 16: (4, 'u1', 4), 17: (4, 'u1', 4),
           18: (4, 'i1', 4), 19: (4, 'u1', 4), 20: (4, 'i1', 4), 21: (4, '<i2', 2), 22: (8, '<i2', 4), 23: (4, '<u2', 2),
           24: (8, '<u2', 4), 26: (8, '<i2', 4), 45: (4, '<i2', 2), 46: (8, '<i2', 4), 47: (4, 'u1', 4)}
POSITION, WEIGHTS, INDICES, NORMAL, UV, TANGENT, BITANGENT, COLOR = 0, 1, 2, 3, 5, 6, 7, 10

def _decode(sem, typ, raw, uv_factor=2048.0):
    """Raw member values -> floats in the meaning of the semantic (list of arrays: UV members can hold two UVs)."""
    raw = raw.astype(np.float64)
    if sem == POSITION: return [raw[:, :3]]
    if sem == WEIGHTS:
        if typ == 16: return [raw / 127.0]
        if typ == 19: return [raw / 255.0]
        if typ == 22: return [raw / 65535.0]
        if typ == 26: return [raw / 32767.0]
        return [raw]
    if sem == INDICES: return [raw]
    if sem in (NORMAL, TANGENT, BITANGENT):
        if typ in (2, 3): return [raw]
        if typ in (16, 17, 19, 47): return [(raw - 127.0) / 127.0]
        if typ == 26: return [raw / 32767.0]
        if typ == 18: return [raw[:, ::-1] / 127.0]
        if typ == 46: return [(raw.astype(np.int64) & 0xFFFF).astype(np.float64) - 32767.0 / 32767.0]
        return [raw]
    if sem == UV:
        if typ in (1, 2): return [raw[:, :2]]
        if typ == 3: return [raw[:, :2], raw[:, 2:4]]
        if typ == 19: return [raw[:, :2] / 255.0, raw[:, 2:4] / 255.0]
        if typ in (22, 46): return [raw[:, :2] / uv_factor, raw[:, 2:4] / uv_factor]
        return [raw[:, :2] / uv_factor]
    if sem == COLOR:
        return [raw / 255.0] if typ in (16, 19) else [raw]
    return [raw]

def read_flver(data):
    assert data[:6] == b'FLVER\0' and data[6:8] == b'L\0', data[:8]
    version, doff, _, nd, nm, nb, nmesh, nvb = struct.unpack_from('<9i', data, 8)[:8]
    bbmin = struct.unpack_from('<3f', data, 0x28); bbmax = struct.unpack_from('<3f', data, 0x34)
    idx_size, unicode = data[0x48], data[0x49]
    nfs, nlay, ntex = struct.unpack_from('<3i', data, 0x50)
    p = 0x80
    dummies = []
    for _ in range(nd):
        pos = struct.unpack_from('<3f', data, p); fwd = struct.unpack_from('<3f', data, p + 16)
        ref, parent = struct.unpack_from('<hh', data, p + 28)
        up = struct.unpack_from('<3f', data, p + 32)
        attach, = struct.unpack_from('<h', data, p + 44)
        dummies.append({'id': ref, 'pos': pos, 'forward': fwd, 'up': up, 'parent': parent, 'attach': attach})
        p += 64
    materials = []
    for _ in range(nm):
        no, mo, tc, ti = struct.unpack_from('<4i', data, p)
        materials.append({'name': _str(data, no, unicode), 'mtd': _str(data, mo, unicode), 'tex': (ti, tc)})
        p += 32
    nodes = []
    for _ in range(nb):
        t = struct.unpack_from('<3f', data, p); no, = struct.unpack_from('<i', data, p + 12)
        r = struct.unpack_from('<3f', data, p + 16); parent, = struct.unpack_from('<h', data, p + 28)
        s = struct.unpack_from('<3f', data, p + 32)
        nodes.append({'name': _str(data, no, unicode), 't': t, 'r': r, 's': s, 'parent': parent})
        p += 128
    meshes = []
    for _ in range(nmesh):
        weights, = struct.unpack_from('<?', data, p)
        mat, = struct.unpack_from('<i', data, p + 4)
        node, bc, _, bo, fc, fo, vc, vo = struct.unpack_from('<8i', data, p + 16)
        meshes.append({'material': mat, 'node': node, 'weighted': weights,
                       'bones': list(struct.unpack_from(f'<{bc}i', data, bo)) if bc else [],
                       'facesets': list(struct.unpack_from(f'<{fc}i', data, fo)),
                       'buffers': list(struct.unpack_from(f'<{vc}i', data, vo))})
        p += 48
    facesets = []
    for _ in range(nfs):
        flags, strip, cull, _, n, io = struct.unpack_from('<I??hii', data, p)
        isz, = struct.unpack_from('<i', data, p + 24)
        isz = isz or idx_size
        dt = '<u2' if isz == 16 else '<u4'
        facesets.append({'flags': flags, 'strip': strip, 'indices': np.frombuffer(data, dt, n, doff + io).astype(np.int64)})
        p += 32
    buffers = []
    for _ in range(nvb):
        bi, li, vs, vcount, _, _, _, bo = struct.unpack_from('<8i', data, p)
        buffers.append((li, vs, vcount, bo)); p += 32
    layouts = []
    for _ in range(nlay):
        mc, _, _, mo = struct.unpack_from('<4i', data, p); p += 16
        members, off = [], 0
        for k in range(mc):
            _, so, typ, sem, si = struct.unpack_from('<5i', data, mo + k * 20)
            members.append((so, typ, sem, si)); off = so + _LTYPES[typ][0]
        layouts.append(members)
    textures = []
    for _ in range(ntex):
        po, to = struct.unpack_from('<ii', data, p)
        scale = struct.unpack_from('<ff', data, p + 8)
        textures.append({'path': _str(data, po, unicode), 'type': _str(data, to, unicode), 'scale': scale}); p += 32
    for m in materials:
        ti, tc = m.pop('tex'); m['textures'] = textures[ti:ti + tc]
    uv_factor = 2048.0 if version >= 0x2000E else 1024.0
    for m in meshes:
        attrs = {}
        for b in m.pop('buffers'):
            li, vs, vcount, bo = buffers[b]
            for so, typ, sem, si in layouts[li]:
                size, dt, comps = _LTYPES[typ]
                arr = np.ndarray((vcount, comps), dtype=dt, buffer=data, offset=doff + bo + so, strides=(vs, np.dtype(dt).itemsize))
                for j, v in enumerate(_decode(sem, typ, arr, uv_factor)):
                    key = (sem, si + j) if sem == UV else (sem, si)
                    attrs.setdefault(key, v)
        m['attrs'] = attrs
        fs = [facesets[i] for i in m.pop('facesets')]
        main = next((f for f in fs if not f['flags'] & 0xFF000000), fs[0] if fs else None)
        tris = np.zeros((0, 3), np.int64)
        if main is not None:
            idx = main['indices']
            if main['strip']:
                out = []
                for k in range(len(idx) - 2):
                    a, b, c = idx[k], idx[k + 1], idx[k + 2]
                    if a == b or b == c or a == c or 0xFFFF in (a, b, c): continue
                    out.append((a, b, c) if k % 2 == 0 else (b, a, c))
                tris = np.array(out, np.int64).reshape(-1, 3)
            else:
                tris = idx.reshape(-1, 3)
        m['triangles'] = tris
    return {'version': version, 'bbox': (bbmin, bbmax), 'nodes': nodes, 'dummies': dummies,
            'materials': materials, 'meshes': meshes}

def read_tpf(data):
    """TPF (PC) -> {texture name: (dds bytes, format byte)}."""
    assert data[:4] == b'TPF\0', data[:4]
    n, = struct.unpack_from('<i', data, 8)
    enc = data[0xE]
    out = {}
    p = 0x10
    for _ in range(n):
        off, size = struct.unpack_from('<Ii', data, p)
        fmt = data[p + 8]
        no, has_floats = struct.unpack_from('<Ii', data, p + 12)
        out[_str(data, no, enc == 1)] = (data[off:off + size], fmt)
        p += 20
        if has_floats: p += 8 + struct.unpack_from('<i', data, p + 4)[0]
    return out

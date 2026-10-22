"""Readers for the Elden Ring file formats import_er_game.py needs. Read-only: nothing here writes to the game folder.

    BHD5/BDT  archive headers (RSA-encrypted) and the files they point into
    DCX       compressed files: DFLT (zlib), ZSTD, KRAK (the game's own Oodle DLL)
    BND4      file bundles (regulation.bin, .anibnd, .msgbnd)
    PARAM     game param tables, laid out by Paramdex definitions
    FMG       text tables (weapon names)
    TAE       animation events (hitboxes, cancel windows, hyper armor...)

Formats follow SoulsFormats (https://github.com/soulsmods/SoulsFormats); keys and layouts are fetched by the importer.
"""
import ctypes, math, re, struct, zlib
import xml.etree.ElementTree as ET
from compression import zstd
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_public_key

# regulation.bin AES key (SoulsFormats SFUtil.ER_REGULATION_KEY); the first 16 bytes of the file are the IV
REGULATION_KEY = bytes.fromhex('99BFFC366A6BC8C6F5827D093602D676C42892A01C207FB024D3AF4E493FEF99')

# --- archives -----------------------------------------------------------------------------------------------------

def archive_keys(archive_keys_cs):
    """RSA public keys per archive from UXM's ArchiveKeys.cs, e.g. {'Data0': '-----BEGIN RSA PUBLIC KEY-----...'}."""
    block = archive_keys_cs[archive_keys_cs.index('EldenRingKeys'):]
    block = block[:block.index('};')]
    return {m.group(1): m.group(2) for m in re.finditer(
        r'\["([^"]+)"\]\s*=\s*@"(-----BEGIN RSA PUBLIC KEY-----.*?-----END RSA PUBLIC KEY-----)', block, re.S)}

def rsa_decrypt(data, pem):
    pub = load_pem_public_key(pem.encode()).public_numbers()
    k = (pub.n.bit_length() + 7) // 8
    out = bytearray()
    for i in range(0, len(data), k):
        out += pow(int.from_bytes(data[i:i+k], 'big'), pub.e, pub.n).to_bytes(k - 1, 'big')
    return bytes(out)

def path_hash(path):
    h = 0
    for c in path.lower().replace('\\', '/'):
        h = (h * 0x85 + ord(c)) & 0xFFFFFFFFFFFFFFFF
    return h

def read_bhd5(raw):
    """Decrypted BHD5 -> {path hash: (offset, padded size, size, aes key and ranges or None)}."""
    assert raw[:4] == b'BHD5', raw[:4]
    buckets, boff = struct.unpack_from('<ii', raw, 0x10)
    files = {}
    for b in range(buckets):
        count, hoff = struct.unpack_from('<ii', raw, boff + b*8)
        for i in range(count):
            h, padded, size, off, _sha, aes = struct.unpack_from('<QiiqqQ', raw, hoff + i*40)
            key = None
            if aes:
                n, = struct.unpack_from('<i', raw, aes + 16)
                key = (raw[aes:aes+16], [struct.unpack_from('<qq', raw, aes + 20 + j*16) for j in range(n)])
            files[h] = (off, padded, size, key)
    return files

def read_from_bdt(bdt_path, entry):
    off, padded, size, key = entry
    with open(bdt_path, 'rb') as f:
        f.seek(off)
        data = bytearray(f.read(padded))
    if key:
        dec = Cipher(algorithms.AES(key[0]), modes.ECB()).decryptor()
        for s, e in key[1]:
            if s != -1 and e > s:
                data[s:e] = dec.update(bytes(data[s:e]))
    return bytes(data[:size or padded])

# --- compression and bundles ---------------------------------------------------------------------------------------

_oodle = {}
def dcx_decompress(data, oodle_dll=None):
    assert data[:4] == b'DCX\0', data[:4]
    size, csize = struct.unpack_from('>II', data, 0x1C)
    fmt, body = data[0x28:0x2C], data[0x4C:0x4C+csize]
    if fmt == b'DFLT': return zlib.decompress(body)
    if fmt == b'ZSTD': return zstd.decompress(body)
    if fmt == b'KRAK':
        if oodle_dll not in _oodle:
            fn = ctypes.WinDLL(oodle_dll).OodleLZ_Decompress
            fn.restype = ctypes.c_int64
            fn.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int, ctypes.c_int,
                           ctypes.c_int, ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                           ctypes.c_int64, ctypes.c_int]
            _oodle[oodle_dll] = fn
        out = ctypes.create_string_buffer(size)
        n = _oodle[oodle_dll](body, csize, out, size, 1, 0, 0, None, 0, None, None, None, 0, 3)
        assert n == size, (n, size)
        return out.raw
    raise ValueError(f'unknown DCX format {fmt}')

def decrypt_regulation(raw):
    dec = Cipher(algorithms.AES(REGULATION_KEY), modes.CBC(raw[:16])).decryptor()
    return dcx_decompress(dec.update(raw[16:]) + dec.finalize())

def read_bnd4(data):
    """BND4 -> {file name (last path part): bytes}."""
    assert data[:4] == b'BND4', data[:4]
    e = '>' if data[0x09] else '<'
    count, = struct.unpack_from(e+'i', data, 0x0C)
    stride, = struct.unpack_from(e+'q', data, 0x20)
    unicode_, fmt = data[0x30], data[0x31]
    if data[0x0A]:  # format byte is stored bit-reversed
        fmt = int(f'{fmt:08b}'[::-1], 2)
    files = {}
    for i in range(count):
        p = 0x40 + i*stride
        size, = struct.unpack_from(e+'q', data, p + 8)
        q = p + 16 + (8 if fmt & 0x20 else 0)
        if fmt & 0x10: off, = struct.unpack_from(e+'q', data, q); q += 8
        else: off, = struct.unpack_from(e+'i', data, q); q += 4
        if fmt & 0x02: q += 4
        no, = struct.unpack_from(e+'i', data, q)
        if unicode_:
            end = no
            while data[end:end+2] != b'\0\0': end += 2
            name = data[no:end].decode('utf-16-le')
        else:
            name = data[no:data.index(b'\0', no)].decode('shift_jis')
        files[name.replace('\\', '/').rsplit('/', 1)[-1]] = data[off:off+size]
    return files

# --- params --------------------------------------------------------------------------------------------------------

_TYPES = {'s8': ('b', 1), 'u8': ('B', 1), 's16': ('h', 2), 'u16': ('H', 2), 's32': ('i', 4), 'u32': ('I', 4),
          'f32': ('f', 4), 'dummy8': ('B', 1), 'b32': ('i', 4), 'angle32': ('f', 4), 'f64': ('d', 8)}

def param_layout(paramdef_xml):
    """Paramdex XML -> ([(field, type, byte offset, bit position or None, bit count or array length)], row size)."""
    out, off, unit = [], 0, None
    for f in ET.fromstring(paramdef_xml).iter('Field'):
        m = re.match(r'(\w+)\s+(\w+)\s*(?::\s*(\d+))?\s*(?:\[(\d+)\])?', f.get('Def').strip())
        t, name, bits, n = m.group(1), m.group(2), m.group(3), int(m.group(4) or 1)
        size = _TYPES[t][1]
        if bits is not None and int(bits) < size*8:
            bits = int(bits)
            if unit and unit[0] == size and unit[2] + bits <= size*8:
                out.append((name, t, unit[1], unit[2], bits)); unit = (size, unit[1], unit[2] + bits)
            else:
                out.append((name, t, off, 0, bits)); unit = (size, off, bits); off += size
            continue
        unit = None
        out.append((name, t, off, None, n)); off += size*n
    return out, off

def read_param(data, paramdef_xml):
    """PARAM -> {row id: {field: value}}. Checks the definition's row size against the file."""
    rows, = struct.unpack_from('<H', data, 0x0A)
    layout, size = param_layout(paramdef_xml)
    heads = [struct.unpack_from('<iiqq', data, 0x40 + i*24) for i in range(rows)]
    if rows > 1 and heads[1][2] - heads[0][2] != size:
        raise ValueError(f'param definition is {size} bytes per row, file has {heads[1][2] - heads[0][2]}')
    table = {}
    for rid, _, off, _ in heads:
        r = {}
        for name, t, o, bit, n in layout:
            if t == 'dummy8': continue
            code, sz = _TYPES[t]
            if bit is not None:
                v, = struct.unpack_from('<' + {1: 'B', 2: 'H', 4: 'I'}[sz], data, off + o)
                r[name] = (v >> bit) & ((1 << n) - 1)
            elif n == 1:
                r[name], = struct.unpack_from('<' + code, data, off + o)
            else:
                r[name] = list(struct.unpack_from(f'<{n}{code}', data, off + o))
        table[rid] = r
    return table

# --- text ----------------------------------------------------------------------------------------------------------

def read_fmg(data):
    """FMG (version 2, 64-bit offsets) -> {id: text}."""
    groups, = struct.unpack_from('<i', data, 0x0C)
    offsets, = struct.unpack_from('<q', data, 0x18)
    out = {}
    for g in range(groups):
        idx, first, last = struct.unpack_from('<iii', data, 0x28 + g*16)
        for i in range(last - first + 1):
            so, = struct.unpack_from('<q', data, offsets + (idx + i)*8)
            if so <= 0: continue
            end = so
            while data[end:end+2] != b'\0\0': end += 2
            out[first + i] = data[so:end].decode('utf-16-le')
    return out

# --- animation events ----------------------------------------------------------------------------------------------

def read_tae(data):
    """TAE -> (section, {anim id: (events, imported full anim id or None)}); events are (type, start s, end s, params)."""
    assert data[:4] == b'TAE '
    tae_id, n, off = struct.unpack_from('<iiq', data, 0x50)
    anims = {}
    for i in range(n):
        aid, ao = struct.unpack_from('<qq', data, off + i*16)
        eh, _, _, af, ec = struct.unpack_from('<qqqqi', data, ao)
        kind, = struct.unpack_from('<i', data, af)
        imported = struct.unpack_from('<i', data, af + 0x18)[0] if kind == 1 else None
        events = []
        for j in range(ec):
            so, eo, do = struct.unpack_from('<qqq', data, eh + j*24)
            s, = struct.unpack_from('<f', data, so)
            e, = struct.unpack_from('<f', data, eo)
            typ, _, po = struct.unpack_from('<iiq', data, do)
            events.append((typ, s, e, data[po:po+64] if po else b''))
        anims[aid] = (events, imported)
    return tae_id - 2000, anims

def frame_clock(events, fps=30):
    """Seconds of TAE time -> frames of real time. Event 608 changes playback speed linearly from its first to its
    second float over its range, so the same TAE time can play out faster or slower."""
    segs = sorted((s, e, *struct.unpack_from('<ff', p)) for t, s, e, p in events if t == 608 and e < 1e6)
    def frame(t):
        real, cur = 0.0, 0.0
        for s, e, a, b in segs:
            if s >= t: break
            real += max(0.0, s - cur)
            hi = min(e, t)
            if hi > s and a > 0 and b > 0:
                if abs(b - a) < 1e-6: real += (hi - s) / a
                else: real += (e - s) / (b - a) * math.log((a + (b - a) * (hi - s) / (e - s)) / a)
            cur = max(cur, hi)
        real += max(0.0, t - cur)
        return round(real * fps)
    return frame

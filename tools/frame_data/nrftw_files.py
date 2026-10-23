"""Reader for No Rest for the Wicked's gameplay database (scouting prototype). Read-only: nothing here writes to the game folder.

    quantumDatabase.bin   StreamingAssets/; header 'MOON_QDB', a (type id, size) table, then LZ4 blocks wrapped as
                          MessagePack ext 99 (MessagePack-CSharp's Lz4Block). Decompressed, it is a stream of
                          MessagePack values with string keys: [type hash, asset] pairs, one per Quantum asset,
                          each asset carrying its 'Guid'. Fixed-point numbers are {'RawValue': n} with 16 fraction bits.
    asset names           the qdb_assets_all_*.bundle Addressables bundle (UnityPy) maps each asset path, e.g.
                          Assets/actions/playerRig/.../doubleDaggerAttackA1.action, to the same AssetGuid.

Usage:
    python tools/frame_data/nrftw_files.py "Z:/SteamLibrary/steamapps/common/NoRestForTheWicked" doubleDaggerAttackA1.action
prints the decoded asset as JSON (fixed-point values converted to floats).
"""
import json, os, struct, sys
import lz4.block

DATA = 'NoRestForTheWicked_Data/StreamingAssets'

# --- MessagePack --------------------------------------------------------------------------------------------------

class Reader:
    """Plain MessagePack, plus Moon's custom ext values (baked curves, bone tracks): their payload starts with an
    inner [int length][bool] header that the ext's own length leaves out. Those come back as ('ext', type, raw bytes)."""
    def __init__(self, b, o=0):
        self.b, self.o = b, o

    def _u(self, fmt):
        v = struct.unpack_from(fmt, self.b, self.o)[0]
        self.o += struct.calcsize(fmt)
        return v

    def _bytes(self, n):
        v = self.b[self.o:self.o+n]
        self.o += n
        return v

    def read(self):
        t = self.b[self.o]; self.o += 1
        if t <= 0x7f: return t
        if t >= 0xe0: return t - 256
        if t <= 0x8f: return self._map(t & 15)
        if t <= 0x9f: return [self.read() for _ in range(t & 15)]
        if t <= 0xbf: return self._bytes(t & 31).decode('utf8', 'replace')
        if t == 0xc0: return None
        if t in (0xc2, 0xc3): return t == 0xc3
        if t in (0xc4, 0xc5, 0xc6): return self._bytes(self._u({0xc4: '>B', 0xc5: '>H', 0xc6: '>I'}[t]))
        if t in (0xc7, 0xc8, 0xc9): return self._ext(self._u({0xc7: '>B', 0xc8: '>H', 0xc9: '>I'}[t]))
        if 0xd4 <= t <= 0xd8: return self._ext(1 << (t - 0xd4))
        fixed = {0xca: '>f', 0xcb: '>d', 0xcc: '>B', 0xcd: '>H', 0xce: '>I', 0xcf: '>Q',
                 0xd0: '>b', 0xd1: '>h', 0xd2: '>i', 0xd3: '>q'}
        if t in fixed: return self._u(fixed[t])
        if t in (0xd9, 0xda, 0xdb): return self._bytes(self._u({0xd9: '>B', 0xda: '>H', 0xdb: '>I'}[t])).decode('utf8', 'replace')
        if t in (0xdc, 0xdd): return [self.read() for _ in range(self._u('>H' if t == 0xdc else '>I'))]
        if t in (0xde, 0xdf): return self._map(self._u('>H' if t == 0xde else '>I'))
        raise ValueError(f'MessagePack type {t:#x} at {self.o-1}')

    def _map(self, n):
        """A few of Moon's custom formatters (armament SelectionData, ImmunitySections) write two values for one key.
        The second comes back under '<key>$1'."""
        d, prev = {}, None
        for _ in range(n):
            k = self.read()
            extra = 1
            while not isinstance(k, (str, int)) and isinstance(prev, str):
                d[f'{prev}${extra}'] = k
                extra += 1
                k = self.read()
            d[k if isinstance(k, (str, int)) else repr(k)] = self.read()
            prev = k
        return d

    def _ext(self, n):
        typ = self._u('>b')
        b, q = self.b, self.o
        h, il = b[q], None
        if h == n and h <= 0x7f: il = 1
        elif h == 0xcc and b[q+1] == n: il = 2
        elif h == 0xcd and struct.unpack_from('>H', b, q+1)[0] == n: il = 3
        elif h == 0xce and struct.unpack_from('>I', b, q+1)[0] == n: il = 5
        if il is not None and b[q+il] in (0xc2, 0xc3):
            self.o = q + il + 1
        return ('ext', typ, self._bytes(n))

# --- quantumDatabase.bin ------------------------------------------------------------------------------------------

def unpack_qdb(path):
    """The decompressed MessagePack stream of quantumDatabase.bin."""
    b = open(path, 'rb').read()
    assert b[:8] == b'MOON_QDB', 'not a MOON_QDB file'
    o = 16 + 8 * struct.unpack_from('<I', b, 12)[0]
    out = []
    while o < len(b):
        assert b[o] == 0xc9, f'expected an LZ4 block at {o}'
        n, typ = struct.unpack_from('>Ib', b, o + 1)
        payload = b[o+6:o+6+n]
        assert typ == 99 and payload[0] == 0xd2
        out.append(lz4.block.decompress(payload[5:], uncompressed_size=struct.unpack_from('>i', payload, 1)[0]))
        o += 6 + n
    return b''.join(out)

def qdb_assets(raw):
    """{guid: (type hash, asset)} for every asset in the stream."""
    r, assets = Reader(raw), {}
    def add(item):
        if isinstance(item, list) and len(item) == 2 and isinstance(item[1], dict) and isinstance(item[1].get('Guid'), dict):
            assets[item[1]['Guid']['Value']] = (item[0], item[1])
    while r.o < len(raw):
        v = r.read()
        if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int): add(v)
        elif isinstance(v, list):
            for item in v: add(item)
    return assets

def fp(o):
    """Replace {'RawValue': n} fixed-point values with floats, ext blobs with a short description."""
    if isinstance(o, dict):
        return round(o['RawValue'] / 65536, 4) if set(o) == {'RawValue'} else {k: fp(v) for k, v in o.items()}
    if isinstance(o, list): return [fp(x) for x in o]
    if isinstance(o, tuple): return f'<ext {o[1]}, {len(o[2])} bytes>'
    if isinstance(o, bytes): return f'<{len(o)} bytes>'
    return o

# --- asset names --------------------------------------------------------------------------------------------------

def asset_guids(game_dir):
    """{asset path: AssetGuid} from the qdb_assets Addressables bundle (needs UnityPy)."""
    import UnityPy
    folder = os.path.join(game_dir, DATA, 'aa/StandaloneWindows64')
    bundle = next(f for f in os.listdir(folder) if f.startswith('qdb_assets_all_'))
    guids = {}
    for path, obj in UnityPy.load(os.path.join(folder, bundle)).container.items():
        if obj.type.name == 'MonoBehaviour':
            g = obj.read_typetree().get('AssetGuid')
            if g: guids[path] = g['Value']
    return guids

class Game:
    """The decoded database plus asset paths, cached in .cache/nrftw/ (keyed by the database's size and date) because a
    full decode takes about half a minute. game.path[guid] / game.guid[path] / game.asset(guid or path)."""
    def __init__(self, game_dir, cache_dir=None):
        import pickle
        self.dir = game_dir
        db = os.path.join(game_dir, DATA, 'quantumDatabase.bin')
        st = os.stat(db)
        cache = os.path.join(cache_dir or os.path.join(os.path.dirname(__file__), '..', '..', '.cache', 'nrftw'),
                             f'qdb-{st.st_size}-{int(st.st_mtime)}.pkl')
        if os.path.exists(cache):
            self.guid, self.assets = pickle.load(open(cache, 'rb'))
        else:
            self.guid = asset_guids(game_dir)
            self.assets = qdb_assets(unpack_qdb(db))
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, 'wb') as f: pickle.dump((self.guid, self.assets), f, protocol=5)
        self.path = {g: p for p, g in self.guid.items()}
        self._env = None

    def asset(self, key):
        """The asset for a guid, an asset path or a {'Id': {'Value': guid}} reference; None when missing."""
        if isinstance(key, dict): key = key['Id']['Value']
        if isinstance(key, str): key = self.guid.get(key)
        return self.assets.get(key, (None, None))[1]

    def type_of(self, key):
        if isinstance(key, str): key = self.guid.get(key)
        return self.assets.get(key, (None, None))[0]

    def bundle(self):
        """The qdb_assets bundle (UnityPy), whose MonoBehaviours carry names, icons and prefab references, loaded with
        static_assets and world_assets, which hold the icon sprites and their textures."""
        if self._env is None:
            import UnityPy
            folder = os.path.join(self.dir, DATA, 'aa/StandaloneWindows64')
            self._env = UnityPy.load(*[os.path.join(folder, f) for f in sorted(os.listdir(folder))
                                       if f.startswith(('qdb_assets_all_', 'static_assets_all_', 'world_assets_all_'))])
        return self._env

    def icon(self, path):
        """An item's inventory icon (PIL image), or None."""
        try: ref = self.bundle().container[path].read().ItemIcon
        except (KeyError, AttributeError): return None
        if not ref.m_PathID: return None
        return ref.read().image

    def english(self, path, field='ItemNameMsg'):
        """English text of an item's localised message (ItemNameMsg, DescriptionData...), or None."""
        try: obj = self.bundle().container[path]
        except KeyError: return None
        ref = obj.read_typetree().get(field)
        if not ref or not ref.get('m_PathID') or ref.get('m_FileID'): return None
        return obj.assetsfile.objects[ref['m_PathID']].read_typetree().get('English') or None

if __name__ == '__main__':
    game_dir, suffix = sys.argv[1], sys.argv[2]
    guids = {p: g for p, g in asset_guids(game_dir).items() if p.endswith(suffix)}
    assets = qdb_assets(unpack_qdb(os.path.join(game_dir, DATA, 'quantumDatabase.bin')))
    for path, g in guids.items():
        print(path)
        print(json.dumps(fp(assets.get(g, (None, None))[1]), indent=1))

"""Enum names from No Rest for the Wicked's IL2CPP metadata (global-metadata.dat, version 31, not encrypted). Read-only.

The gameplay database stores enums as numbers (action section ids, damage schools, input slots); their names only exist
in the metadata. This reads just enough of it: the string table, type definitions (88 bytes, name at +0, first field at
+32, field count at +68), fields (12 bytes: name, type, token) and field default values (12 bytes: field, type, data),
whose data is IL2CPP's compressed int encoding.

    python tools/frame_data/nrftw_il2cpp.py "Z:/SteamLibrary/steamapps/common/NoRestForTheWicked" QuantumActionSectionId DamageSchool
"""
import os, struct, sys

META = 'NoRestForTheWicked_Data/il2cpp_data/Metadata/global-metadata.dat'

class Metadata:
    def __init__(self, game_dir):
        b = self.b = open(os.path.join(game_dir, META), 'rb').read()
        assert struct.unpack_from('<Ii', b, 0) == (0xFAB11BAF, 31), 'expected IL2CPP metadata version 31'
        h = struct.unpack_from('<64i', b, 8)
        sec = lambda i: (h[2 * i], h[2 * i + 1])
        self.strings = sec(2)[0]
        self.defaults_data = sec(8)[0]
        fo, fs = sec(11)
        self.fields = [struct.unpack_from('<3i', b, fo + 12 * i) for i in range(fs // 12)]
        do, ds = sec(7)
        self.defaults = {f: d for f, t, d in (struct.unpack_from('<3i', b, do + 12 * i) for i in range(ds // 12))}
        to, ts = sec(19)
        self.types = {}
        for k in range(ts // 88):
            name = self.str(struct.unpack_from('<i', b, to + 88 * k)[0])
            start = struct.unpack_from('<i', b, to + 88 * k + 32)[0]
            count = struct.unpack_from('<H', b, to + 88 * k + 68)[0]
            self.types.setdefault(name, []).append((start, count))

    def str(self, i):
        o = self.strings + i
        return self.b[o:self.b.index(b'\0', o)].decode('utf8', 'replace')

    def _int(self, o):
        b = self.b
        v = b[o]
        if v & 0x80 == 0: u = v
        elif v & 0xC0 == 0x80: u = ((v & 0x3F) << 8) | b[o + 1]
        elif v & 0xE0 == 0xC0: u = ((v & 0x1F) << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]
        elif v == 0xF0: u = struct.unpack_from('<I', b, o + 1)[0]
        elif v == 0xFE: u = 0xFFFFFFFE
        else: u = 0xFFFFFFFF
        if u == 0xFFFFFFFF: return -2 ** 31
        return -(u >> 1) - 1 if u & 1 else u >> 1

    def enum(self, name, which=0):
        """{value: field name} for an enum type (the which-th type of that name)."""
        start, count = self.types[name][which]
        out = {}
        for f in range(start, start + count):
            fname = self.str(self.fields[f][0])
            if fname != 'value__' and f in self.defaults:
                out[self._int(self.defaults_data + self.defaults[f])] = fname
        return out

if __name__ == '__main__':
    m = Metadata(sys.argv[1])
    for name in sys.argv[2:]:
        for i in range(len(m.types.get(name, []))):
            print(name, i, m.enum(name, i))

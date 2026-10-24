"""Read an Xbox disc image (XDVDFS) without changing it.

  python ngb_xiso.py <iso> list                -> prints every file with its size
  python ngb_xiso.py <iso> extract <out> <glob> [<glob> ...]   -> copies matching files (by name, case-insensitive)
"""
import fnmatch, os, struct, sys

SECTOR = 2048
BASES = [0, 0xFD90, 0x30600, 0xFD90000, 0x18300000]
MAGIC = b"MICROSOFT*XBOX*MEDIA"


def find_base(f):
    for b in BASES:
        f.seek(b + 32 * SECTOR)
        if f.read(20) == MAGIC:
            return b
    raise SystemExit("no XDVDFS volume found")


def walk(f, base, sector, size, prefix, out):
    if size == 0:
        return
    f.seek(base + sector * SECTOR)
    data = f.read(size)
    seen = set()
    stack = [0]
    while stack:
        off = stack.pop()
        if off in seen or off + 14 > len(data):
            continue
        seen.add(off)
        left, right, start, length, attr, nlen = struct.unpack_from("<HHIIBB", data, off)
        if left == 0xFFFF:
            continue
        name = data[off + 14: off + 14 + nlen].decode("latin-1")
        path = prefix + name
        if attr & 0x10:
            walk(f, base, start, length, path + "/", out)
        else:
            out.append((path, base + start * SECTOR, length))
        if left:
            stack.append(left * 4)
        if right:
            stack.append(right * 4)


def files(f):
    base = find_base(f)
    f.seek(base + 32 * SECTOR + 20)
    root, rsize = struct.unpack("<II", f.read(8))
    out = []
    walk(f, base, root, rsize, "", out)
    return sorted(out)


def main():
    iso, cmd = sys.argv[1], sys.argv[2]
    with open(iso, "rb") as f:
        entries = files(f)
        if cmd == "list":
            for p, o, n in entries:
                print(f"{n:>12} {p}")
            print(f"{len(entries)} files, {sum(n for _, _, n in entries)} bytes")
        elif cmd == "extract":
            outdir, globs = sys.argv[3], [g.lower() for g in sys.argv[4:]]
            for p, o, n in entries:
                if not any(fnmatch.fnmatch(p.lower(), g) or fnmatch.fnmatch(os.path.basename(p).lower(), g) for g in globs):
                    continue
                dst = os.path.join(outdir, *p.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                f.seek(o)
                with open(dst, "wb") as w:
                    left = n
                    while left:
                        chunk = f.read(min(left, 1 << 22))
                        w.write(chunk)
                        left -= len(chunk)
                print("extracted", p, n)


if __name__ == "__main__":
    main()

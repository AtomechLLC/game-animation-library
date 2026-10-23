"""Exports Elden Ring's common (non-weapon) player animations for the 3D preview and the GIF renders: rolls, walks,
hit reactions, gestures and the like, listed in tools/er_gifs/common_anims.json as
[{"id": "a000_027110", "label": "Roll forward (medium load)", "want": "forward roll"}, ...].

    python tools/frame_data/export_er_common.py "D:/SteamLibrary/steamapps/common/ELDEN RING"

Run export_er_models.py first; this adds to its output in frame-data/models/elden-ring/:

    anim/<id>.bin               each animation baked the way export_er_models bakes moves (30 fps, root motion)
    moves/common.json           the "Common" class: {id: {frames, weapon, hits: []}}
    models.json                 gains classes.Common; nothing else in it changes
"""
import json, math, os, sys
import numpy as np
import export_er_models as M

LIST = os.path.join(M.ROOT, 'tools', 'er_gifs', 'common_anims.json')
WEAPON = 'Broadsword'

class Game(M.Game):
    """Also looks in the two section-0 bundles moves never need: a00_md (hit reactions 005xxx) and a00_lo (idles)."""
    def hkx(self, sec, aid):
        root = super().hkx(sec, aid)
        if root is not None or sec != 0: return root
        name = f'a000_{aid:06d}.hkx'
        for group in ('a00_md', 'a00_lo'):
            if group not in self._bundles:
                b = M.F.read_bnd4(self.arc.read(f'/chr/c0000_{group}.anibnd.dcx'))
                comp = next(v for k, v in b.items() if k.endswith('.compendium'))
                self._bundles[group] = (b, M.H.read_compendium(comp))
            b, comp = self._bundles[group]
            if name in b: return M.H.read_tagfile(b[name], comp)
        return None

def bake_any(gm, aid):
    """gm.move without the TAE: plain 30 fps over the animation's length, for ids the TAE has no entry for."""
    sec, n = int(aid[1:4]), int(aid[5:])
    root = gm.find_hkx(sec, n)
    if root is None: return None, 0
    a = M.H.animation(root)
    total = max(1, int(math.ceil(a['duration'] * M.G.FPS - 1e-6)))
    return M.bake(a, np.arange(total) / M.G.FPS), total

def main(game_dir):
    gm = Game(game_dir)
    wanted = json.load(open(LIST, encoding='utf-8'))
    moves, missing, size = {}, [], 0
    for w in wanted:
        aid = w['id']
        if aid in moves: continue
        sec, n = int(aid[1:4]), int(aid[5:])
        if n in gm.taes.get(sec, {}):
            data, frames, _ = gm.move(aid)
        else:
            data, frames = bake_any(gm, aid)
        if data is None:
            missing.append(aid); print('  no animation for', aid, w['label']); continue
        open(os.path.join(M.OUT, 'anim', f'{aid}.bin'), 'wb').write(data)
        size += len(data)
        moves[aid] = {'frames': frames, 'weapon': WEAPON, 'hits': []}
    with open(os.path.join(M.OUT, 'moves', 'common.json'), 'w', encoding='utf-8') as f:
        json.dump({'class': 'Common', 'moves': moves, 'attacks': {}}, f, ensure_ascii=False, separators=(',', ':'))
    path = os.path.join(M.OUT, 'models.json')
    manifest = json.load(open(path, encoding='utf-8'))
    manifest['classes']['Common'] = {'file': 'moves/common.json', 'weapon': WEAPON}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(moves)} of {len(wanted)} animations, {size / 1e6:.1f} MB; missing: {", ".join(missing) or "none"}')

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(M.G.game_dir(sys.argv[1]))

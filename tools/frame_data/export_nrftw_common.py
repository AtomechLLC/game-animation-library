"""Exports No Rest for the Wicked's common (non-attack) player animations for the 3D preview and the GIF renders:
quicksteps, rolls, sneaking, swimming, mantles, ladders, wall and rope climbing. Listed in
tools/er_gifs/nrftw_common_anims.json as [{"id": "oneHanded-quickStepL", "label": "Quickstep left", "want": ...}, ...].

    python tools/frame_data/export_nrftw_common.py "Z:/SteamLibrary/steamapps/common/NoRestForTheWicked"
    python tools/frame_data/export_nrftw_common.py "<install>" --find quickStepL stroke     # list candidates

Run export_nrftw_models.py first; this adds to its output in frame-data/models/no-rest-for-the-wicked/:

    anim/<id>.bin               each clip baked the way export_nrftw_models bakes an action (60 fps, FDA2, poses every
                                2nd frame, root_JNT's translation as root motion, the same bones)
    moves/common.json           the "Common" class: {id: {frames, anim, weapon, hits: []}}, no boxes
    models.json                 gains classes.Common; nothing else in it changes

These animations aren't Quantum actions: the hero's view plays them through Moon's own animator. Each is a
ClipAnimation MonoBehaviour (its Clip is the AnimationClip) of playerMoonAnimatorDefinition, reached from a weapon
group's <group>AnimationSet (oneHanded, greatHammers, greatSwords... each has its own roll and quickstep clips) or from
a blend space (swimStokeBlendSpace, climbMovementBlend...). An id is "<context>-<ClipAnimation name>", the context
being the AnimationSet's group, an ancestor blend's name, or a piece of the asset path ("ladder"), or "hero" when the
name alone is unique.
"""
import collections, json, os, sys
import export_nrftw_models as M

LIST = os.path.join(M.ROOT, 'tools', 'er_gifs', 'nrftw_common_anims.json')
WEAPON = 'Claymore'
DEFINITION = 'playerMoonAnimatorDefinition'

def refs_of(v, out):
    if isinstance(v, dict):
        if 'm_PathID' in v and 'm_FileID' in v:
            if v['m_PathID']: out.add(v['m_PathID'])
        else:
            for x in v.values(): refs_of(x, out)
    elif isinstance(v, list):
        for x in v: refs_of(x, out)

class Animations:
    """The player's ClipAnimations, with what references them (path ids are unique across the bundles)."""
    def __init__(self, A):
        files = {o.assets_file.name: o.assets_file for o in A.env.objects}
        self.files = {k.lower(): f for k, f in files.items()}
        paths = {}
        for k, objs in A.paths.items():
            for p in objs:
                if p.type.name == 'MonoBehaviour': paths[p.m_PathID] = k
        self.info, self.back = {}, collections.defaultdict(set)
        definition = None
        for af in files.values():
            for pid, o in af.objects.items():
                if o.type.name != 'MonoBehaviour': continue
                try: t = o.read_typetree()
                except Exception: continue
                refs = set()
                refs_of({k: v for k, v in t.items() if k not in ('m_Script', 'm_GameObject', 'AnimatorDefinition')}, refs)
                if t.get('m_Name') == DEFINITION: definition = pid
                d = t.get('AnimatorDefinition')
                self.info[pid] = {'name': t.get('m_Name') or '', 'def': d and d['m_PathID'], 'clip': t.get('Clip'),
                                  'file': af, 'path': paths.get(pid, '')}
                for r in refs: self.back[r].add(pid)
        self.clips = collections.defaultdict(list)
        for pid, i in self.info.items():
            if i['def'] == definition and i['clip'] is not None: self.clips[i['name']].append(pid)

    def contexts(self, pid, depth=7):
        """Names this ClipAnimation is reached from: blend spaces up to its weapon groups' AnimationSets."""
        out, seen, level = set(), {pid}, {pid}
        for _ in range(depth):
            nxt = set()
            for p in level:
                for q in self.back.get(p, ()):
                    if q in seen or q not in self.info: continue
                    seen.add(q)
                    n = self.info[q]['name']
                    if n.endswith('AnimationSet'): out.add(n[:-len('AnimationSet')])
                    else: out.add(n); nxt.add(q)
            level = nxt
        return out

    def find(self, context, name):
        """The ClipAnimations an id names (several when the game duplicates one)."""
        cands = self.clips.get(name, [])
        if context == 'hero': return cands
        return [p for p in cands if context in self.contexts(p) or (context in self.info[p]['path'])]

    def clip(self, pid):
        i = self.info[pid]
        fid, cpid = i['clip']['m_FileID'], i['clip']['m_PathID']
        af = i['file']
        if fid: af = self.files.get(af.externals[fid - 1].path.rsplit('/', 1)[-1].lower())
        o = af and af.objects.get(cpid)
        return o.read() if o is not None else None

def bake(ex, clip, key):
    """export_nrftw_models' move_anim on a one-segment action covering the whole clip (no hitboxes: no time warp)."""
    length = M.U.clip_length(clip)
    ex.clips[key] = clip
    action = {'TimelineData': {'Duration': length},
              'Animations': [{'StartFrame': 0, 'FrameCount': max(1, int(round(length * M.FPS))), 'Animation': {'Id': {'Value': key}}}]}
    return ex.move_anim(action)

def main(game_dir, find=None):
    ex = M.Exporter(game_dir)
    print('indexing the animator...')
    an = Animations(ex.A)
    if find:
        for name in find:
            for p in an.clips.get(name, []):
                c = an.clip(p)
                print(name, p, round(M.U.clip_length(c), 3) if c else None, an.info[p]['path'] or '-', sorted(an.contexts(p))[:12])
        return
    ex.armor(*M.EXPORT['armor'])        # fills ex.skinned, so the same bones are kept
    ex.keep = ex.needed()
    wanted = json.load(open(LIST, encoding='utf-8'))
    path = os.path.join(M.OUT, 'models.json')
    manifest = json.load(open(path, encoding='utf-8'))
    assert WEAPON in manifest['weapons'], WEAPON
    moves, missing, size = {}, [], 0
    for w in wanted:
        aid = w['id']
        if aid in moves: continue
        context, name = aid.split('-', 1)
        found = an.find(context, name)
        clips = {}
        for p in found:
            c = an.clip(p)
            if c is not None: clips.setdefault(c.m_Name + str(round(M.U.clip_length(c), 3)), (p, c))
        if not clips:
            missing.append(aid); print('  no animation for', aid, w['label']); continue
        if len(clips) > 1: print(f'  {aid}: {len(clips)} different clips, using the first')
        p, c = clips[min(clips)] if len(clips) > 1 else next(iter(clips.values()))
        r = bake(ex, c, aid)
        if r is None:
            missing.append(aid); print('  nothing to bake for', aid); continue
        frames, data = r
        open(os.path.join(M.OUT, 'anim', f'{aid}.bin'), 'wb').write(data)
        size += len(data)
        moves[aid] = {'frames': frames, 'anim': aid, 'weapon': WEAPON, 'hits': []}
    with open(os.path.join(M.OUT, 'moves', 'common.json'), 'w', encoding='utf-8') as f:
        json.dump({'class': 'Common', 'moves': moves, 'boxes': {}}, f, ensure_ascii=False, separators=(',', ':'))
    manifest['classes']['Common'] = {'file': 'moves/common.json', 'weapon': WEAPON}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(moves)} of {len(wanted)} animations, {size / 1e6:.1f} MB; missing: {", ".join(missing) or "none"}')

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    args = sys.argv[2:]
    main(sys.argv[1], args[1:] if args[:1] == ['--find'] else None)

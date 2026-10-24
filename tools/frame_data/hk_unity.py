"""Unity side of Hollow Knight (and Silksong): the asset files read with UnityPy. Read-only.

The Steam build is Unity 6 with Mono scripts and no type trees in the asset files, so MonoBehaviours are laid out
from the game's own Managed DLLs with TypeTreeGeneratorAPI. Its trees miss the 4-byte align after m_Enabled, which
every MonoBehaviour has; MonoTrees adds it back.
"""
import os, struct

class MonoTrees:
    """UnityPy typetree_generator built from <game>/<x>_Data/Managed, with the m_Enabled align fixed."""
    def __init__(self, data_dir, unity_version):
        from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
        from UnityPy.helpers.TypeTreeNode import TypeTreeNode
        self._node = TypeTreeNode
        self.gen = TypeTreeGenerator(unity_version)
        self.gen.load_local_dll_folder(os.path.join(data_dir, 'Managed'))
        self.cache = {}

    def get_nodes_up(self, assembly, fullname):
        key = (assembly, fullname)
        if key not in self.cache:
            if not assembly.endswith('.dll'): assembly += '.dll'
            base = self.gen.get_nodes(assembly, fullname)
            nodes = []
            for b in base:
                flag = b.m_MetaFlag
                if b.m_Level == 1 and b.m_Name == 'm_Enabled': flag |= 0x4000
                nodes.append(self._node(b.m_Level, b.m_Type, b.m_Name, 0, 0, m_MetaFlag=flag))
            self.cache[key] = self._node.from_list(nodes)
        return self.cache[key]

def data_dir(game_dir):
    return os.path.join(game_dir, next(f for f in os.listdir(game_dir) if f.endswith('_Data')))

def unity_version(ddir):
    with open(os.path.join(ddir, 'globalgamemanagers'), 'rb') as f:
        head = f.read(64)
    # version string follows the header
    i = head.find(b'6000.') if b'6000.' in head else head.find(b'20')
    return head[i:head.index(b'\0', i)].decode()

def load(game_dir, files):
    """One UnityPy environment over the named asset files (relative to the _Data folder), MonoBehaviours readable."""
    import UnityPy
    ddir = data_dir(game_dir)
    env = UnityPy.load(*[os.path.join(ddir, f) for f in files])
    env.typetree_generator = MonoTrees(ddir, unity_version(ddir))
    return env

def mono_header(raw):
    """(game object path id, script file id, script path id, name) straight from a MonoBehaviour's bytes."""
    go_file, go_path = struct.unpack_from('<iq', raw, 0)
    s_file, s_path = struct.unpack_from('<iq', raw, 16)
    n = struct.unpack_from('<i', raw, 28)[0]
    return go_path, s_file, s_path, raw[32:32 + n].decode('utf-8', 'replace')

# --- a plain type tree reader --------------------------------------------------------------------------------------
# UnityPy's reader trips on some generated trees (nested strings and arrays inside serialized classes), so
# MonoBehaviours are read here by walking the generated nodes directly. Strings and arrays always align to 4 bytes,
# as Unity writes them; other nodes align when their meta flag says so.
_PRIM = {'SInt8': 'b', 'UInt8': 'B', 'char': 'B', 'bool': '?', 'SInt16': 'h', 'short': 'h', 'UInt16': 'H',
         'unsigned short': 'H', 'SInt32': 'i', 'int': 'i', 'UInt32': 'I', 'unsigned int': 'I', 'Type*': 'i',
         'SInt64': 'q', 'long long': 'q', 'UInt64': 'Q', 'unsigned long long': 'Q', 'FileSize': 'Q',
         'float': 'f', 'double': 'd'}

class _Node:
    __slots__ = ('type', 'name', 'flag', 'kids')
    def __init__(self, t, n, f): self.type, self.name, self.flag, self.kids = t, n, f, []

def _tree(nodes):
    root = None; stack = []
    for b in nodes:
        n = _Node(b.m_Type, b.m_Name, b.m_MetaFlag)
        while stack and stack[-1][0] >= b.m_Level: stack.pop()
        if stack: stack[-1][1].kids.append(n)
        else: root = n
        stack.append((b.m_Level, n))
    return root

class Reader:
    def __init__(self, raw): self.b, self.p = raw, 0
    def align(self): self.p = (self.p + 3) & ~3
    def read(self, n):
        if n.type in _PRIM:
            fmt = _PRIM[n.type]; v = struct.unpack_from('<' + fmt, self.b, self.p)[0]; self.p += struct.calcsize(fmt)
        elif n.type == 'string' and not (n.kids and n.kids[0].kids[1].type != 'char'):
            ln = struct.unpack_from('<i', self.b, self.p)[0]; self.p += 4
            if ln < 0 or self.p + ln > len(self.b): raise ValueError(f'bad string length {ln} at {self.p} ({n.name})')
            v = self.b[self.p:self.p + ln].decode('utf-8', 'replace'); self.p += ln; self.align()
            return v
        elif n.kids and n.kids[0].type == 'Array' and len(n.kids) == 1:
            v = self.array(n.kids[0])
        elif n.type == 'Array':
            v = self.array(n)
        else:
            v = {k.name: self.read(k) for k in n.kids}
        if n.flag & 0x4000: self.align()
        return v
    def array(self, a):
        size = struct.unpack_from('<i', self.b, self.p)[0]; self.p += 4
        if size < 0 or size > len(self.b): raise ValueError(f'bad array size {size} at {self.p}')
        el = a.kids[1]
        if el.type in ('UInt8', 'char', 'SInt8') and not el.kids:
            v = self.b[self.p:self.p + size]; self.p += size
        elif el.type in _PRIM and not el.kids:
            fmt = _PRIM[el.type]; v = list(struct.unpack_from(f'<{size}{fmt}', self.b, self.p)); self.p += size * struct.calcsize(fmt)
        else:
            v = [self.read(el) for _ in range(size)]
        self.align()
        return v

class Game:
    """The asset files of one install, with MonoBehaviours readable by script class name."""
    def __init__(self, game_dir, files=('resources.assets',)):
        import UnityPy
        self.dir = data_dir(game_dir)
        self.trees = MonoTrees(self.dir, unity_version(self.dir))
        g = UnityPy.load(os.path.join(self.dir, 'globalgamemanagers.assets'))
        self.scripts = {}
        for o in g.objects:
            if o.type.name == 'MonoScript':
                s = o.read()
                full = (s.m_Namespace + '.' if s.m_Namespace else '') + s.m_ClassName
                self.scripts[o.path_id] = (s.m_AssemblyName, full, s.m_ClassName)
        self.env = UnityPy.load(*[os.path.join(self.dir, f) for f in files])
        self.files = {os.path.basename(n): f for n, f in self.env.files.items() if hasattr(f, 'objects')}
        self._trees = {}

    def load_file(self, name):
        """An asset file of the install (loaded on first use), for references into other files."""
        if name not in self.files:
            self.env.load_file(os.path.join(self.dir, name))
            self.files = {os.path.basename(n): f for n, f in self.env.files.items() if hasattr(f, 'objects')}
        return self.files[name]

    def script(self, obj):
        """Class name of a MonoBehaviour (None for other objects)."""
        if obj.type.name != 'MonoBehaviour': return None
        s = self.scripts.get(mono_header(obj.get_raw_data())[2])
        return s and s[2]

    def mono(self, obj):
        """A MonoBehaviour as a dict, read with the game's own field layout."""
        asm, full, _ = self.scripts[mono_header(obj.get_raw_data())[2]]
        key = (asm, full)
        if key not in self._trees:
            if not asm.endswith('.dll'): asm += '.dll'
            self._trees[key] = _tree(self.trees.gen.get_nodes(asm, full))
        root = self._trees[key]
        r = Reader(obj.get_raw_data())
        out = {}
        for k in root.kids:
            if k.name == 'm_Enabled':
                out[k.name] = r.read(k); r.align(); continue
            out[k.name] = r.read(k)
        return out

    # --- hierarchy helpers -----------------------------------------------------------------------------------------
    def obj(self, assets, path_id):
        return self.files[assets].objects[path_id]

    def components(self, go_obj):
        """[(type or script class name, object reader)] of a GameObject (an ObjectReader)."""
        go = go_obj.read()
        f = go_obj.assets_file
        out = []
        for c in go.m_Component:
            o = f.objects.get(c.component.m_PathID)
            if o is None: continue
            out.append((self.script(o) or o.type.name, o))
        return out

    def children(self, go_obj):
        f = go_obj.assets_file
        tr = next(o for t, o in self.components(go_obj) if t in ('Transform', 'RectTransform')).read()
        return [f.objects[ch.read().m_GameObject.m_PathID] for ch in tr.m_Children]

    def child(self, go_obj, path):
        for name in path.split('/'):
            go_obj = next((c for c in self.children(go_obj) if c.read().m_Name == name), None)
            if go_obj is None: return None
        return go_obj

    def comp(self, go_obj, kind):
        return next((o for t, o in self.components(go_obj) if t == kind), None)

# --- PlayMaker -----------------------------------------------------------------------------------------------------
# ActionData keeps every action's parameters in parallel lists: paramDataType (HutongGames.PlayMaker.ParamDataType),
# paramName, and paramDataPos, an offset into byteData for value types or an index into the typed list for the rest.
PDT = ['Integer', 'Boolean', 'Float', 'String', 'Color', 'ObjectReference', 'LayerMask', 'Enum', 'Vector2', 'Vector3',
       'Vector4', 'Rect', 'Array', 'Character', 'AnimationCurve', 'FsmFloat', 'FsmInt', 'FsmBool', 'FsmString',
       'FsmGameObject', 'FsmOwnerDefault', 'FunctionCall', 'FsmAnimationCurve', 'FsmEvent', 'FsmObject', 'FsmColor',
       'Unsupported', 'GameObject', 'FsmVector3', 'LayoutOption', 'FsmRect', 'FsmEventTarget', 'FsmMaterial',
       'FsmTexture', 'Quaternion', 'FsmQuaternion', 'FsmProperty', 'FsmVector2', 'FsmTemplateControl', 'FsmVar',
       'CustomClass', 'FsmArray', 'FsmEnum']
_LISTS = {'String': 'stringParams', 'FsmString': 'fsmStringParams', 'FsmGameObject': 'fsmGameObjectParams',
          'FsmOwnerDefault': 'fsmOwnerDefaultParams', 'FsmObject': 'fsmObjectParams', 'ObjectReference': 'unityObjectParams',
          'FsmVar': 'fsmVarParams', 'FsmArray': 'fsmArrayParams', 'FsmEnum': 'fsmEnumParams', 'FsmEventTarget': 'fsmEventTargetParams',
          'FsmVector2': 'fsmVector2Params', 'FsmVector3': 'fsmVector3Params', 'FsmColor': 'fsmColorParams',
          'FsmRect': 'fsmRectParams', 'FsmQuaternion': 'fsmQuaternionParams', 'FunctionCall': 'functionCallParams',
          'FsmProperty': 'fsmPropertyParams', 'AnimationCurve': 'animationCurveParams',
          'FsmAnimationCurve': 'animationCurveParams', 'LayoutOption': 'layoutOptionParams',
          'FsmTemplateControl': 'fsmTemplateControlParams', 'FsmMaterial': 'fsmObjectParams', 'FsmTexture': 'fsmObjectParams'}

_LISTS0 = {'FsmFloat': 'fsmFloatParams', 'FsmInt': 'fsmIntParams', 'FsmBool': 'fsmBoolParams', 'FsmEvent': 'stringParams'}

def _fsmvar(raw, fmt):
    """byteData of FsmFloat/FsmInt/FsmBool: value, useVariable, variable name."""
    n = struct.calcsize(fmt)
    if len(raw) < n: return None
    v = struct.unpack_from('<' + fmt, raw, 0)
    v = v[0] if len(v) == 1 else v
    if len(raw) > n and raw[n]: return {'var': raw[n + 1:].decode('utf-8', 'replace'), 'value': v}
    return v

def _param(ad, kind, pos, size):
    bd = ad['byteData']
    if isinstance(bd, str): bd = ad['byteData'] = bytes.fromhex(bd)
    b = bd[pos:pos + size]
    # older actions (FSM dataVersion 2) keep Fsm* values in typed lists instead of byteData
    if size == 0 and kind in _LISTS0:
        lst = ad.get(_LISTS0[kind], [])
        if pos >= len(lst): return None
        v = lst[pos]
        if kind == 'FsmEvent': return v or None
        if isinstance(v, dict) and v.get('useVariable'): return {'var': v.get('name'), 'value': v.get('value')}
        return v.get('value') if isinstance(v, dict) else v
    if kind in ('Integer', 'Enum', 'LayerMask'): return struct.unpack_from('<i', b)[0] if size >= 4 else None
    if kind == 'Boolean': return bool(b[0]) if b else None
    if kind == 'Float': return struct.unpack_from('<f', b)[0] if size >= 4 else None
    if kind == 'FsmFloat': return _fsmvar(b, 'f')
    if kind == 'FsmInt': return _fsmvar(b, 'i')
    if kind == 'FsmBool': return _fsmvar(b, '?')
    if kind == 'FsmVector2' and size: return _fsmvar(b, '2f')
    if kind == 'FsmVector3' and size: return _fsmvar(b, '3f')
    if kind == 'FsmEvent': return b.decode('utf-8', 'replace') or None
    if kind == 'Vector2': return struct.unpack_from('<2f', b) if size >= 8 else None
    if kind == 'Vector3': return struct.unpack_from('<3f', b) if size >= 12 else None
    lst = _LISTS.get(kind)
    if lst and pos < len(ad.get(lst, [])):
        v = ad[lst][pos]
        if isinstance(v, dict) and 'value' in v and not v.get('useVariable'): return v['value']
        if isinstance(v, dict) and v.get('useVariable'): return {'var': v.get('name'), 'value': v.get('value')}
        return v
    return None

def actions(state):
    """[(action class short name, {param: value})] of one FsmState, in order."""
    ad = state['actionData']
    names, starts = ad['actionNames'], ad['actionStartIndex']
    types, pnames, poss, sizes = ad['paramDataType'], ad['paramName'], ad['paramDataPos'], ad['paramByteDataSize']
    out = []
    for i, nm in enumerate(names):
        a, e = starts[i], (starts[i + 1] if i + 1 < len(starts) else len(types))
        ps = {}
        j = a
        while j < e:
            kind = PDT[types[j]] if types[j] < len(PDT) else str(types[j])
            if kind == 'Array':
                n = ad['arrayParamSizes'][poss[j]] if poss[j] < len(ad['arrayParamSizes']) else 0
                items = []
                for k in range(j + 1, min(j + 1 + n, e)):
                    kk = PDT[types[k]]; items.append(_param(ad, kk, poss[k], sizes[k]))
                ps[pnames[j]] = items; j += 1 + n; continue
            ps[pnames[j]] = _param(ad, kind, poss[j], sizes[j])
            j += 1
        out.append((nm.rsplit('.', 1)[-1], ps))
    return out

def transitions(state):
    return [(t['fsmEvent']['name'], t['toState']) for t in state['transitions']]

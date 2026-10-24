"""2D Toolkit (tk2d) sprites and animations of Hollow Knight and Silksong, read with hk_unity. Read-only.

    tk2dSpriteCollectionData   spriteDefinitions: per sprite its quad (positions, in world units, vertices
                               bottom-left, bottom-right, top-left, top-right), its atlas uvs in the same vertex order
                               (a 'flipped' sprite is stored rotated in the atlas, which the uvs already encode), and
                               a material whose main texture is the atlas.
    tk2dSpriteAnimation        clips: name, fps, wrapMode (0 loop, 1 loop section from loopStart, 2 once, 4 ping
                               pong, 5 single frame) and frames, each a sprite of a collection plus a trigger event.
Sprites are drawn at the collection's texel size (64 px per unit for the Knight).
"""
from PIL import Image

class Sprites:
    def __init__(self, game):
        self.g = game
        self._coll, self._atlas, self._lib = {}, {}, {}

    def collection(self, pptr_or_obj, assets=None):
        obj = self._resolve(pptr_or_obj, assets)
        key = (obj.assets_file.name, obj.path_id)
        if key not in self._coll:
            d = self.g.mono(obj)
            d['_obj'] = obj
            self._coll[key] = d
        return self._coll[key]

    def library(self, pptr_or_obj, assets=None):
        obj = self._resolve(pptr_or_obj, assets)
        key = (obj.assets_file.name, obj.path_id)
        if key not in self._lib:
            d = self.g.mono(obj)
            d['_obj'] = obj
            d['byName'] = {c['name']: c for c in d['clips'] if c['name']}
            for c in d['clips']:          # a frame's collection reference is relative to the library's file
                for fr in c['frames']: fr['_src'] = obj
            self._lib[key] = d
        return self._lib[key]

    def _resolve(self, p, assets):
        if hasattr(p, 'get_raw_data'): return p
        return self.g.resolve(p, assets)

    def atlas(self, coll, material_id):
        mat_ptr = coll['materials'][material_id]
        obj = self._resolve(mat_ptr, coll['_obj'])
        key = (obj.assets_file.name, obj.path_id)
        if key not in self._atlas:
            mat = obj.read()
            tex = None
            for k, v in mat.m_SavedProperties.m_TexEnvs:
                if k == '_MainTex': tex = v.m_Texture
            img = self._resolve(tex, obj).read().image.convert('RGBA')
            self._atlas[key] = img.transpose(Image.FLIP_TOP_BOTTOM)   # uv y runs up
        return self._atlas[key]

    def sprite(self, coll, sprite_id):
        """(RGBA image, (x0, y1) world position of its top-left corner, units per pixel) of one sprite."""
        sd = coll['spriteDefinitions'][sprite_id]
        cache = sd.get('_img')
        if cache: return cache
        atlas = self.atlas(coll, sd['materialId'])
        P, U = sd['positions'], sd['uvs']
        tex = sd['texelSize']['x'] or 1 / 64
        x0, y0, x1, y1 = P[0]['x'], P[0]['y'], P[3]['x'], P[3]['y']
        W, H = max(1, round((x1 - x0) / tex)), max(1, round((y1 - y0) / tex))
        aw, ah = atlas.size
        # output pixel (i, j) (j down from the top) -> position -> uv -> atlas pixel (y down in the flipped atlas)
        u0, v0 = U[0]['x'] * aw, U[0]['y'] * ah
        du_x, dv_x = (U[1]['x'] - U[0]['x']) * aw / W, (U[1]['y'] - U[0]['y']) * ah / W
        du_y, dv_y = (U[2]['x'] - U[0]['x']) * aw / H, (U[2]['y'] - U[0]['y']) * ah / H
        # atlas row r = v (flipped atlas: v up becomes row down from the top of the flipped image)
        # output row j counts down from the top: position y = y1 - j, i.e. H - j steps up from the bottom
        a, b, c = du_x, -du_y, u0 + du_y * H
        d, e, f = dv_x, -dv_y, v0 + dv_y * H
        img = atlas.transform((W, H), Image.AFFINE, (a, b, c, d, e, f), resample=Image.NEAREST)
        sd['_img'] = (img, (x0, y1), tex)
        return sd['_img']

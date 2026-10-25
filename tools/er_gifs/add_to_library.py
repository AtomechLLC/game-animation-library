"""Add the Elden Ring, No Rest for the Wicked and Devil May Cry 3 renders from tools/er_gifs/render.js to library.json and gif-screening.json.

Each job in jobs.json with a rendered gifs/<out>.webp gets a `gifs` record on its entry (host "<game> render",
page_url = the move in Move Explorer). Safe to rerun: records already present (same local file) are skipped.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
jobs = json.load(open(os.path.join(HERE, 'jobs.json')))
fdata, mdata = {}, {}
fdOf = lambda g: fdata.get(g) or fdata.setdefault(g, {(m['class'], m['id']): m for m in json.load(open(os.path.join(ROOT, 'frame-data', g + '.json')))['moves']})
modelsOf = lambda g: mdata.get(g) or mdata.setdefault(g, json.load(open(os.path.join(ROOT, 'frame-data', 'models', g, 'models.json'))))
lib_path, scr_path = os.path.join(ROOT, 'library.json'), os.path.join(ROOT, 'gif-screening.json')
lib, scr = json.load(open(lib_path)), json.load(open(scr_path))
byid = {a['id']: a for a in lib['animations']}
added = 0
GAMES = {'elden-ring': 'Elden Ring', 'no-rest-for-the-wicked': 'No Rest for the Wicked', 'devil-may-cry-3': 'Devil May Cry 3'}
for j in jobs:
    gid = j.get('game', 'elden-ring')
    game = GAMES[gid]
    local = 'gifs/%s.webp' % j['out']
    if not os.path.exists(os.path.join(ROOT, local)):
        continue
    if j['class'] == 'Common':                                  # no frame-data row to link: the render itself
        title, page = '%s, rendered with the Frame Data 3D preview' % j['label'], local
    else:
        models = modelsOf(gid)
        weapon = j.get('weapon') or json.load(open(os.path.join(ROOT, 'frame-data', 'models', gid,
                                                                models['classes'][j['class']]['file'])))['moves'][j['move']]['weapon']
        move = fdOf(gid)[(j['class'], j['move'])]
        if gid == 'elden-ring':
            title = '%s %s (%s), rendered from the Frame Data 3D preview' % (j['class'], j['label'], weapon)
            page = 'move-explorer.html#c=%s&t=%s&m=%s' % (j['class'].replace(' ', '+'), move['type'], j['move'])
        else:                                                   # Devil May Cry 3: Dante's moves, linked with the game
            title = "Dante's %s (%s), rendered from the Frame Data 3D preview" % (j['label'], weapon)
            page = 'move-explorer.html#g=%s&c=%s&t=%s&m=%s' % (gid, j['class'], move['type'], j['move'])
    # `also` lists further entries that show the same render
    for entry in [re.sub(r'-(er|nr|dmc)\d+$', '', j['out'])] + j.get('also', []):
        a = byid[entry]
        if any(g.get('local') == local for g in a['gifs']):
            continue
        # first (and so the card's thumbnail) only where the entry has no solid clip yet; otherwise after the others
        solid = any(g.get('local') and (g.get('screened') or {}).get('confidence', 'high') == 'high'
                    and (g.get('screened') or {}).get('verdict', 'added') == 'added' for g in a['gifs'])
        a['gifs'].insert(len(a['gifs']) if solid else 0, {
            'page_url': page,
            'media_url': '', 'title': title, 'game': game, 'host': game + ' render', 'local': local, 'source_url': '',
            'screened': {'verdict': 'added', 'confidence': j.get('confidence', 'high'), 'what': j['what']},
        })
        scr['added'].append({'animation': entry, 'clip': j['out'], 'game': game, 'what': j['what'],
                             'confidence': j.get('confidence', 'high')})
        added += 1
json.dump(lib, open(lib_path, 'w'), indent=1, ensure_ascii=False)
json.dump(scr, open(scr_path, 'w'), indent=1, ensure_ascii=False)
print('added', added)

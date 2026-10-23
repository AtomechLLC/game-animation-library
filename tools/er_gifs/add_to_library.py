"""Add the Elden Ring renders from tools/er_gifs/render.js to library.json and gif-screening.json.

Each job in jobs.json with a rendered gifs/<out>.webp gets a `gifs` record on its entry (host "Elden Ring render",
page_url = the move in the Frame Data tab). Safe to rerun: records already present (same local file) are skipped.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
jobs = json.load(open(os.path.join(HERE, 'jobs.json')))
fd = json.load(open(os.path.join(ROOT, 'frame-data', 'elden-ring.json')))
moves = {(m['class'], m['id']): m for m in fd['moves']}
types = {t['id']: t['name'] for t in fd['moveTypes']}
models = json.load(open(os.path.join(ROOT, 'frame-data', 'models', 'elden-ring', 'models.json')))
lib_path, scr_path = os.path.join(ROOT, 'library.json'), os.path.join(ROOT, 'gif-screening.json')
lib, scr = json.load(open(lib_path)), json.load(open(scr_path))
byid = {a['id']: a for a in lib['animations']}
added = 0
for j in jobs:
    local = 'gifs/%s.webp' % j['out']
    if not os.path.exists(os.path.join(ROOT, local)):
        continue
    entry = j['out'].rsplit('-er', 1)[0]
    a, m = byid[entry], moves[(j['class'], j['move'])]
    if any(g.get('local') == local for g in a['gifs']):
        continue
    weapon = j.get('weapon') or json.load(open(os.path.join(ROOT, 'frame-data', 'models', 'elden-ring',
                                                            models['classes'][j['class']]['file'])))['moves'][j['move']]['weapon']
    title = '%s %s (%s), rendered from the Frame Data 3D preview' % (j['class'], j['label'], weapon)
    what = j['what']
    a['gifs'].insert(0, {
        'page_url': 'frame-data.html#c=%s&t=%s&m=%s' % (j['class'].replace(' ', '+'), m['type'], j['move']),
        'media_url': '', 'title': title, 'game': 'Elden Ring', 'host': 'Elden Ring render', 'local': local, 'source_url': '',
        'screened': {'verdict': 'added', 'confidence': j.get('confidence', 'high'), 'what': what},
    })
    scr['added'].append({'animation': entry, 'clip': j['out'], 'game': 'Elden Ring', 'what': what, 'confidence': j.get('confidence', 'high')})
    added += 1
json.dump(lib, open(lib_path, 'w'), indent=1, ensure_ascii=False)
json.dump(scr, open(scr_path, 'w'), indent=1, ensure_ascii=False)
print('added', added)

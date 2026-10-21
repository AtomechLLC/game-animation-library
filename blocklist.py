"""GIFs removed for good: the blocklist in gif-blocklist.json.

Removing a GIF on the review page (/admin) puts it on the site's blocklist. Export it from there (or pass --from with
the site's /api?action=blocklist URL) and this script merges it into gif-blocklist.json, then takes every matching GIF
out of library.json: it moves to the entry's rejected_gifs and its file is deleted from gifs/.

    python blocklist.py                                         apply gif-blocklist.json to library.json
    python blocklist.py --from https://YOUR-SITE/api?action=blocklist   (or a downloaded gif-blocklist.json) merge first

Any script that gathers GIFs should skip a candidate when blocked(gif, file_bytes) is true:

    from blocklist import load, blocked
    bl = load()
    if blocked(bl, {'page_url': page, 'media_url': media, 'source_url': src}, data): skip
"""
import hashlib, json, os, sys, urllib.request

FILE = 'gif-blocklist.json'


def load(path=FILE):
    """{'urls', 'hashes', 'entries'} from gif-blocklist.json (empty when it is missing). Same matching as lib/store.js:
    file URLs (media_url, source_url) and SHA-256, plus the page URL of a blocked GIF that had no file. Page URLs are
    otherwise not matched, since several Ultimate Frame Data GIFs share one character page."""
    try:
        entries = json.load(open(path, encoding='utf-8')).get('blocked', [])
    except FileNotFoundError:
        entries = []
    urls = {e[k] for e in entries for k in ('media_url', 'source_url') if e.get(k)}
    urls |= {e['page_url'] for e in entries if e.get('page_url') and not (e.get('media_url') or e.get('source_url') or e.get('sha256'))}
    hashes = {e['sha256'] for e in entries if e.get('sha256')}
    return {'urls': urls, 'hashes': hashes, 'entries': entries}


def blocked(bl, gif, data=None):
    """True when a GIF (dict with page_url / media_url / source_url / local) or its file bytes are on the blocklist."""
    if any(gif.get(k) in bl['urls'] for k in ('media_url', 'source_url', 'page_url') if gif.get(k)):
        return True
    if data is None and gif.get('local') and os.path.exists(gif['local']):
        data = open(gif['local'], 'rb').read()
    return data is not None and hashlib.sha256(data).hexdigest() in bl['hashes']


def merge(src):
    """Add the entries from a URL or file to gif-blocklist.json."""
    if src.startswith('http'):
        new = json.load(urllib.request.urlopen(src, timeout=30)).get('blocked', [])
    else:
        new = json.load(open(src, encoding='utf-8')).get('blocked', [])
    try:
        doc = json.load(open(FILE, encoding='utf-8'))
    except FileNotFoundError:
        doc = {'about': 'GIFs removed from the library for good.', 'blocked': []}
    ident = lambda e: e.get('key') or e.get('sha256') or e.get('page_url')
    have = {ident(e) for e in doc['blocked']}
    added = [e for e in new if ident(e) not in have]
    doc['blocked'].extend(added)
    json.dump(doc, open(FILE, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'{FILE}: {len(added)} new, {len(doc["blocked"])} in total')


def apply():
    bl = load()
    lib = json.load(open('library.json', encoding='utf-8'))
    removed = 0
    for a in lib['animations']:
        keep = []
        for g in a.get('gifs', []):
            if not blocked(bl, g):
                keep.append(g)
                continue
            if g.get('local') and os.path.exists(g['local']):
                os.remove(g['local'])
            g.pop('local', None)
            g['screened'] = {'verdict': 'blocklisted', 'confidence': 'high', 'what': 'Removed on the review page'}
            a.setdefault('rejected_gifs', []).append(g)
            removed += 1
            print('removed', a['id'], '|', g.get('title') or g.get('page_url'))
        a['gifs'] = keep
    json.dump(lib, open('library.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'{removed} blocklisted GIFs taken out of library.json')


if __name__ == '__main__':
    if '--from' in sys.argv:
        merge(sys.argv[sys.argv.index('--from') + 1])
    apply()

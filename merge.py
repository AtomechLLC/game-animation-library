import json,glob
d=json.load(open('index.json'))
refs={}
for f in sorted(glob.glob('refs*.json')):
    try: r=json.load(open(f))
    except Exception as e: print('bad',f,e); continue
    for k,v in r.items():
        seen={x['url'] for x in refs.get(k,[])}
        refs.setdefault(k,[]).extend(x for x in v if isinstance(x,dict) and x.get('url','').startswith('http') and x['url'] not in seen)
gifs={}
for f in sorted(glob.glob('gifs*.json')):
    try: r=json.load(open(f))
    except Exception as e: print('bad',f,e); continue
    for k,v in r.items():
        if not isinstance(v,dict): continue
        seen={x['url'] for x in refs.get(k,[])}
        refs.setdefault(k,[]).extend(x for x in v.get('references',[]) if isinstance(x,dict) and x.get('url','').startswith('http') and x['url'] not in seen)
        gs={x['page_url'] for x in gifs.get(k,[])}
        gifs.setdefault(k,[]).extend(x for x in v.get('gifs',[]) if isinstance(x,dict) and x.get('page_url','').startswith('http') and x['page_url'] not in gs)
import os
for a in d['animations']:
    a['references']=refs.get(a['id'],[])[:6]
    a['gifs']=gifs.get(a['id'],[])[:4]
    for i,g in enumerate(a['gifs']):
        for ext in ('gif','webp','mp4'):
            f=f"gifs/{a['id']}-{i}.{ext}"
            if os.path.exists(f): g['local']=f
json.dump(d,open('library.json','w'),indent=1,ensure_ascii=False)
n=sum(1 for a in d['animations'] if a['references']); t=sum(len(a['references']) for a in d['animations'])
print('gifs',sum(1 for a in d['animations'] if a['gifs']),sum(len(a['gifs']) for a in d['animations']));print('filled',n,'of',len(d['animations']),'links',t)
json.dump([{'id':a['id'],'name':a['name'],'example_games':a['example_games']} for a in d['animations'] if not a['references']],open('todo.json','w'),indent=0)
html=open('template.html').read().replace('__DATA__',json.dumps(d,ensure_ascii=False).replace('</','<\\/')).replace('__CONFIG__','{}')
open('atlas.html','w').write(html)

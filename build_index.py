import json,re,sys
cats=[];entries=[];cur=None
combat={'locomotion','melee','ranged','magic','defense','reactions','death','fighting','enemies','stealth','vfx','ui'}
for line in open(sys.argv[1]):
    line=line.rstrip('\n')
    if not line.strip(): continue
    if line.startswith('# CAT'):
        cid,name,desc=[s.strip() for s in line[5:].split('|')]
        cur=cid;cats.append({'id':cid,'name':name,'description':desc,'domain':'combat' if cid in combat else 'non-combat'});continue
    name,sub,tags,games,desc,*also=[s.strip() for s in line.split('|')]
    slug=re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-')
    entries.append({'id':f'{cur}.{slug}','name':name,'category':cur,'subcategory':sub,
      'tags':[t.strip() for t in tags.split(',')],'example_games':[g.strip() for g in games.split(';')],
      'description':desc,'search_query':f'{name} animation video game','references':[]})
    if also and also[0]: entries[-1]['also']=[c.strip() for c in also[0].split(',')]
ids=[e['id'] for e in entries];assert len(ids)==len(set(ids))
json.dump({'categories':cats,'animations':entries},open(sys.argv[2],'w'),indent=1)
print(len(cats),len(entries))

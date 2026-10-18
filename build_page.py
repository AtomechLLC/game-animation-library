import json,sys
# Renders template.html with library.json into a standalone page (default: index.html)
out=sys.argv[1] if len(sys.argv)>1 else 'index.html'
d=json.load(open('library.json',encoding='utf-8'))
html=open('template.html',encoding='utf-8').read().replace('__DATA__',json.dumps(d,ensure_ascii=False).replace('</',r'<\/'))
open(out,'w',encoding='utf-8').write(html)
print('wrote',out,len(d['animations']),'animations')

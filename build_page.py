import json,os,sys
# Renders template.html with library.json into a standalone page (default: action-atlas.html, the Action Atlas app).
# LIBRARY_API_URL (optional) points the page at a deployed /api so the static copy gets voting and suggestions too.
def render(cfg):
    d=json.load(open('library.json',encoding='utf-8'))
    dump=lambda o:json.dumps(o,ensure_ascii=False).replace('</',r'<\/')
    html=open('template.html',encoding='utf-8').read().replace('__DATA__',dump(d)).replace('__CONFIG__',dump(cfg))
    return html,len(d['animations'])
if __name__=='__main__':
    out=sys.argv[1] if len(sys.argv)>1 else 'action-atlas.html'
    api=os.environ.get('LIBRARY_API_URL','').strip()
    html,n=render({'api':api} if api else {})
    open(out,'w',encoding='utf-8').write(html)
    print('wrote',out,n,'animations')

"""Local review copy of the atlas for the owner's workstation.

    python serve_local.py            # then open http://localhost:8765
    python serve_local.py 9000       # another port

Every GIF and entry gets a "✕ Mark" button. Marks are saved to marks.json in this folder,
so a later Claude thread can search for better images for exactly those entries.
Listens on 127.0.0.1 only.
"""
import http.server, json, os, sys
from build_page import render

ROOT = os.path.dirname(os.path.abspath(__file__))
MARKS = os.path.join(ROOT, 'marks.json')

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def send_body(self, code, body, ctype):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            html, _ = render({'local': True, 'marks': 'marks.json'})
            return self.send_body(200, html.encode('utf-8'), 'text/html; charset=utf-8')
        if path == '/marks.json':
            body = open(MARKS, 'rb').read() if os.path.exists(MARKS) else b'{"marks": []}'
            return self.send_body(200, body, 'application/json')
        if not (path.startswith('/gifs/') or path == '/library.json'):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if self.path.split('?')[0] != '/marks.json':
            return self.send_error(404)
        # Only accept writes from the page this server rendered
        origin = self.headers.get('Origin', '')
        if origin and origin not in (f'http://localhost:{PORT}', f'http://127.0.0.1:{PORT}'):
            return self.send_error(403)
        try:
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            marks = [m for m in data.get('marks', []) if isinstance(m, dict) and m.get('animation')]
        except Exception:
            return self.send_error(400)
        marks.sort(key=lambda m: (m['animation'], m.get('gif', '')))
        with open(MARKS, 'w', encoding='utf-8') as f:
            json.dump({'marks': marks}, f, indent=1, ensure_ascii=False)
            f.write('\n')
        self.send_body(200, b'{"ok": true}', 'application/json')

if __name__ == '__main__':
    os.chdir(ROOT)
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f'Local atlas on http://localhost:{PORT}  (marks are saved to {MARKS})')
    http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()

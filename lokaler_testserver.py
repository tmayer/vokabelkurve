# Lokaler Testserver: liefert webspace/ aus und bildet api/decks.php und api/progress.php nach (ohne die Prüfungen der PHP-Fassung).
# Start: python3 lokaler_testserver.py webspace testdaten  ->  http://localhost:8765  (anderer Port: VK_PORT=8768 python3 …)
import hashlib, json, os, re, sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

ROOT = sys.argv[1]
DATA = sys.argv[2]
os.makedirs(DATA, exist_ok=True)
cfg = open(os.path.join(ROOT, 'api', 'config.php')).read()
HASH = sys.argv[3] if len(sys.argv) > 3 else re.search(r"VK_TOKEN_HASH = '([0-9a-f]+)'", cfg).group(1)

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def j(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def auth(self):
        t = self.headers.get('X-VK-Token', '')
        return len(t) >= 20 and hashlib.sha256(t.encode()).hexdigest() == HASH

    def do_GET(self):
        p = urlparse(self.path).path
        if p == '/api/decks.php':
            d = os.path.join(ROOT, 'decks')
            out = [{'file': f, 'size': os.path.getsize(os.path.join(d, f)), 'mtime': 0}
                   for f in sorted(os.listdir(d)) if re.search(r'\.(csv|tsv|txt)$', f)]
            return self.j(200, {'decks': out})
        if p == '/api/progress.php':
            if not self.auth():
                return self.j(401, {'error': 'Geräteschlüssel fehlt oder ist falsch'})
            decks = {}
            for f in os.listdir(DATA):
                m = re.match(r'progress-([a-z0-9-]+)\.json$', f)
                if m:
                    decks[m.group(1)] = json.load(open(os.path.join(DATA, f)))
            st = json.load(open(os.path.join(DATA, 'settings.json'))) if os.path.exists(os.path.join(DATA, 'settings.json')) else {}
            return self.j(200, {'settings': st, 'decks': decks})
        if p.startswith('/data/') or p.endswith('config.php'):
            return self.j(403, {'error': 'verboten'})
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != '/api/progress.php':
            return self.j(404, {})
        if not self.auth():
            return self.j(401, {'error': 'Geräteschlüssel fehlt oder ist falsch'})
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        if 'settings' in body:
            json.dump(body['settings'], open(os.path.join(DATA, 'settings.json'), 'w'))
        if 'deck' in body:
            f = os.path.join(DATA, 'progress-%s.json' % body['deck'])
            if body.get('reset'):
                if os.path.exists(f):
                    os.remove(f)
            elif 'cards' in body:
                cards = json.load(open(f)) if os.path.exists(f) else {}
                for k, c in body['cards'].items():
                    if c is None:
                        cards.pop(k, None)
                    else:
                        cards[k] = c
                json.dump(cards, open(f, 'w'))
        return self.j(200, {'ok': True})

    def end_headers(self):
        # Browser sollen jedes Mal nachfragen, ob es eine neuere Fassung gibt (sonst zeigt Safari oft eine alte Version)
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, *a):
        pass

ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('VK_PORT', '8765'))), H).serve_forever()

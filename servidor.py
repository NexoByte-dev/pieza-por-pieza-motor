#!/usr/bin/env python3
"""Servidor local del estudio. Sirve los archivos y, en modo terminal, recibe el MP4 renderizado.
Uso: python3 servidor.py [PUERTO] [CARPETA_SALIDA]  (lo usan abrir_estudio.command y renderizar.sh)"""
import http.server, os, sys, urllib.parse, threading
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
OUT = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else 'salida')
os.makedirs(OUT, exist_ok=True)

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/api/videos':                      # lista los videos: videos/<id>/video.json
            import json, glob
            vs = []
            for f in sorted(glob.glob('videos/*/video.json')):
                v = json.load(open(f)); v['id'] = os.path.basename(os.path.dirname(f)); vs.append(v)
            vs.sort(key=lambda v: (v.get('orden', 999), v['id']))
            b = json.dumps(vs, ensure_ascii=False).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers()
            self.wfile.write(b); return
        if u.path == '/aviso':
            print(urllib.parse.parse_qs(u.query).get('m', [''])[0], flush=True); return self._ok()
        if u.path == '/fin':
            self._ok(); threading.Thread(target=srv.shutdown).start(); return
        return super().do_GET()
    def do_PUT(self):
        name = os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(self.path).path))
        n = int(self.headers['Content-Length']); left = n
        with open(os.path.join(OUT, name), 'wb') as f:
            while left: chunk = self.rfile.read(min(left, 1 << 20)); f.write(chunk); left -= len(chunk)
        self._ok()
    def _ok(self):
        self.send_response(200); self.send_header('Content-Length', '0'); self.end_headers()

os.chdir(os.path.dirname(os.path.abspath(__file__)))
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
srv.serve_forever()

from asset_paths import ASSETS
"""Read-only loopback server for the user's offline AniimoTools copy."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import threading


class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def end_headers(self):
        self.send_header('Content-Security-Policy',"default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self' data:; object-src 'none'; frame-src 'none'")
        super().end_headers()


def serve():
    folder=ASSETS/'simulator'
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(folder)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server,f'http://127.0.0.1:{server.server_port}/index.html'

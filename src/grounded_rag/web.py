"""A localhost demonstration server, not a public production service."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import threading
from urllib.parse import urlsplit

from .gemini import ProviderError


def make_handler(assistant):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data, content_type='application/json; charset=utf-8'):
            raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/':
                self.reply(200, files('grounded_rag').joinpath('static/index.html').read_bytes(), 'text/html; charset=utf-8')
            elif path == '/health':
                self.reply(200, {'status': 'ok', 'mode': assistant.mode, 'chunks': len(assistant.chunks),
                                 'documents': len({c.source for c in assistant.chunks})})
            else:
                self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            if self.path != '/api/ask':
                self.reply(404, {'error': 'Not found'})
                return
            # No CORS. Reject browser requests originating from another site.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                self.reply(403, {'error': 'Cross-origin requests are not accepted'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16000:
                    raise ValueError('Invalid request size')
                if 'application/json' not in self.headers.get('Content-Type', ''):
                    raise ValueError('Use application/json')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Expected a JSON object')
                if not lock.acquire(blocking=False):
                    self.reply(429, {'error': 'A query is already running; retry shortly'})
                    return
                try:
                    result = assistant.ask(payload.get('question'))
                finally:
                    lock.release()
                self.reply(200, result)
            except (ValueError, json.JSONDecodeError, UnicodeError) as exc:
                self.reply(400, {'error': str(exc)})
            except ProviderError as exc:
                self.reply(502, {'error': str(exc)})

        def log_message(self, *_):
            # Avoid writing users' questions to request logs.
            pass

    return Handler


def serve(assistant, host='127.0.0.1', port=8765):
    server = ThreadingHTTPServer((host, port), make_handler(assistant))
    print(f'Local demo: http://{host}:{port} (mode={assistant.mode})', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

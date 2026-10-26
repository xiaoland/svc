"""Disposable loopback service controlled through HTTP, never historical PIDs."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["serve", "probe", "stop"])
parser.add_argument("--port", type=int, default=0)
args = parser.parse_args()
port_file = Path("port.json")

if args.action == "serve":
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"SVC macOS acceptance fixture")

        def do_POST(self):
            self.send_response(200)
            self.end_headers()
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *args):
            print(args, flush=True)

    with HTTPServer(("127.0.0.1", args.port), Handler) as server:
        port_file.write_text(json.dumps(server.server_port))
        print("SVC fixture ready", flush=True)
        server.serve_forever()
else:
    port = json.loads(port_file.read_text())
    request = Request(f"http://127.0.0.1:{port}/", method="POST" if args.action == "stop" else "GET")
    with urlopen(request, timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)

"""Drive one real native terminal with fixed local Responses frames; no real model."""
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import tempfile
import threading
import time
from svc_cli.activity.harness.providers import CodexProvider
from svc_cli.activity.harness.service import identity, terminate
from svc_cli.activity.harness.install import setup
from svc_cli.activity.harness.transport import CodexClient

cli = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'
lab = '/Volumes/WorkSSD/Development/svc-dev-lab'
command = "/usr/bin/python3 -u -c 'import time; print(\"SVC native Codex acceptance\", flush=True); time.sleep(20)'"
requests = []
def completed(key):
    return {'type': 'response.completed', 'response': {'id': key, 'usage': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}}}
class ResponseFrames(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        number = len(requests)
        requests.append(self.path)
        key = f'svc-response-{number}'
        item = ({'type': 'function_call', 'call_id': 'svc-bounded-terminal', 'name': 'exec_command',
            'arguments': json.dumps({'cmd': command, 'workdir': lab, 'yield_time_ms': 10, 'max_output_tokens': 100})}
            if number == 0 else {'type': 'message', 'role': 'assistant', 'id': 'svc-finished',
                'content': [{'type': 'output_text', 'text': 'done'}]})
        frames = [{'type': 'response.created', 'response': {'id': key}},
            {'type': 'response.output_item.done', 'item': item}, completed(key)]
        body = ''.join('event: ' + x['type'] + '\ndata: ' + json.dumps(x) + '\n\n' for x in frames).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *_):
        pass

with tempfile.TemporaryDirectory(prefix='svc-cx-', dir='/tmp') as temporary:
    root = Path(temporary)
    endpoint = root / 'control.sock'
    codex_home = root / 'codex'
    codex_home.mkdir(mode=0o700)
    os.environ['SVC_HARNESS_HOME'] = str(root / 'harness')
    responder = ThreadingHTTPServer(('127.0.0.1', 0), ResponseFrames)
    worker = threading.Thread(target=responder.serve_forever, daemon=True)
    worker.start()
    (codex_home / 'config.toml').write_text(f'''model = "gpt-5"
model_provider = "svc_acceptance"
approval_policy = "never"
sandbox_mode = "danger-full-access"
[model_providers.svc_acceptance]
name = "SVC finite local response replay"
base_url = "http://127.0.0.1:{responder.server_port}/v1"
wire_api = "responses"
request_max_retries = 0
stream_max_retries = 0
supports_websockets = false
''')
    with (root / 'server.err').open('w+') as errors:
        server = subprocess.Popen([cli, 'app-server', '--listen', f'unix://{endpoint}'], cwd=codex_home,
            env={**os.environ, 'CODEX_HOME': str(codex_home), 'CODEX_API_KEY': 'svc-local-replay-not-a-secret'},
            stdout=subprocess.DEVNULL, stderr=errors)
        try:
            deadline = time.monotonic() + 6
            while not endpoint.exists() and server.poll() is None and time.monotonic() < deadline:
                time.sleep(.1)
            if not endpoint.exists():
                errors.seek(0)
                raise RuntimeError(errors.read())
            endpoint.resolve().chmod(0o600)
            setup('codex', socket_path=str(endpoint))
            with CodexClient(endpoint.resolve(), timeout=6) as owner:
                value = owner.call('thread/start', {'cwd': lab, 'ephemeral': True})
                thread = value['thread']['id']
                owner.call('turn/start', {'threadId': thread, 'input': [{'type': 'text', 'text': 'Run the fixed local acceptance command', 'textElements': []}]})
                provider = CodexProvider(endpoint)
                item = None
                deadline = time.monotonic() + 8
                while item is None and time.monotonic() < deadline:
                    item = next((x for x in provider.executions() if json.loads(x.native_id)[0] == thread), None)
                    if item is None:
                        time.sleep(.2)
                if item is None:
                    raise RuntimeError('fixed native exec_command did not create a background terminal')
                receipt = terminate(identity(item), force=False, by='human')
                deadline = time.monotonic() + 3
                while any(x.native_id == item.native_id for x in provider.executions()) and time.monotonic() < deadline:
                    time.sleep(.1)
                if any(x.native_id == item.native_id for x in provider.executions()):
                    raise RuntimeError('native terminal remains after terminate acknowledgement')
                completion = False
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        event = json.loads(owner.connection.recv(timeout=deadline - time.monotonic()))
                    except TimeoutError:
                        break
                    if event.get('method') == 'item/completed' and event.get('params', {}).get('item', {}).get('type') == 'commandExecution':
                        completion = True
                        break
                print(json.dumps({'provider': 'codex', 'separateNativeServer': True, 'realModelRequests': 0,
                    'localResponseRequests': len(requests), 'nativeList': True,
                    'nativeTerminateAcknowledged': receipt.status == 'requested', 'terminalRemoved': True,
                    'originalConnectionObservedCommandCompletion': completion, 'desktopAttached': False}))
        finally:
            errors.flush(); errors.seek(0); Path('/tmp/svc-codex-server-errors.txt').write_text(errors.read())
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    server.kill()
            server.wait(timeout=3)
            responder.shutdown(); responder.server_close(); worker.join(timeout=1)

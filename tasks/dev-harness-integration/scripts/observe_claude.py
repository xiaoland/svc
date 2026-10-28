"""Launch an isolated idle native background session, inspect, then stop its exact id."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from svc_cli.activity.harness.providers import ClaudeProvider
from svc_cli.activity.harness.service import identity, logs, terminate

cli = '/opt/homebrew/bin/claude'
lab = '/Volumes/WorkSSD/Development/svc-dev-lab'
with tempfile.TemporaryDirectory(prefix='svc-cl-', dir='/tmp') as temporary:
    # Native state is isolated, including daemon roster. No user conversation or secret is read.
    os.environ['CLAUDE_CONFIG_DIR'] = temporary
    os.environ['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'] = '1'
    (Path(temporary) / '.claude.json').write_text(json.dumps({'hasCompletedOnboarding': True, 'theme': 'dark', 'projects': {lab: {'hasTrustDialogAccepted': True}}}))
    process = None
    native = None
    try:
        result = subprocess.run([cli, '--bg', '--bare', '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}'],
            cwd=lab, stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=12)
        if result.returncode:
            raise RuntimeError(result.stderr[:1500])
        provider = ClaudeProvider(cli)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            items = provider.executions()
            native = next((x for x in items if x.scope == 'session' and x.can_terminate), None)
            if native:
                break
            time.sleep(.2)
        if native is None:
            raise RuntimeError('isolated native session not published: ' + result.stdout[:500])
        text = logs(identity(native))
        receipt = terminate(identity(native), force=False, by='human')
        deadline = time.monotonic() + 5
        while any(x.can_terminate for x in provider.executions()) and time.monotonic() < deadline:
            time.sleep(.2)
        still_running = any(x.native_id == native.native_id and x.can_terminate for x in provider.executions())
        if still_running:
            raise RuntimeError('native stop did not stop own idle session')
        print(json.dumps({'provider': 'claude', 'isolatedNativeState': True, 'inferenceRequests': 0,
            'nativeList': True, 'nativeLogs': isinstance(text.text, str), 'nativeStop': receipt.status,
            'scope': native.scope, 'ownSessionStopped': True}))
    finally:
        if native is not None:
            subprocess.run([cli, 'stop', native.native_id], capture_output=True, timeout=10)

"""Exercise the actual installed Pi registry/Host API through the shipped bridge."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import sys

from svc_cli.activity.harness.providers import PiProvider
from svc_cli.activity.harness.service import collect, logs, resolve, terminate
from svc_cli.activity.harness.transport import unix_request
from svc_cli.errors import SvcError
from svc_cli._execution import ExecutionStore
from svc_cli.activity.monitor import monitor
from svc_cli.activity.usage import UsageSampler
from svc_cli.activity.darwin import DarwinMetrics
from svc_cli.cli_output.activity import project_monitor

root = Path(__file__).resolve().parents[3]
package = Path.home() / '.pi/agent/npm/node_modules/pi-background-tasks'
lab = Path('/Volumes/WorkSSD/Development/svc-dev-lab')
with tempfile.TemporaryDirectory(prefix='svc-pi-', dir='/tmp') as temporary:
    directory = Path(temporary)
    harness = directory / 'h'
    os.environ['SVC_HARNESS_HOME'] = str(harness)
    os.environ['CLAUDE_CONFIG_DIR'] = str(directory / 'claude')
    ready = directory / 'ready.json'
    with (directory / 'host.stderr').open('w+') as errors:
        process = subprocess.Popen(['node', str(Path(__file__).with_name('pi-host.mjs')), str(package),
            str(root / 'cli/src/svc_cli/data/integrations/pi-extension.ts'), str(lab), str(ready)],
            stdout=subprocess.DEVNULL, stderr=errors)
        try:
            deadline = time.monotonic() + 8
            while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(.1)
            if not ready.exists():
                errors.seek(0)
                raise RuntimeError(errors.read())
            snapshot = collect((lab,))
            recorded = project_monitor(monitor(store=ExecutionStore(directory / 'executions'), project_roots=(lab,)))
            (root / 'tasks/dev-harness-integration/evidence/owned-pi-monitor.json').write_text(recorded.model_dump_json() + '\n')
            item = next(x for x in snapshot.executions if x.provider == 'pi')
            if not (item.can_terminate and item.project_path == str(lab)):
                raise RuntimeError('native Pi task not controllable/project assigned')
            deadline = time.monotonic() + 3
            text = ''
            while 'SVC native Pi acceptance' not in text and time.monotonic() < deadline:
                text = logs(item.execution_id).text
                time.sleep(.1)
            if 'SVC native Pi acceptance' not in text:
                raise RuntimeError('native logs absent')
            sampler = UsageSampler(DarwinMetrics())
            sampler.prepare_external('same-physical-root-a', item.process_id, process.pid)
            sampler.prepare_external('same-physical-root-b', item.process_id, process.pid)
            time.sleep(.05)
            measured = sampler.finish()
            physical_roots = sum(x is not None for x in measured.values())
            if physical_roots != 1:
                raise RuntimeError('same physical root was accounted more than once')
            descriptor = next(harness.glob('pi-*.json'))
            provider = PiProvider(descriptor)
            wrong_token_rejected = False
            try:
                unix_request(provider.path, {'version': 1, 'instance': provider.activation,
                    'token': '0' * 64, 'operation': 'list'})
            except SvcError:
                wrong_token_rejected = True
            if not wrong_token_rejected:
                raise RuntimeError('bridge accepted wrong secret')
            native_client = os.environ.get('SVC_ACCEPTANCE_SWIFT_CLIENT')
            client_observation = None
            if native_client:
                result = subprocess.run([native_client, '--live', str(Path(sys.executable).parent / 'svc')], capture_output=True, text=True, timeout=12, check=True)
                client_observation = json.loads(result.stdout)
                receipt_status = 'requested'
            else:
                receipt_status = terminate(item.execution_id, force=False, by='human').status
            terminal = next(x for x in collect((lab,)).executions if x.provider == 'pi')
            if terminal.state != 'stopped' or terminal.can_terminate:
                raise RuntimeError('native registry did not settle task stop')
            old_id = item.execution_id
            process.send_signal(signal.SIGUSR1)
            deadline = time.monotonic() + 3
            while descriptor.exists() and time.monotonic() < deadline:
                time.sleep(.05)
            stale_rejected = False
            try:
                resolve(old_id)
            except SvcError:
                stale_rejected = True
            if not stale_rejected:
                raise RuntimeError('old activation id was accepted')
            print(json.dumps({'provider': 'pi', 'actualRegistryVersion': '2.6.10',
                'nativeList': True, 'nativeLogs': True, 'projectAssigned': True,
                'wrongTokenRejected': wrong_token_rejected, 'nativeStopState': terminal.state, 'duplicatePhysicalRootsCounted': physical_roots,
                'reloadInvalidatedIdentity': stale_rejected, 'receipt': receipt_status, 'appClient': client_observation}, ensure_ascii=False))
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=8)

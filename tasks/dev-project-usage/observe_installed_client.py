"""Observe the product Foundation client against one bounded lab execution."""
import json
from pathlib import Path
import re
import subprocess
import time

root = Path(__file__).resolve().parent
evidence = root / 'evidence'
cli = json.loads((evidence / 'runtime.json').read_text())['runtime']
lab = Path('/Volumes/WorkSSD/Development/svc-dev-lab')
with (evidence / 'client-owner.stderr').open('w+') as errors:
    owner = subprocess.Popen([cli, 'dev', 'exec', '--project', str(lab), '--cwd', str(lab),
        '--source', 'agent', '--label', 'svc-dev-lab 客户端终止验收', '--json', '--',
        '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3', str(lab / 'runner.py'),
        'work', '--duration', '30'], stdout=subprocess.PIPE, stderr=errors, text=True)
    try:
        execution_id = None
        for _ in range(40):
            errors.seek(0)
            match = re.search(r'svc execution: ([a-f0-9-]+)', errors.read())
            if match:
                execution_id = match[1]
                break
            if owner.poll() is not None:
                raise RuntimeError('lab owner exited before publication')
            time.sleep(0.1)
        if not execution_id:
            raise RuntimeError('lab publication timed out')
        result = subprocess.run(['/tmp/svc-observe-project-client', cli,
            str(evidence / 'live-monitor.json'), '--terminate', execution_id],
            text=True, capture_output=True, timeout=15, check=True)
        (evidence / 'client.json').write_text(result.stdout)
        output, _ = owner.communicate(timeout=10)
        outcome = json.loads(output)
        (evidence / 'client-owner.json').write_text(json.dumps({'processExitCode': owner.returncode,
            'result': outcome}, ensure_ascii=False, indent=2) + '\n')
        print(result.stdout)
        print(json.dumps({'processExitCode': owner.returncode, 'result': outcome}))
    finally:
        if owner.poll() is None:
            # The fixture expires by itself; do not kill the CLI owner or any unrelated process.
            owner.communicate(timeout=35)

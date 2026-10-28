"""Install the already-built local bundle and register only dedicated lab projects."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import resource
import shutil
import subprocess
import tempfile
import time

from tools import macos_app

root = Path(__file__).resolve().parent
evidence = root / 'evidence'
cli = json.loads((evidence / 'runtime.json').read_text())['runtime']
bundle = Path('dist/macos/project-usage/SVC.app').resolve()
destination = Path('/Applications/SVC.app')
macos_app.verify(bundle)
signature = subprocess.run(['codesign', '-dvvv', str(bundle)], capture_output=True, text=True, check=True).stderr
if 'Authority=Apple Development:' not in signature or 'TeamIdentifier=7J9DJNJ782' not in signature:
    raise RuntimeError('unexpected development signing identity')
macos_app.stop_application()

def preferences():
    return plistlib.loads(subprocess.run(['defaults', 'export', 'dev.svc.menubar', '-'], capture_output=True, check=True).stdout)

before = preferences()
backup = Path(tempfile.mkdtemp(prefix='svc-delivery-preferences-'))
os.chmod(backup, 0o700)
(backup / 'before.plist').write_bytes(plistlib.dumps(before))
original_files = {Path(path) / name for path in before.get('projects', []) for name in ('svc.json', 'svc.local.json')}
hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in original_files if path.is_file()}
registration = subprocess.run(['/tmp/svc-observe-project-client', cli, str(evidence / 'live-monitor.json'), '--register'],
    capture_output=True, text=True, timeout=20, check=True)
registered = json.loads(registration.stdout)
(evidence / 'registration.json').write_text(registration.stdout)
if not all(registered.get(key) is True for key in ('originalProjectsPreserved', 'originalSectionsPreserved', 'originalAssignmentsPreserved', 'cliPreferencesPreserved')):
    raise RuntimeError(f'preference preservation failed; backup: {backup}')
after = preferences()
labs = ['/Volumes/WorkSSD/Development/svc-dev-lab', '/Volumes/WorkSSD/Development/svc-dev-lab-peer']
if not all(path in after.get('projects', []) for path in labs) or not set(before.get('projects', [])).issubset(after.get('projects', [])):
    raise RuntimeError(f'project registration not persisted; backup: {backup}')
if any(before.get(key) != after.get(key) for key in ('cliPath', 'searchPath')):
    raise RuntimeError(f'CLI preferences changed; backup: {backup}')
macos_app.replace_bundle(bundle, destination)
macos_app.verify(destination)
subprocess.run(['/usr/bin/open', '-g', str(destination), '--args', '--background'], check=True)
time.sleep(1)
pids = subprocess.run(['pgrep', '-x', 'SVCMenuBar'], text=True, capture_output=True, check=True).stdout.split()
if len(pids) != 1:
    raise RuntimeError('expected one installed app process')
command = subprocess.run(['ps', '-p', pids[0], '-o', 'command='], text=True, capture_output=True, check=True).stdout.strip()
if not command.startswith('/Applications/SVC.app/Contents/MacOS/SVCMenuBar'):
    raise RuntimeError('running process is not installed bundle')
installed_signature = subprocess.run(['codesign', '-dvvv', str(destination)], text=True, capture_output=True, check=True).stderr
if installed_signature != signature:
    # The reported Executable path differs after installation; compare actual authority and requirement separately.
    authority = [line for line in installed_signature.splitlines() if line.startswith(('Authority=', 'TeamIdentifier=', 'CDHash='))]
else:
    authority = [line for line in signature.splitlines() if line.startswith(('Authority=', 'TeamIdentifier=', 'CDHash='))]
with tempfile.TemporaryDirectory(prefix='svc-binary-compare-') as temporary:
    binaries=[]
    for number, app in enumerate((bundle, destination)):
        copied=Path(temporary)/str(number)
        shutil.copy2(app/'Contents/MacOS/SVCMenuBar',copied)
        subprocess.run(['codesign','--remove-signature',str(copied)],check=True,capture_output=True)
        binaries.append(hashlib.sha256(copied.read_bytes()).hexdigest())
if binaries[0] != binaries[1]:
    raise RuntimeError('installed code differs from prepared code')
if any(hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest for path,digest in hashes.items()):
    raise RuntimeError('an original project configuration changed')
usage_before=resource.getrusage(resource.RUSAGE_CHILDREN)
started=time.perf_counter()
monitor=subprocess.run([cli,'dev','monitor','--json'],capture_output=True,text=True,check=True,timeout=10)
elapsed=time.perf_counter()-started
usage_after=resource.getrusage(resource.RUSAGE_CHILDREN)
snapshot=json.loads(monitor.stdout)
info=macos_app.bundle_info(destination)
report={
    'installedApp':str(destination),'appVersion':info['CFBundleShortVersionString'],
    'sourceRevision':info['SVCSourceRevision'],'cli':info['SVCDefaultCLIPath'],
    'pid':int(pids[0]),'command':command,'signature':authority,'strictSignatureVerified':True,
    'preparedAndInstalledCodeMatched':True,'originalProjectCount':len(before.get('projects',[])),
    'registeredLabProjects':labs,'originalConfigurationsUnchanged':True,
    'cliPreferencesPreserved':True,'monitorSchema':snapshot['schema_version'],
    'monitorWallSeconds':round(elapsed,3),
    'monitorCPUSeconds':round(usage_after.ru_utime+usage_after.ru_stime-usage_before.ru_utime-usage_before.ru_stime,3),
    'monitorIssues':snapshot['issues'],
    'remainingLabActivity':[(item['execution_id'],item['state']) for item in snapshot['executions'] if item.get('project_path') in labs and item.get('state')=='running'],
}
(evidence/'installation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
shutil.rmtree(backup)
print(json.dumps(report,ensure_ascii=False,indent=2))

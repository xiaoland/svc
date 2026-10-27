"""Record a local installation without exporting private preference contents."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

root=Path(sys.argv[1]); phase=sys.argv[2]
repo=Path(__file__).resolve().parents[3]
def call(*argv):return subprocess.check_output(argv,text=True).strip()
info=plistlib.loads(Path('/Applications/SVC.app/Contents/Info.plist').read_bytes())
cli=Path(info['SVCDefaultCLIPath'])
before=plistlib.loads((root/'preferences-before.plist').read_bytes())
after=plistlib.loads(subprocess.check_output(['defaults','export','dev.svc.menubar','-']))
projects=json.loads((root/'project-digests-before.json').read_text())
package=Path(call(str(cli.parent/'python'),'-c','import svc_cli; print(next(iter(svc_cli.__path__)))'))
files=[p for p in (repo/'cli/src/svc_cli').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
mismatch=[str(p.relative_to(repo)) for p in files if not(package/p.relative_to(repo/'cli/src/svc_cli')).is_file() or p.read_bytes()!=(package/p.relative_to(repo/'cli/src/svc_cli')).read_bytes()]
subprocess.run(['codesign','--verify','--strict','/Applications/SVC.app'],check=True)
signing=subprocess.run(['codesign','-dv','--verbose=4','/Applications/SVC.app'],capture_output=True,text=True,check=True).stderr
report={'phase':phase,'app_version':info['CFBundleShortVersionString'],'source_revision':info['SVCSourceRevision'],'build_profile':info['SVCBuildProfile'],'bundle_id':info['CFBundleIdentifier'],'cli_path':str(cli),'cli_version':call(str(cli),'--version'),'wheel_sha256':(cli.parent.parent/'.svc-wheel-sha256').read_text().strip(),'schema_versions':{command:json.loads(call(str(cli),'dev',command,'--json-schema'))['x-svc-result-schema-version'] for command in ['list','status','act','reconcile']},'all_preferences_preserved':before==after,'project_count':len(after.get('projects',[])),'projects_and_cli_preferences_preserved':all(before.get(k)==after.get(k) for k in ['projects','cliPath','searchPath']),'project_configuration_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in projects.items()),'cli_source_file_count':len(files),'cli_source_mismatches':mismatch,'signature_valid':True,'apple_development_identity':'Authority=Apple Development:' in signing,'hardened_runtime':'runtime' in signing,'team_id':next((line.split('=',1)[1] for line in signing.splitlines() if line.startswith('TeamIdentifier=')),None),'running_processes':call('ps','-p',call('pgrep','-x','SVCMenuBar').replace('\n',','),'-o','pid=,command=')}
(root/(phase+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))

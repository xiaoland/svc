"""Run isolated native Section interactions against product sources and a real CLI."""
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

repo=Path(__file__).resolve().parents[3]
cli=Path(sys.argv[1]);output=Path(sys.argv[2]).resolve();output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='svc-sections-') as temporary:
 root=Path(temporary)
 controller=root/'controller.py'
 controller.write_text('''import sys,time
from pathlib import Path
root=Path(sys.argv[1]);mode=sys.argv[2]
with (root/'effects').open('a') as f:f.write(mode+' started\\n')
if mode=='wait':
 (root/'started').touch();end=time.monotonic()+30
 while not (root/'gate').exists() and time.monotonic()<end:time.sleep(.02)
 (root/'finished').touch()
if mode=='fail':sys.exit(7)
''')
 for name in ['alpha','beta','gamma']:
  project=root/name;project.mkdir()
  actions={mode:{'kind':'exec','argv':[str(cli.parent/'python'),str(controller),str(root),mode],'intent':mode,'effect_scope':name,'traits':['runtime'],'data_effect':'unchanged'} for mode in ['wait','fail']}
  (project/'svc.json').write_text(json.dumps({'schema_version':5,'dev':{'resources':{'worker':{'scope':'repository','actions':actions}}}}))
 bundle=root/'SectionObservation.app';binary=bundle/'Contents/MacOS/SectionObservation';binary.parent.mkdir(parents=True)
 (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundlePackageType':'APPL','CFBundleExecutable':binary.name,'CFBundleIdentifier':'dev.svc.section-observation','LSUIElement':True,'NSPrincipalClass':'NSApplication','LSMinimumSystemVersion':'14.0'}))
 inputs=sorted(p for p in (repo/'macos/Sources/SVCMenuBar').rglob('*.swift') if p.name!='SVCMenuBarApp.swift')
 subprocess.run(['swiftc','-parse-as-library','-swift-version','6',*[str(p) for p in inputs],str(Path(__file__).with_suffix('.swift')),'-o',str(binary)],check=True)
 subprocess.run(['codesign','--force','--sign','-',str(bundle)],capture_output=True,check=True)
 try:
  result=subprocess.run(['/usr/bin/open','-g','-n','-W',str(bundle),'--args',str(root),str(cli)],capture_output=True,text=True,timeout=100)
  (output/'launcher.txt').write_text(result.stdout+result.stderr)
  result.check_returncode()
  report=json.loads((root/'report.json').read_text())
  report['effects']=(root/'effects').read_text().splitlines() if (root/'effects').exists() else []
  report['controller_finished']=(root/'finished').exists()
  report['source_hashes']={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
  report['cli']=str(cli)
  (output/'observations.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  for p in root.glob('*.png'):shutil.copy2(p,output/p.name)
  print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},ensure_ascii=False,indent=2))
 finally:(root/'gate').touch()

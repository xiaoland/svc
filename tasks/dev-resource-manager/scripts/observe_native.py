"""Observe actual product controls with a packaged CLI in an accessory host."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

source = Path(__file__).resolve()
repo = source.parents[3]
cli = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
controller = '''import json, sys, time
from pathlib import Path
from datetime import datetime, timezone
root=Path(sys.argv[1]); mode=sys.argv[2]
if mode == "observe":
    print(json.dumps({"schema_version":1,"state":"satisfied","value":(root/"version").read_text(),"data_at":datetime.now(timezone.utc).isoformat()}))
elif mode == "wait":
    (root/"waiting").touch(); deadline=time.monotonic()+30
    while not (root/"gate").exists() and time.monotonic()<deadline: time.sleep(.03)
    (root/"finished").touch()
elif mode == "destroy": (root/"data").unlink()
elif mode == "disconnect": (root/"connection").unlink()
elif mode == "update": (root/"version").write_text("2.0")
elif mode == "reject": sys.exit(7)
'''
with tempfile.TemporaryDirectory(prefix='svc-native-observe-') as temporary:
    root = Path(temporary)
    project = root/'开发资源与很长名称的隔离项目'; project.mkdir()
    owner = root/'owner'; owner.mkdir()
    (owner/'svc.json').write_text(json.dumps({'schema_version':5,'dev':{'resources':{'shared':{'scope':'repository','access':['http://localhost']}}}}))
    fixture=root/'controller.py'; fixture.write_text(controller)
    for name in ('data','connection'): (root/name).write_text('owned fixture')
    (root/'version').write_text('1.0')
    def argv(mode): return [str(cli.parent/'python'),str(fixture),str(root),mode]
    def action(mode, intent, trait, effect='unchanged'):
        return {'kind':'exec','argv':argv(mode),'intent':intent,'traits':[trait],'effect_scope':'本次隔离资源','data_effect':effect}
    resources={
        'shared':{'label':'共享数据库 · 只有引用方明确声明的销毁入口','owner':{'repo':str(owner),'resource':'shared'},'actions':{'destroy':action('destroy','销毁数据','provision','delete')}},
        'connection':{'label':'连接通路','scope':'repository','relations':['shared'], 'observations':{'reachable':{'probe':{'kind':'tcp','host':'127.0.0.1','port':1,'timeout':.2}}},'actions':{'disconnect':action('disconnect','断开连接','connection')}},
        'install':{'label':'主机组件安装 · 版本与运行分别观察','scope':'host','host_key':'svc-observation-'+root.name,'observations':{'version':{'label':'安装版本','probe':{'kind':'exec','argv':argv('observe'),'format':'json'}},'permission':{'label':'设备授权','automatic':False,'probe':{'kind':'exec','argv':[str(cli.parent/'python'),'-c','raise SystemExit(1)']}},'running':{'label':'运行状态','probe':{'kind':'exec','argv':[str(cli.parent/'python'),'-c','raise SystemExit(1)']}}},'actions':{'update':action('update','更新组件','installation','modify'),'manual':{'kind':'manual','intent':'授权设备','effect_scope':'本机组件','steps':['在系统设置中完成授权']}}},
        'wait':{'label':'停止并等待在途请求完成','scope':'repository','actions':{'stop':action('wait','等待停止','runtime'),'reject':action('reject','请求控制者拒绝','runtime')}}}
    resources['reference']={'label':'同一数据库的人工引用入口','owner':{'repo':str(owner),'resource':'shared'},'actions':{'manual':{'kind':'manual','intent':'查看引用方步骤','effect_scope':'引用方允许的操作','steps':['向控制者核对资源']}}}
    (project/'svc.json').write_text(json.dumps({'schema_version':5,'dev':{'resources':resources}},ensure_ascii=False))
    bundle=root/'ResourceObservation.app'; executable=bundle/'Contents/MacOS/ResourceObservation'; executable.parent.mkdir(parents=True)
    (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundlePackageType':'APPL','CFBundleExecutable':executable.name,'CFBundleIdentifier':'dev.svc.resource-observation','LSUIElement':True,'NSPrincipalClass':'NSApplication','LSMinimumSystemVersion':'14.0'}))
    inputs=sorted(p for p in (repo/'macos/Sources/SVCMenuBar').rglob('*.swift') if p.name!='SVCMenuBarApp.swift')
    app_source=repo/'macos/Sources/SVCMenuBar/App/SVCMenuBarApp.swift'
    delegate_source=root/'ProductDelegate.swift'; delegate_source.write_text(app_source.read_text().split('\n@main\n')[0])
    subprocess.run(['swiftc','-parse-as-library','-swift-version','6',*[str(p) for p in inputs],str(delegate_source),str(source.with_suffix('.swift')),'-o',str(executable)],check=True)
    subprocess.run(['codesign','--force','--sign','-',str(bundle)],check=True,capture_output=True)
    env=dict(os.environ,XDG_RUNTIME_DIR=str(root/'runtime'))
    result=subprocess.run([str(executable),'--monitor',str(bundle),str(root),str(cli)],env=env,text=True,capture_output=True,timeout=300)
    (output/'native-raw.txt').write_text(result.stdout+'\n'+result.stderr)
    result.check_returncode()
    report=json.loads(result.stdout)
    report['effects']={'data_deleted':not(root/'data').exists(),'connection_removed':not(root/'connection').exists(),'installed_version':(root/'version').read_text(),'wait_finished':(root/'finished').exists()}
    report['cli_path']=str(cli)
    report['source_hashes']={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*inputs,app_source]}
    report['limit']='Actual product views/store/client in isolated accessory host; no installed-app menu interaction.'
    (output/'native-observations.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    for png in root.glob('*.png'): shutil.copy2(png,output/png.name)
    print(json.dumps(report,ensure_ascii=False,indent=2))

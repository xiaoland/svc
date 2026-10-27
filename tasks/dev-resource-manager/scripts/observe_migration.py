"""Observe a real CLI 17 owner holding the same coordination boundary as CLI 18."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

old, new, destination = map(Path, sys.argv[1:4])
report = {'old_cli':str(old.resolve()),'new_cli':str(new.resolve())}
with tempfile.TemporaryDirectory(prefix='svc-migration-') as temporary:
    root=Path(temporary); project=root/'project'; project.mkdir()
    controller=root/'controller.py'
    controller.write_text('''import sys,time
from pathlib import Path
root=Path(sys.argv[1])
with (root/'events').open('a') as stream: stream.write(sys.argv[2]+' started\\n')
(root/'started').touch()
end=time.monotonic()+20
while not (root/'gate').exists() and time.monotonic()<end: time.sleep(.02)
''')
    env=dict(os.environ,XDG_RUNTIME_DIR=str(root/'runtime'))
    argv=[sys.executable,str(controller),str(root),'old']
    (project/'svc.json').write_text(json.dumps({'schema_version':4,'dev':{'targets':{'server':{'scope':'repository','probe':{'kind':'exec','argv':[sys.executable,'-c','raise SystemExit(1)']},'provision':{'kind':'exec','mode':'run','argv':argv},'readiness_timeout':15,'poll_interval':.05}}}}))
    owner=subprocess.Popen([str(old.resolve()),'dev','ensure','server','--repo',str(project),'--json'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        end=time.monotonic()+90
        while not (root/'started').exists():
            if time.monotonic()>end: raise TimeoutError('old owner did not start')
            time.sleep(.02)
        config={'schema_version':5,'dev':{'resources':{'server':{'scope':'repository','actions':{'go':{'kind':'exec','intent':'迁移控制','effect_scope':'隔离资源','argv':[*argv[:-1],'new']}}}}}}
        (project/'svc.json').write_text(json.dumps(config))
        def call():
            result=subprocess.run([str(new.resolve()),'dev','act','server','go','--repo',str(project),'--json'],env=env,capture_output=True,text=True,timeout=90)
            return {'exit':result.returncode,'stdout':json.loads(result.stdout),'stderr':result.stderr}
        report['during_old_owner']=call()
        report['events_during_lock']=(root/'events').read_text().splitlines()
        report['old_owner_still_running']=owner.poll() is None
        (root/'gate').touch()
        stdout,stderr=owner.communicate(timeout=90)
        report['old_settled']={'exit':owner.returncode,'stdout':json.loads(stdout),'stderr':stderr}
        report['after_drain']=call()
        report['events_after_drain']=(root/'events').read_text().splitlines()
        config['dev']['resources']['server']['scope']='host'
        config['dev']['resources']['server']['host_key']=root.name
        (project/'svc.json').write_text(json.dumps(config))
        report['scope_change_after_settlement']=call()
        shared=root/'shared';shared.mkdir()
        (shared/'svc.json').write_text(json.dumps({'schema_version':5,'dev':{'resources':{'server':{'scope':'host','host_key':root.name,'access':['http://localhost']}}}}))
        resource=config['dev']['resources']['server']
        del resource['scope'];del resource['host_key']
        resource['owner']={'repo':str(shared),'resource':'server'}
        (project/'svc.json').write_text(json.dumps(config))
        report['owner_change_after_settlement']=call()
        report['events_after_identity_changes']=(root/'events').read_text().splitlines()
    finally:
        (root/'gate').touch()
        if owner.poll() is None: owner.communicate(timeout=90)
Path(destination).write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))

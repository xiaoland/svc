"""Record provider freshness and explicit observation behavior through the CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

cli=Path(sys.argv[1]).resolve(); destination=Path(sys.argv[2]); report={}
with tempfile.TemporaryDirectory(prefix='svc-facets-') as temporary:
    root=Path(temporary); events=root/'events'
    def probe(text):
        return {'kind':'exec','format':'json','argv':[str(cli.parent/'python'),'-c',f'from pathlib import Path; Path({str(events)!r}).open("a").write("observed\\n"); print({text!r})']}
    facets={
        'fresh':{'probe':probe('{"schema_version":1,"state":"satisfied","value":"installed"}')},
        'stale':{'ttl':1,'probe':probe('{"schema_version":1,"state":"satisfied","data_at":"2000-01-01T00:00:00+00:00","value":"old"}')},
        'unknown':{'probe':probe('{"schema_version":1,"state":"unknown"}')},
        'duplicate':{'probe':probe('{"schema_version":1,"state":"satisfied","state":"unknown"}')},
        'overflow':{'probe':probe('{"schema_version":1,"state":"satisfied","value":1e999}')},
        'oversize':{'probe':probe('x'*65537)},
        'remote-denied':{'probe':{'kind':'http','url':'http://192.0.2.1','timeout':.1}},
        'manual':{'automatic':False,'probe':probe('{"schema_version":1,"state":"unsatisfied"}')},
    }
    config={'schema_version':5,'dev':{'resources':{
        'access-only':{'access':['https://example.invalid/developer']},
        'component':{'scope':'host','host_key':root.name,'observations':facets},
        'service':{'observations':{'wrong-purpose':{'probe':{'kind':'exec','argv':[str(cli.parent/'python'),'-c','pass']}}},'actions':{'ensure':{'kind':'exec','argv':[str(cli.parent/'python'),'-c',f'from pathlib import Path; Path({str(root/"started")!r}).touch()'],'intent':'就绪','effect_scope':'隔离实例','completion':'ready','interruption':'terminate','conditions':['wrong-purpose'],'convergent':True}}}
    }}}
    (root/'svc.json').write_text(json.dumps(config))
    env=dict(os.environ,XDG_RUNTIME_DIR=str(root/'runtime'))
    def call(*args):
        proc=subprocess.run([str(cli),'dev',*args,'--repo',str(root),'--json'],env=env,text=True,capture_output=True,timeout=60)
        return {'exit':proc.returncode,'stdout':json.loads(proc.stdout),'stderr':proc.stderr}
    report['list']=call('list'); report['probe_called_by_list']=events.exists()
    report['access_only']=call('status','access-only')
    text=subprocess.run([str(cli),'dev','list','access-only','--repo',str(root)],env=env,text=True,capture_output=True,timeout=30)
    report['text']={'exit':text.returncode,'stdout':text.stdout,'stderr':text.stderr}
    report['automatic']=call('status','component')
    report['explicit']=call('status','component','--observation','manual')
    report['invalid_ready_provenance']=call('act','service','ensure')
    report['service_started']=(root/'started').exists()
clock=subprocess.run([str(cli.parent/'python'),'-c','''
import json
from datetime import datetime, timezone, timedelta
from svc_cli.dev import observations
from svc_cli.dev.models import Observation
edge=datetime(2026,1,1,tzinfo=timezone.utc)
class Clock(datetime):
 @classmethod
 def now(cls,tz=None): return cls.instant
observations.datetime=Clock
fact=Observation(key='r',label='r',state='satisfied',source='isolated',checked_at=edge.isoformat(),expires_at=edge.isoformat())
result={}
for name,offset in [('before',-1),('at',0),('after',1)]:
 Clock.instant=edge+timedelta(microseconds=offset)
 result[name]=observations.satisfied((fact,))
print(json.dumps(result))
'''],capture_output=True,text=True,check=True)
report['controlled_expiry_boundary']=json.loads(clock.stdout)
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({key:value.get('exit') for key,value in report.items() if isinstance(value,dict)}))

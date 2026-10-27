"""Record invalid resource configurations and a valid local overlay."""
import copy
import json
from pathlib import Path
import tempfile
from svc_cli.config import ConfigError, load_config, parse_project_config

base={'schema_version':5,'dev':{'resources':{'r':{'actions':{'go':{'kind':'exec','intent':'执行','effect_scope':'临时对象','argv':['true']}}}}}}
changes={'wait-timeout':{'timeout':1},'ready-without-proof':{'completion':'ready'},'submission-conditions':{'completion':'submitted','conditions':['missing']},'convergence-delete':{'data_effect':'delete','convergent':True},'result-mode':{'result':'operation-json'},'nul-argv':{'argv':['bad\0arg']}}
report={}
for name,change in changes.items():
 doc=copy.deepcopy(base);doc['dev']['resources']['r']['actions']['go'].update(change)
 try:parse_project_config(json.dumps(doc).encode());report[name]={'accepted':True}
 except ConfigError as e:report[name]={'accepted':False,'message':str(e)}
for name,resource in {'host-without-key':{'scope':'host','access':['http://localhost']},'owner-plus-scope':{'scope':'repository','owner':{'repo':'../owner','resource':'r'},'access':['http://localhost']},'no-capability':{}}.items():
 try:parse_project_config(json.dumps({'schema_version':5,'dev':{'resources':{'r':resource}}}).encode());report[name]={'accepted':True}
 except ConfigError as e:report[name]={'accepted':False,'message':str(e)}
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'svc.json').write_text(json.dumps(base))
 overlay={'schema_version':5,'dev':{'resources':{'r':{'actions':{'go':{'env':{'LOCAL':'yes'}}}}}}}
 (p/'svc.local.json').write_text(json.dumps(overlay))
 report['overlay']={'env':load_config(p).effective.dev.resources['r'].actions['go'].env}
Path('tasks/dev-resource-manager/evidence/configuration-boundaries.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print({k:v.get('accepted',v) for k,v in report.items()})

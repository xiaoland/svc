"""Stage 6 observations: real CLI requests plus explicit, isolated fault gates.

This is a task-local evidence collector, not a repository test suite. It preserves
raw outcomes; acceptance judgments belong to verification.md.
"""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

cli=Path(sys.argv[1]).resolve(); python=str(cli.parent/'python'); output=Path(sys.argv[2]).resolve()
report={'cli':str(cli),'observations':{}}
CONTROLLER=r'''
import json,os,signal,sys,time
from pathlib import Path
root=Path(sys.argv[1]); name=sys.argv[2]; mode=sys.argv[3]
def log(value):
 with (root/(name+'.events')).open('a') as f: f.write(value+'\n')
if mode.startswith('probe'):
 if mode=='probe-ok': sys.exit(0)
 if mode=='probe-no': sys.exit(1)
 if mode=='probe-error': sys.exit(8)
 if mode=='probe-json':
  print(json.dumps({'schema_version':1,'state':'satisfied','instance':sys.argv[4]})); sys.exit(0)
 sys.exit(0 if (root/(name+'.started')).exists() else 1)
log('started'); (root/(name+'.started')).touch(); (root/(name+'.pid')).write_text(str(os.getpid()))
def sig(n,f): log('signal:'+str(n)); sys.exit(128+n)
signal.signal(signal.SIGTERM,sig); signal.signal(signal.SIGINT,sig)
if mode=='wait':
 end=time.monotonic()+45
 while not(root/(name+'.gate')).exists() and time.monotonic()<end: time.sleep(.02)
if mode.startswith('submit'):
 result=Path(os.environ['SVC_DEV_RESULT_FILE']); log('submission')
 if mode=='submit-valid':
  print('stdout log'); print('stderr log',file=sys.stderr); result.write_text(json.dumps({'schema_version':1,'operation':{'id':'operation-1','url':'https://example.invalid/operation-1'}}))
 elif mode=='submit-malformed': result.write_text('{')
 elif mode=='submit-link':
  p=root/'linked'; p.write_text('{"schema_version":1,"operation":{"id":"unsafe"}}'); result.symlink_to(p)
 elif mode=='submit-large': result.write_text('x'*65537)
 elif mode=='submit-duplicate': result.write_text('{"schema_version":1,"operation":{"id":"a","id":"b"}}')
 elif mode=='submit-url': result.write_text('{"schema_version":1,"operation":{"id":"a","url":"file:///tmp/example"}}')
 elif mode=='submit-nonzero': sys.exit(7)
log('finished'); (root/(name+'.done')).touch()
'''
WRAPPER=r'''
import os,sys,time
from pathlib import Path
from svc_cli.dev import runtime,records
from svc_cli.cli import main
hook,roottext=sys.argv[1:3]; root=Path(roottext); args=sys.argv[3:]
def gate(name):
 (root/(name+'.at')).touch(); end=time.monotonic()+30
 while not(root/(name+'.go')).exists() and time.monotonic()<end: time.sleep(.01)
if hook=='locked':
 original=runtime.resolve_resource; calls=0
 def resolve(*args,**kwargs):
  global calls
  calls+=1
  if calls==2: gate('locked')
  return original(*args,**kwargs)
 runtime.resolve_resource=resolve
if hook in ('before-launch','settled-crash','settle-failure'):
 original=records.write
 def write(store,record):
  if hook=='settle-failure' and record.phase=='settled': raise OSError('injected receipt storage failure')
  original(store,record)
  if hook=='before-launch' and record.phase=='pending': gate('before-launch')
  if hook=='settled-crash' and record.phase=='settled': os._exit(99)
 records.write=write
if hook in ('pending-failure','pointer-crash','running-failure'):
 from svc_cli._execution import ExecutionStore
 if hook=='pending-failure':
  def fail_pending(*args): raise OSError('injected pending publication failure')
  records.write=fail_pending
 elif hook=='pointer-crash':
  original_pointer=ExecutionStore.write_coordination
  def pointer(self,*args):
   original_pointer(self,*args); os._exit(98)
  ExecutionStore.write_coordination=pointer
 else:
  original_execution=ExecutionStore.write
  def mechanical(self,record):
   if record.state=='running':
    (root/'running-failure.at').touch(); raise OSError('injected running record failure')
   original_execution(self,record)
  ExecutionStore.write=mechanical
if hook=='follower':
 original=records.read; first=True
 def read(*args,**kwargs):
  global first
  value=original(*args,**kwargs)
  if first and value.phase=='pending':
   first=False; gate('follower')
  return value
 records.read=read
sys.exit(main(args))
'''
processes=[]; sentinel=None
with tempfile.TemporaryDirectory(prefix='svc-accept-resources-') as temporary:
 root=Path(temporary); fixture=root/'controller.py'; fixture.write_text(CONTROLLER); wrapper=root/'gated_cli.py';wrapper.write_text(WRAPPER)
 env=dict(os.environ,XDG_RUNTIME_DIR=str(root/'runtime'))
 def wait(path,seconds=30):
  end=time.monotonic()+seconds
  while not path.exists():
   if time.monotonic()>end: raise TimeoutError(str(path))
   time.sleep(.01)
 def argv(name,mode,*rest): return [python,str(fixture),str(root),name,mode,*rest]
 def action(name,mode='finite',**kwargs): return {'kind':'exec','intent':name,'effect_scope':'隔离资源','argv':argv(name,mode),**kwargs}
 def resource(name,mode='finite',**kwargs): return {'scope':'repository','actions':{'go':action(name,mode,**kwargs)}}
 def project(name,config):
  p=root/name;p.mkdir();save(p,config);return p
 def save(p,config): (p/'svc.json').write_text(json.dumps({'schema_version':5,'dev':{'resources':config}}))
 def start(p,*args,hook=None):
  command=([python,str(wrapper),hook,str(root)] if hook else [str(cli)])+['dev',*args,'--repo',str(p),'--json']
  child=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);processes.append(child);return child
 def collect(child):
  out,err=child.communicate(timeout=60)
  try: value=json.loads(out)
  except ValueError: value=out
  return {'exit':child.returncode,'result':value,'stderr':err[-6000:]}
 def call(p,*args,hook=None):return collect(start(p,*args,hook=hook))
 def events(name):
  p=root/(name+'.events');return p.read_text().splitlines() if p.exists() else []
 def alive(name):
  p=root/(name+'.pid')
  if not p.exists():return False
  try:os.kill(int(p.read_text()),0);return True
  except ProcessLookupError:return False
 def record(name,data):report['observations'][name]=data
 try:
  # Completion, artificial commands, and submission result boundaries.
  for mode in ['finite','submit-valid','submit-missing','submit-malformed','submit-link','submit-large','submit-duplicate','submit-url','submit-nonzero']:
   cfg={'r':resource(mode,mode,**({'completion':'submitted','result':'operation-json'} if mode.startswith('submit') else {}))};p=project(mode,cfg)
   record(mode,{'response':call(p,'act','r','go'),'events':events(mode)})
  for mode in ['probe-no','probe-error']:
   name='condition-'+mode;r=resource(name,conditions=['done'],completion_timeout=.15,poll_interval=.03)
   r['observations']={'done':{'probe':{'kind':'exec','argv':argv(name,mode)}}};p=project(name,{'r':r})
   record(name,{'response':call(p,'act','r','go'),'events':events(name)})
  p=project('manual',{'r':{'actions':{'manual':{'kind':'manual','intent':'授权','effect_scope':'临时设备','steps':['进入控制者设置']}}}})
  record('manual-absent',{'manual':call(p,'act','r','manual'),'absent':call(p,'act','r','absent')})
  # Signals and owned-process boundaries.
  sentinel=subprocess.Popen([python,'-c','import time;time.sleep(120)']);processes.append(sentinel)
  for name,extra,send in [('terminate-signal',{'interruption':'terminate'},True),('terminate-timeout',{'interruption':'terminate','timeout':.4},False)]:
   p=project(name,{'r':resource(name,'wait',**extra)});child=start(p,'act','r','go');wait(root/(name+'.started'))
   if send:child.send_signal(signal.SIGTERM)
   record(name,{'response':collect(child),'events':events(name),'child_alive':alive(name),'sentinel_alive':sentinel.poll() is None})
  p=project('prelaunch',{'r':resource('prelaunch')});child=start(p,'act','r','go',hook='before-launch');wait(root/'before-launch.at');child.send_signal(signal.SIGINT);time.sleep(.05);(root/'before-launch.go').touch()
  record('prelaunch',{'response':collect(child),'events':events('prelaunch')})
  # Ready provenance, early exit, and ownership after release when receipt writing fails.
  for name,probe_mode,instance,mode,hook in [('ready-good','probe-json','${dev.instance}','wait',None),('ready-wrong','probe-json','wrong','wait',None),('ready-early','probe-no',None,'finite',None),('released-storage-failure','probe-state',None,'wait','settle-failure')]:
   r=resource(name,mode,completion='ready',interruption='terminate',conditions=['ready'],completion_timeout=.35,poll_interval=.03)
   if name!='released-storage-failure':r.pop('scope')
   probe={'kind':'exec','argv':argv(name,probe_mode,*([instance] if instance else []))}
   if probe_mode=='probe-json':probe['format']='json'
   r['observations']={'ready':{'purpose':'runtime-readiness','probe':probe}};p=project(name,{'r':r})
   response=call(p,'act','r','go',hook=hook)
   record(name,{'response':response,'child_alive':alive(name),'events':events(name),'status':call(p,'status')})
   (root/(name+'.gate')).touch()
  # Owner failures preserve local observations and never inherit actions/probes.
  owner=project('owner',{'base':resource('owner','wait')})
  reference=project('reference',{'r':{'owner':{'repo':str(owner),'resource':'base'},'observations':{'local':{'probe':{'kind':'exec','argv':argv('local','probe-ok')}}},'actions':{'go':action('reference')}}})
  child=start(owner,'act','base','go');wait(root/'owner.started')
  record('shared-competition',{'response':call(reference,'act','r','go'),'reference_events':events('reference')});(root/'owner.gate').touch();collect(child)
  missing=project('missing-owner',{'r':{'owner':{'repo':str(root/'missing'),'resource':'base'},'access':['http://localhost'],'observations':{'local':{'probe':{'kind':'exec','argv':argv('local','probe-ok')}}},'actions':{'go':action('missing')}}})
  record('missing-owner',{'status':call(missing,'status'),'control':call(missing,'act','r','go'),'events':events('missing')})
  chain=project('chain',{'r':{'owner':{'repo':str(reference),'resource':'r'},'access':['http://localhost']}})
  record('owner-chain',call(chain,'list'))
  # Lock-time reparse and join changes, using gates outside production code.
  for name,expected,scope in [('locked-digest',True,False),('locked-current',False,False),('locked-scope',False,True)]:
   for suffix in ['at','go']:(root/('locked.'+suffix)).unlink(missing_ok=True)
   cfg={'r':resource(name)};p=project(name,cfg);listing=call(p,'list')['result'];digest=listing['resources'][0]['declaration_digest']
   child=start(p,'act','r','go',*(['--expected-digest',digest] if expected else []),hook='locked');wait(root/'locked.at')
   cfg['r']['actions']['go']['argv']=argv(name+'-new','finite')
   if scope:cfg['r']['scope']='host';cfg['r']['host_key']=name
   save(p,cfg);(root/'locked.go').touch()
   record(name,{'response':collect(child),'old_events':events(name),'new_events':events(name+'-new')})
  for name,change in [('join-signal',False),('join-stale',True)]:
   for suffix in ['at','go']:(root/('follower.'+suffix)).unlink(missing_ok=True)
   cfg={'r':resource(name,'wait',conditions=['done'],convergent=True)};cfg['r']['observations']={'done':{'probe':{'kind':'exec','argv':[python,'-c',f'from pathlib import Path; raise SystemExit(0 if Path({str(root/(name+".done"))!r}).exists() else 1)']}}};p=project(name,cfg)
   owner_child=start(p,'act','r','go');wait(root/(name+'.started'));follower=start(p,'act','r','go',hook='follower');wait(root/'follower.at')
   if change:cfg['r']['actions']['go']['intent']='changed';save(p,cfg)
   else:follower.send_signal(signal.SIGINT);time.sleep(.05)
   (root/'follower.go').touch();result=collect(follower)
   still=owner_child.poll() is None;(root/(name+'.gate')).touch()
   record(name,{'follower':result,'owner_alive_before_gate':still,'owner':collect(owner_child),'events':events(name)})
  # Settled is authoritative even if the CLI crashes before emitting its response.
  p=project('settled',{'r':resource('settled')});crash=call(p,'act','r','go',hook='settled-crash');status=call(p,'status');again=call(p,'act','r','go')
  record('settled-crash',{'crash':crash,'status':status,'next_request':again,'events':events('settled')})
  for hook in ['pending-failure','pointer-crash']:
   p=project(hook,{'r':resource(hook)});first=call(p,'act','r','go',hook=hook);before=events(hook);again=call(p,'act','r','go')
   record(hook,{'first':first,'events_before_next':before,'next_request':again,'events_after_next':events(hook)})
  name='running-failure';p=project(name,{'r':resource(name,'wait')});child=start(p,'act','r','go',hook=name);wait(root/(name+'.started'));wait(root/'running-failure.at');child.send_signal(signal.SIGTERM);time.sleep(.2)
  busy=call(p,'act','r','go');live=child.poll() is None;(root/(name+'.gate')).touch();result=collect(child)
  record(name,{'owner_alive_before_gate':live,'busy':busy,'result':result,'events':events(name),'next_request':call(p,'act','r','go')})
  # Missing act metadata is corruption, not a legacy record.
  p=project('corrupt',{'r':resource('corrupt')});first=call(p,'act','r','go');execution=first['result']['execution'];meta=Path(execution['log_path']).parent/'dev.json';meta.unlink()
  record('missing-metadata',{'response':call(p,'act','r','go'),'events':events('corrupt')})
 finally:
  for marker in root.glob('*.started'):(root/(marker.stem+'.gate')).touch()
  for name in ['locked','before-launch','follower']:(root/(name+'.go')).touch()
  for child in processes:
   if child.poll() is None:
    if child is sentinel:child.terminate()
    child.communicate(timeout=60)
  output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({key:value.get('response',value).get('exit') for key,value in report['observations'].items() if isinstance(value,dict)},ensure_ascii=False))

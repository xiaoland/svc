"""Collect real CLI/controller evidence in disposable projects; no test framework."""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

CONTROLLER = r'''
import json, os, signal, subprocess, sys, time
from pathlib import Path
root=Path(sys.argv[1]); mode=sys.argv[2]; name=sys.argv[3]
def append(s):
    with (root/(name+".events")).open("a") as f: f.write(s+"\n")
def wait_gate():
    end=time.monotonic()+25
    while not (root/(name+".gate")).exists() and time.monotonic()<end: time.sleep(.02)
if mode == "observe":
    append("observed")
    sys.exit(0 if (root/(name+".done")).exists() else 1)
if mode == "post":
    (root/(name+".observing")).touch(); wait_gate(); sys.exit(0)
if mode == "submit":
    try:
        fd=os.open(root/(name+".pending"), os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.close(fd)
    except FileExistsError: sys.exit(9)
    subprocess.Popen([sys.executable,__file__,str(root),"worker",name],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    Path(os.environ["SVC_DEV_RESULT_FILE"]).write_text(json.dumps({"schema_version":1,"operation":{"id":name+"-op"}}))
    print("accepted",file=sys.stderr); sys.exit(0)
signal.signal(signal.SIGINT,lambda n,f:append("signal:"+str(n)))
signal.signal(signal.SIGTERM,lambda n,f:append("signal:"+str(n)))
append("started"); (root/(name+".started")).touch()
if mode in {"wait","worker"}: wait_gate()
append("finished"); (root/(name+".done")).touch()
if mode == "worker": (root/(name+".pending")).unlink(missing_ok=True)
'''

def wait_file(path: Path, seconds: float=10):
    deadline=time.monotonic()+seconds
    while not path.exists():
        if time.monotonic()>deadline: raise TimeoutError(str(path))
        time.sleep(.02)

def main():
    output=Path(sys.argv[1]) if len(sys.argv)>1 else Path('tasks/dev-resource-manager/runtime-observations.json')
    output=output.resolve()
    cli=os.environ.get("SVC_OBSERVE_CLI")
    report={"source":cli or "working-tree CLI", "scenarios":{}}
    processes=[]
    with tempfile.TemporaryDirectory(prefix='svc-resource-observe-') as directory:
        root=Path(directory); repo=root/'project'; repo.mkdir(); fixture=root/'controller.py'; fixture.write_text(CONTROLLER)
        env=dict(os.environ, XDG_RUNTIME_DIR=str(root/'runtime'))
        def command(mode,name): return [sys.executable,str(fixture),str(root),mode,name]
        def action(mode,name,**extra):
            return {"kind":"exec","intent":name,"effect_scope":"隔离临时文件","data_effect":"modify","argv":command(mode,name),**extra}
        def resource(name,mode='wait',**extra):
            return {"scope":"repository","actions":{"go":action(mode,name,**extra)}}
        configs={"wait":resource('wait'),"lost":resource('lost'),"install":resource('install','finite'),
                 "submit":resource('submit','submit',completion='submitted',result='operation-json')}
        configs['ensure']={"scope":"repository","observations":{"done":{"probe":{"kind":"exec","argv":command('observe','ensure')}}},
                           "actions":{"ensure":action('wait','ensure',conditions=['done'],convergent=True)}}
        configs['post']={"scope":"repository","observations":{"done":{"automatic":False,"probe":{"kind":"exec","argv":command('post','post'),"timeout":20}}},
                         "actions":{"go":action('finite','post',conditions=['done'])}}
        def save(): (repo/'svc.json').write_text(json.dumps({"schema_version":5,"dev":{"resources":configs}}))
        save()
        def start(*args, location=repo):
            proc=subprocess.Popen(([cli] if cli else [sys.executable,'-m','svc_cli.cli'])+['dev',*args,'--repo',str(location),'--json'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            processes.append(proc); return proc
        def collect(proc):
            out,err=proc.communicate(timeout=30)
            try: value=json.loads(out)
            except json.JSONDecodeError: value=out
            return {"exit_code":proc.returncode,"result":value,"stderr":err}
        def call(*args,location=repo): return collect(start(*args,location=location))
        def events(name):
            p=root/(name+'.events'); return p.read_text().splitlines() if p.exists() else []
        try:
            first=call('list'); before=events('ensure'); status=call('status','ensure')
            report['scenarios']['read_only']={"list":first,"provider_events_after_list":before,"status":status,"provider_events_after_status":events('ensure')}
            digest=next(x['declaration_digest'] for x in first['result']['resources'] if x['resource']=='install')
            configs['install']['actions']['go']['intent']='变更后的安装'; save()
            stale=call('act','install','go','--expected-digest',digest)
            report['scenarios']['stale']={"response":stale,"controller_events":events('install')}
            report['scenarios']['finite']={"response":call('act','install','go'),"controller_events":events('install')}
            owner=start('act','wait','go'); wait_file(root/'wait.started')
            busy=call('act','wait','go')
            for number in [signal.SIGINT,signal.SIGTERM,signal.SIGINT]: owner.send_signal(number); time.sleep(.1)
            time.sleep(3.3)
            report['scenarios']['wait']={"busy":busy,"owner_alive_after_signals":owner.poll() is None,"controller_before_finish":events('wait')}
            (root/'wait.gate').touch(); report['scenarios']['wait']['completion']=collect(owner)
            owner=start('ensure','ensure'); wait_file(root/'ensure.started')
            follower=start('ensure','ensure'); time.sleep(.6); (root/'ensure.gate').touch()
            report['scenarios']['join']={"owner":collect(owner),"follower":collect(follower),"events":events('ensure')}
            owner=start('act','lost','go'); wait_file(root/'lost.started'); owner.kill(); collect(owner)
            lost1=call('act','lost','go'); lost2=call('act','lost','go'); eid=lost1['result']['execution']['execution_id']
            wrong=call('reconcile','lost','--execution','00000000-0000-4000-8000-000000000000','--acknowledge-unknown')
            inspect=call('reconcile','lost','--execution',eid)
            confirmed=call('reconcile','lost','--execution',eid,'--acknowledge-unknown')
            report['scenarios']['owner_lost']={"first":lost1,"second":lost2,"wrong_id":wrong,"without_ack":inspect,"acknowledged":confirmed,"controller_events":events('lost')}
            (root/'lost.gate').touch(); wait_file(root/'lost.done')
            post=start('act','post','go'); wait_file(root/'post.observing'); post.kill(); collect(post)
            report['scenarios']['post_exit_loss']={"first":call('act','post','go'),"second":call('act','post','go'),"controller_events":events('post')}
            (root/'post.gate').touch()
            submitted=call('act','submit','go'); wait_file(root/'submit.started')
            collision=call('act','submit','go')
            report['scenarios']['submitted']={"accepted":submitted,"conflict":collision,"pending":(root/'submit.pending').exists(),"events":events('submit')}
            (root/'submit.gate').touch(); wait_file(root/'submit.done')
            alias=root/'alias'; alias.mkdir(); alias.joinpath('svc.json').write_text(json.dumps({"schema_version":5,"dev":{"resources":{"shared":{"owner":{"repo":str(repo),'resource':'wait'},"access":["http://127.0.0.1:1"],"actions":{"alias":action('finite','alias')}}}}}))
            report['scenarios']['owner_reference']={"owner":call('list','wait'),"reference":call('list','shared',location=alias)}
            old=root/'old'; old.mkdir(); old.joinpath('svc.json').write_text('{"schema_version":4}')
            report['scenarios']['old_config']=call('list',location=old)
        finally:
            for name in configs: (root/(name+'.gate')).touch()
            for proc in processes:
                if proc.poll() is None: proc.communicate(timeout=30)
            # Controller-owned descendants have their own bounded watchdog and completion gates.
            time.sleep(.2)
            output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(output)
    for name, facts in report['scenarios'].items():
        print(name, json.dumps({k:v for k,v in facts.items() if k in {'events','controller_events','owner_alive_after_signals','pending'}},ensure_ascii=False))

if __name__=='__main__': main()

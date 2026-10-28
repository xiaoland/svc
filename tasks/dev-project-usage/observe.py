"""Bounded acceptance observations over isolated records and dedicated projects."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from svc_cli._execution import (
    ExecutionStore, LaunchSpec, release_owned, settle_unstarted_interruption,
    start_isolated, terminate_owned, run_foreground,
)
from svc_cli.activity.managed import execute, request_termination
from svc_cli.activity.monitor import monitor
from svc_cli.activity.provenance import register
from svc_cli.cli_output.activity import project_managed, project_monitor
from svc_cli.errors import SvcError

SCRIPT = Path(__file__).resolve()
LAB = Path('/Volumes/WorkSSD/Development/svc-dev-lab')
PEER = LAB.with_name('svc-dev-lab-peer')
EVIDENCE = SCRIPT.parent / 'evidence'


def owned(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    if spec.get('kind') == 'foreground':
        store=ExecutionStore(Path(spec['store']))
        with store.coordination_lock('run','c'*32):
            published=store.publish(domain='run',operation='execute',subject=spec['label'],
                workspace_instance='lab',intent_digest='lab',coordination_key='c'*32,
                argv=tuple(spec['argv']),cwd=Path(spec['cwd']),capture='split')
            def started(record):
                register(store,record,Path(spec['project']),'explicit')
                Path(spec['id']).write_text(record.execution_id)
            record=run_foreground(store,published,LaunchSpec(tuple(spec['argv']),Path(spec['cwd']),dict(__import__('os').environ)),
                                  stdout_sink=None,stderr_sink=None,on_started=started)
            print(json.dumps(record.as_dict()))
        return
    result = execute(
        tuple(spec['argv']), Path(spec['cwd']), label=spec['label'],
        project=Path(spec['project']), source='agent', store=ExecutionStore(Path(spec['store'])),
        on_started=lambda record: Path(spec['id']).write_text(record.execution_id),
    )
    print(project_managed(result).model_dump_json())


def specification(root, name, cwd, argv, kind='managed'):
    spec = root / (name + '.json')
    spec.write_text(json.dumps(dict(argv=argv, cwd=str(cwd), project=str(cwd),
                                    label=name, store=str(root/'store'), id=str(root/(name+'.id')),kind=kind)))
    return spec


def spawn(root, name, cwd, argv, processes, kind='managed'):
    spec=specification(root,name,cwd,argv,kind)
    output = (root/(name+'.out')).open('w')
    process = subprocess.Popen([sys.executable, str(SCRIPT), '--owned', str(spec)], stdout=output, stderr=output)
    processes.append((process, output))
    return spec, process


def wait_for(snapshot, predicate):
    for _ in range(15):
        value = snapshot()
        if predicate(value):
            return value
        time.sleep(0.15)
    raise RuntimeError('bounded observation did not reach the required state')


def isolated():
    result = {}
    with tempfile.TemporaryDirectory(prefix='svc-project-usage-') as temporary:
        root = Path(temporary)
        store = ExecutionStore(root/'store')
        processes = []
        try:
            sleeper = (sys.executable, '-c', 'import time; time.sleep(5)')
            published = store.publish(domain='dev', operation='act', subject='released-lab',
                workspace_instance='lab', intent_digest='lab', coordination_key='a'*32,
                argv=sleeper, cwd=LAB, capture='merged')
            released = start_isolated(store, published, LaunchSpec(sleeper, LAB, {}))
            register(store, released.record, LAB, 'declared', resource_entry_id='lab-released', resource_key='web')
            release_owned(store, released)
            for number in range(21):
                history = store.publish(domain='run', operation='execute', subject=f'fixture-{number}',
                    workspace_instance='lab', intent_digest='lab', coordination_key=f'{number:032x}',
                    argv=('/usr/bin/true',), cwd=LAB, capture='split')
                settle_unstarted_interruption(store, history.record)
            snapshot = monitor(store=store)
            try:
                termination=request_termination(released.record.execution_id, store=store).status
            except SvcError as error:
                termination=error.code
            result['releasedBeyondHistory'] = {
                'inRecentExecutions': any(item.record.execution_id == released.record.execution_id for item in snapshot.executions),
                'resourceObserved': any(item.execution_id == released.record.execution_id for item in snapshot.resources),
                'usage': project_monitor(snapshot).as_dict()['projects'],
                'termination': termination,
            }
            released.process.wait(timeout=6)

            worker_spec = specification(root, 'inner-project', PEER,
                                       [sys.executable, '-c', 'import time; data=bytearray(1048576); time.sleep(7)'])
            # The outer foreground run includes the inner managed root in its descendants.
            # Use a second outer managed invocation of a bounded nested process for attribution.
            outer_code = 'import subprocess,sys; subprocess.run([sys.executable,sys.argv[1],"--owned",sys.argv[2]],check=True)'
            _, outer = spawn(root, 'outer-project', LAB,
                             [sys.executable, '-c', outer_code, str(SCRIPT), str(worker_spec)], processes,kind='foreground')
            snapshot = wait_for(lambda: monitor(store=store),
                                lambda value: len([item for item in value.executions if item.record.state == 'running']) == 2)
            measured = [item for item in snapshot.projects if item.usage is not None]
            result['nestedProjects'] = {
                'projects': project_monitor(snapshot).as_dict()['projects'],
                'executionProcessCounts': {item.label: item.usage.process_count if item.usage else None for item in snapshot.executions if item.record.state == 'running'},
                'projectProcessTotal': sum(item.usage.process_count for item in measured),
                'issues': snapshot.issues,
            }
            outer.wait(timeout=10)

            code = 'import subprocess,sys; subprocess.Popen([sys.executable,"-c","import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(20)"])'
            _, owner = spawn(root, 'reparented-worker', LAB, [sys.executable, '-c', code], processes)
            snapshot = wait_for(lambda: monitor(store=store), lambda value: any(item.group_state == 'descendants-running' for item in value.executions))
            item = next(item for item in snapshot.executions if item.label == 'reparented-worker')
            result['reparentedWorker'] = dict(groupState=item.group_state, processCount=item.usage.process_count if item.usage else None)
            request_termination(item.record.execution_id, force=True, by='human', store=store)
            owner.wait(timeout=5)

            with store.coordination_lock('dev', 'b'*32):
                attempt = store.publish(domain='dev', operation='act', subject='wrong-identity',
                    workspace_instance='lab', intent_digest='lab', coordination_key='b'*32,
                    argv=sleeper, cwd=LAB, capture='merged')
                running = start_isolated(store, attempt, LaunchSpec(sleeper, LAB, {}))
                register(store, running.record, LAB, 'declared')
                path=store.execution_dir(running.record.execution_id)/'observation.json'
                origin=json.loads(path.read_text()); origin['process_created_at'] += 1000
                path.write_text(json.dumps(origin))
                try:
                    snapshot=monitor(store=store)
                    item=next(item for item in snapshot.executions if item.record.execution_id==running.record.execution_id)
                    result['wrongIdentity']=dict(usage=item.usage, canTerminate=item.can_terminate, issues=snapshot.issues)
                finally:
                    terminate_owned(store,running)
        finally:
            for process, output in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=6)
                output.close()
    return result


def public_cli(cli):
    projects = {str(LAB), str(PEER)}
    def call(*args):
        process = subprocess.run([cli,*args],text=True,capture_output=True,timeout=30)
        if process.returncode not in (0,3):
            raise RuntimeError(process.stderr or process.stdout)
        return json.loads(process.stdout)

    children=[]
    results=[]
    try:
        for project in (LAB,PEER):
            results.append(call('dev','ensure','web','--repo',str(project),'--json'))
            output=tempfile.TemporaryFile()
            process=subprocess.Popen([cli,'dev','exec','--cwd',str(project),'--source','agent','--label',project.name+' bounded work','--json','--',
                                      sys.executable,str(project/'runner.py'),'work','--duration','8'],stdout=output,stderr=output)
            children.append((process,output))
        for _ in range(12):
            snapshot=call('dev','monitor','--json')
            if len([item for item in snapshot['executions'] if item['state']=='running' and item['project_path'] in projects])==2:
                break
            time.sleep(0.15)
        snapshot['executions']=[item for item in snapshot['executions'] if item['project_path'] in projects]
        snapshot['projects']=[item for item in snapshot['projects'] if item['project_path'] in projects]
        snapshot['resources']=[item for item in snapshot['resources'] if item['project_path'] in projects]
        (EVIDENCE/'live-monitor.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
        for project in (LAB,PEER):
            catalog=call('dev','status','--repo',str(project),'--json')
            (EVIDENCE/(project.name+'-catalog.json')).write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
        for process,_ in children:
            process.wait(timeout=12)
        return {'monitorSchema':snapshot['schema_version'],'ready':[item['status'] for item in results], 'projects':snapshot['projects'],
                'resourceCount':len(snapshot['resources']), 'exitCodes':[process.returncode for process,_ in children]}
    finally:
        for process,output in children:
            if process.poll() is None:
                process.terminate(); process.wait(timeout=6)
            output.close()
        for project in (LAB,PEER):
            call('dev','stop','web','--repo',str(project),'--json')


if __name__ == '__main__':
    if sys.argv[1:2]==['--owned']:
        owned(sys.argv[2])
    else:
        EVIDENCE.mkdir(exist_ok=True)
        result={'isolated':isolated(),'publicCLI':public_cli(sys.argv[1])}
        (EVIDENCE/'observations.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False,indent=2))

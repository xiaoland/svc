"""Run a small, sequential, low-load acceptance observation and print its facts."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from svc_cli._execution import ExecutionStore
from svc_cli.activity.managed import request_termination
from svc_cli.activity.monitor import monitor


OWNER = """
import json, sys
from pathlib import Path
from svc_cli._execution import ExecutionStore
from svc_cli.activity.managed import execute
from svc_cli.cli_output.activity import project_managed
root, cwd, label, command = sys.argv[1:]
result = execute(tuple(json.loads(command)), Path(cwd), label=label, source='acceptance-script',
    store=ExecutionStore(Path(root)), on_started=lambda record: print(record.execution_id, flush=True))
print(json.dumps(project_managed(result).as_dict()), flush=True)
"""


def main() -> None:
    report: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="svc-activity-observation-") as temporary:
        directory = Path(temporary)
        store = ExecutionStore(directory / "runtime")
        owners: list[tuple[subprocess.Popen[str], str]] = []

        def start(label: str, argv: list[str]) -> tuple[subprocess.Popen[str], str]:
            process = subprocess.Popen(
                [sys.executable, "-c", OWNER, str(store.root), str(directory), label, json.dumps(argv)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            execution_id = process.stdout.readline().strip()
            owners.append((process, execution_id))
            return process, execution_id

        def finish(process: subprocess.Popen[str]) -> dict[str, object]:
            stdout, stderr = process.communicate(timeout=12)
            return {"owner_exit": process.returncode, "result": json.loads(stdout), "stderr": stderr}

        unrelated = subprocess.Popen(["/bin/sleep", "45"])
        try:
            process, identifier = start("正常结束", ["/bin/echo", "stdout-observed"])
            report["natural"] = finish(process)
            report["stdout"] = store.log_path(store.read(identifier), "stdout").read_text()

            process, identifier = start("正常终止", ["/bin/sleep", "30"])
            time.sleep(0.3)
            before = monitor(store=store)
            report["active_controllable"] = [
                item.can_terminate for item in before.executions if item.record.execution_id == identifier
            ]
            report["terminate_request"] = request_termination(identifier, by="human", store=store).__dict__
            report["terminated"] = finish(process)
            report["unrelated_sleep_alive"] = unrelated.poll() is None

            child_pid = directory / "child.pid"
            worker = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
            launcher = (
                "import subprocess,sys,time,pathlib; "
                f"p=subprocess.Popen([sys.executable,'-c',{worker!r}]); "
                f"pathlib.Path({str(child_pid)!r}).write_text(str(p.pid)); time.sleep(.3)"
            )
            process, identifier = start("主进程先退出", [sys.executable, "-c", launcher])
            time.sleep(1.5)
            before_force = monitor(store=store)
            report["leader_exit_group_state"] = [
                item.group_state for item in before_force.executions if item.record.execution_id == identifier
            ]
            request_termination(identifier, by="human", store=store)
            time.sleep(1.2)
            report["term_ignoring_worker_still_owned"] = store.read(identifier).state
            report["force_request"] = request_termination(identifier, force=True, by="human", store=store).__dict__
            report["forced"] = finish(process)
            try:
                os.kill(int(child_pid.read_text()), 0)
                report["worker_still_present_after_force"] = True
            except ProcessLookupError:
                report["worker_still_present_after_force"] = False

            process, identifier = start("执行者丢失", ["/bin/sleep", "3"])
            time.sleep(.3)
            os.kill(process.pid, signal.SIGKILL)
            process.communicate(timeout=3)
            lost = monitor(store=store)
            report["owner_lost"] = [
                {"state": item.record.state, "can_terminate": item.can_terminate}
                for item in lost.executions if item.record.execution_id == identifier
            ]
            report["owner_lost_request"] = request_termination(identifier, force=True, store=store).__dict__
            time.sleep(3)
            report["pressure"] = lost.pressure.__dict__
            report["issues"] = lost.issues
        finally:
            for process, identifier in owners:
                if process.poll() is None:
                    request_termination(identifier, force=True, store=store)
                    process.communicate(timeout=12)
            unrelated.terminate()
            unrelated.wait(timeout=3)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

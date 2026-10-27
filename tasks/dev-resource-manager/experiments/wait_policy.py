"""Preparation probe: existing execution mechanics with a non-forwarding wait owner."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "cli/src"))
from filelock import Timeout
from svc_cli._execution import ExecutionStore, LaunchSpec, OwnedExecution, start_isolated, wait_owned

KEY = "a" * 64
SCRIPT = str(Path(__file__).resolve())


def wait_for(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() > deadline:
            raise TimeoutError("experiment handshake timed out")
        time.sleep(0.02)


def child(root):
    received = []
    def handle(number, _frame):
        received.append(number)
        (root / "child-signals.json").write_text(json.dumps(received))
    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    (root / "child-started").touch()
    wait_for(lambda: (root / "finish").exists(), seconds=20)
    (root / "child-exited").touch()


def owner(root):
    received = []
    def handle(number, _frame):
        received.append(number)
        (root / "owner-signals.json").write_text(json.dumps(received))
    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    store = ExecutionStore(root / "runtime")
    with store.coordination_lock("dev", KEY):
        argv = (sys.executable, SCRIPT, "child", str(root))
        published = store.publish(domain="dev", operation="prep-wait", subject="fixture",
                                  workspace_instance="prep", intent_digest="prep", coordination_key=KEY,
                                  argv=argv, cwd=root, capture="merged")
        store.write_coordination("dev", KEY, published.record.execution_id)
        owned = start_isolated(store, published, LaunchSpec(argv, root, dict(os.environ)))
        assert isinstance(owned, OwnedExecution)
        settled = wait_owned(store, owned)
        assert settled is not None
        (root / "settled.json").write_text(json.dumps(settled.as_dict()))


def probe(root):
    lock = ExecutionStore(root / "runtime").coordination_lock("dev", KEY)
    try:
        lock.acquire(timeout=0)
    except Timeout:
        print("held")
    else:
        lock.release()
        print("free")


def run():
    with tempfile.TemporaryDirectory(prefix="svc-prep-wait-") as directory:
        root = Path(directory)
        process = subprocess.Popen([sys.executable, SCRIPT, "owner", directory])
        def lock_state():
            return subprocess.check_output([sys.executable, SCRIPT, "probe", directory], text=True).strip()
        try:
            wait_for(lambda: (root / "child-started").exists())
            signals = [signal.SIGINT, signal.SIGTERM, signal.SIGINT]
            for count, number in enumerate(signals, 1):
                process.send_signal(number)
                def acknowledged():
                    try:
                        return len(json.loads((root / "owner-signals.json").read_text())) == count
                    except (FileNotFoundError, json.JSONDecodeError):
                        return False
                wait_for(acknowledged)
            started = time.monotonic()
            while time.monotonic() - started < 3.3:
                assert process.poll() is None
                time.sleep(0.03)
            held = lock_state()
            assert held == "held" and not (root / "child-signals.json").exists()
            assert not (root / "child-exited").exists()
            (root / "finish").touch()
            assert process.wait(timeout=10) == 0
            record = json.loads((root / "settled.json").read_text())
            released = lock_state()
            assert record["state"] == "exited" and record["exit_code"] == 0 and released == "free"
            print(json.dumps({"probe": "existing-mechanics-wait-policy", "owner_signals": [int(x) for x in signals],
                              "child_signals": [], "observed_wait_seconds": round(time.monotonic() - started, 3),
                              "lock_during_wait": held, "lock_after_exit": released,
                              "final_state": record["state"], "exit_code": record["exit_code"],
                              "limit": "isolated owner adapter, not the future dev CLI"}, indent=2))
        finally:
            (root / "finish").touch()
            process.wait(timeout=25)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        run()
    else:
        {"child": child, "owner": owner, "probe": probe}[sys.argv[1]](Path(sys.argv[2]))

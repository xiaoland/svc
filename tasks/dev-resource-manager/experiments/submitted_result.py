"""Preparation probe: controller reference via file, independent of merged logs."""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "cli/src"))
from svc_cli._execution import ExecutionStore, LaunchSpec, OwnedExecution, start_isolated, wait_owned

controller = '''import os, sys
from pathlib import Path
print("ordinary stdout")
print("ordinary stderr", file=sys.stderr)
Path(os.environ["SVC_DEV_RESULT_FILE"]).write_text(sys.argv[1])
'''
results = []
with tempfile.TemporaryDirectory(prefix="svc-prep-submitted-") as directory:
    root = Path(directory)
    store = ExecutionStore(root / "runtime")
    for name, content in [("valid", '{"schema_version":1,"operation":{"id":"controller-op-42"}}'),
                          ("invalid", '{"schema_version":')]:
        result_path = root / (name + ".json")
        argv = (sys.executable, "-c", controller, content)
        published = store.publish(domain="dev", operation="act", subject="fixture",
                                  workspace_instance="prep", intent_digest="prep", coordination_key="b" * 64,
                                  argv=argv, cwd=root, capture="merged")
        env = dict(os.environ, SVC_DEV_RESULT_FILE=str(result_path))
        owned = start_isolated(store, published, LaunchSpec(argv, root, env))
        assert isinstance(owned, OwnedExecution)
        final = wait_owned(store, owned, timeout=5)
        assert final is not None and final.exit_code == 0
        log = (store.execution_dir(final.execution_id) / "output.log").read_text()
        assert "ordinary stdout" in log and "ordinary stderr" in log
        try:
            value = json.loads(result_path.read_text())
            assert value == {"schema_version": 1, "operation": {"id": "controller-op-42"}}
            outcome = "reference-parsed"
        except json.JSONDecodeError:
            outcome = "invalid-result-despite-zero-exit"
        results.append({"case": name, "exit_code": final.exit_code, "merged_log_contains_both_streams": True,
                        "outcome": outcome})
assert [x["outcome"] for x in results] == ["reference-parsed", "invalid-result-despite-zero-exit"]
print(json.dumps({"cases": results, "limit": "transport feasibility only; no future CLI result validation implemented"}, indent=2))

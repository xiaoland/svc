from __future__ import annotations

from types import SimpleNamespace

import pytest

import svc_cli.update as update
from svc_cli.errors import SvcError
from svc_cli.update import SelfUpdatePlan, apply_self_update, plan_self_update


class FakeDistribution:
    def __init__(self, version: str = "10.0.0", installer: str | None = "pip", direct_url: str | None = None) -> None:
        self.version = version
        self.installer = installer
        self.direct_url = direct_url

    def read_text(self, name: str) -> str | None:
        if name == "INSTALLER":
            return self.installer
        if name == "direct_url.json":
            return self.direct_url
        return None


def test_pip_plan_is_explicit_and_editable_or_unknown_installers_block(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(update, "distribution", lambda _: FakeDistribution())
        plan = plan_self_update()
    assert plan.status == "ready"
    assert plan.installer == "pip"
    assert plan.command[-3:] == ("install", "--upgrade", "sustainable-vibe-coding")

    editable = '{"dir_info": {"editable": true}}'
    with monkeypatch.context() as patch:
        patch.setattr(update, "distribution", lambda _: FakeDistribution(direct_url=editable))
        blocked = plan_self_update()
    assert "editable-install" in {item.code for item in blocked.blockers}

    with monkeypatch.context() as patch:
        patch.setattr(update, "distribution", lambda _: FakeDistribution(installer="uv"))
        unsupported = plan_self_update()
    assert "unsupported-installer" in {item.code for item in unsupported.blockers}


def test_apply_requires_exact_unchanged_plan_and_verifies_in_a_fresh_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = SelfUpdatePlan(
        "10.0.0",
        ("python", "-m", "pip", "install", "--upgrade", "sustainable-vibe-coding"),
        "pip",
        (),
    )
    with pytest.raises(SvcError, match="does not match"):
        apply_self_update(plan, "0" * 64)

    with monkeypatch.context() as patch:
        patch.setattr(update, "_installed_version", lambda: "10.0.0")
        patch.setattr(update, "_run_update", lambda _: SimpleNamespace(returncode=0, stderr=""))
        patch.setattr(update, "_fresh_installed_version", lambda: "10.1.0")
        result = apply_self_update(plan, plan.digest)
    assert result["status"] == "updated"
    assert result["previous_version"] == "10.0.0"
    assert result["installed_cli_version"] == "10.1.0"

    with monkeypatch.context() as patch:
        patch.setattr(update, "_installed_version", lambda: "10.0.1")
        with pytest.raises(SvcError, match="changed after planning"):
            apply_self_update(plan, plan.digest)

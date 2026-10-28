"""Install only the Pi bridge or configure an existing native manager."""

from __future__ import annotations

import os
import tempfile
from importlib.resources import files
from pathlib import Path

from ..._execution import _atomic_json
from ...errors import SvcError
from .models import IntegrationSetup
from .providers import configuration, home
from .transport import private_directory, private_file


def setup(
    provider: str, *, executable: str | None = None, socket_path: str | None = None
) -> IntegrationSetup:
    root = home()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_directory(root)
    if provider == "pi":
        if executable or socket_path:
            raise SvcError(
                "harness-setup-invalid", "Pi 接入不接受 CLI 或 socket 覆盖。"
            )
        agent = Path(os.environ.get("SVC_PI_AGENT_DIR", str(Path.home() / ".pi/agent")))
        destination = agent / "extensions/svc-dev.ts"
        destination.parent.mkdir(parents=True, exist_ok=True)
        marker = "// SVC managed native-task bridge v1"
        if (destination.exists() or destination.is_symlink()) and (
            destination.is_symlink() or not destination.read_text().startswith(marker)
        ):
            raise SvcError(
                "harness-extension-conflict", "svc-dev.ts 已存在且不属于 SVC，未覆盖。"
            )
        source = (
            files("svc_cli").joinpath("data/integrations/pi-extension.ts").read_text()
        )
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=destination.parent, prefix=".svc-dev-", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(source)
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return IntegrationSetup(
            provider,
            "installed",
            "Pi 接入已安装；在 Pi 中重新加载扩展或开启下次会话后生效。",
        )
    config = configuration()
    if executable is not None:
        if provider != "claude":
            raise SvcError(
                "harness-setup-invalid", "只有 Claude 接入使用原生 CLI 路径。"
            )
        path = Path(executable).expanduser().resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise SvcError(
                "harness-executable-invalid", "原生 CLI 必须是现有可执行文件。"
            )
        config[f"{provider}_cli"] = str(path)
    if socket_path is not None:
        if provider != "codex":
            raise SvcError(
                "harness-setup-invalid", "只有 Codex 接入使用共享控制 socket。"
            )
        path = Path(socket_path).expanduser()
        if not path.is_absolute():
            raise SvcError("harness-endpoint-invalid", "共享 socket 必须使用绝对路径。")
        path = path.resolve(strict=True)
        private_file(path, socket_file=True)
        config["codex_socket"] = str(path)
    if provider not in ("codex", "claude"):
        raise SvcError("harness-provider-invalid", "未知的执行来源。")
    _atomic_json(root / "config.json", {"schema_version": 1, "settings": config})
    return IntegrationSetup(
        provider, "configured", "原生执行来源配置已保存；没有启动或重启原管理器。"
    )

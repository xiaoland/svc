from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentProvider:
    name: str
    source_relative_dir: Path
    target_relative_dir: Path


PROVIDERS = {
    "codex": AgentProvider(
        name="codex",
        source_relative_dir=Path("src/.agents/codex-agents"),
        target_relative_dir=Path(".codex/agents"),
    ),
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_provider(name: str) -> AgentProvider:
    provider = PROVIDERS.get(name)
    if provider is None:
        supported = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"Unsupported agent provider '{name}'. Supported providers: {supported}")
    return provider


def resolve_source_dir(provider: str, repo_root: Path | None = None) -> Path:
    provider_config = get_provider(provider)
    root = (repo_root or default_repo_root()).resolve()
    source_dir = root / provider_config.source_relative_dir
    if not source_dir.exists():
        raise FileNotFoundError(f"Agent source directory does not exist: {source_dir}")
    return source_dir


def resolve_target_dir(
    provider: str,
    user_home: Path | None = None,
    target_dir: Path | None = None,
) -> Path:
    if target_dir is not None:
        return target_dir.resolve()

    provider_config = get_provider(provider)
    home = (user_home or Path.home()).resolve()
    return home / provider_config.target_relative_dir


def install_agents(
    provider: str = "codex",
    repo_root: Path | None = None,
    user_home: Path | None = None,
    target_dir: Path | None = None,
) -> list[Path]:
    source_dir = resolve_source_dir(provider=provider, repo_root=repo_root)
    destination_dir = resolve_target_dir(
        provider=provider,
        user_home=user_home,
        target_dir=target_dir,
    )

    source_files = sorted(
        path for path in source_dir.iterdir() if path.is_file() and path.suffix == ".toml"
    )
    if not source_files:
        raise FileNotFoundError(f"No agent TOML files found in source directory: {source_dir}")

    destination_dir.mkdir(parents=True, exist_ok=True)

    installed_paths: list[Path] = []
    for source_file in source_files:
        destination_file = destination_dir / source_file.name
        shutil.copy2(source_file, destination_file)
        installed_paths.append(destination_file)
    return installed_paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install repository-managed coding-agent definitions into user-scope config.",
    )
    parser.add_argument(
        "--provider",
        default="codex",
        choices=sorted(PROVIDERS),
        help="Coding-agent runtime provider to install for (default: codex).",
    )
    parser.add_argument(
        "--target-dir",
        default=None,
        help="Optional explicit install directory. Defaults to the provider's user-scope directory.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_dir = Path(args.target_dir).resolve() if args.target_dir else None
    installed_paths = install_agents(provider=args.provider, target_dir=target_dir)
    destination_dir = target_dir or resolve_target_dir(provider=args.provider)

    print(f"Installed {len(installed_paths)} {args.provider} agent files to {destination_dir}")
    for installed_path in installed_paths:
        print(f"- {installed_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

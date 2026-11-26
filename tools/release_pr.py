"""Prepare and verify an explicit release plan against main."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from tools.cli_release import cli_release_version
from tools.corpus import require_version
from tools.release_notes import HEADING, publication_date, release_section


PLAN_PATH = ".release-plan.json"
BRANCH_PREFIX = "release/"


@dataclass(frozen=True)
class Stream:
    tag_prefix: str
    changelog: str
    towncrier: str
    version_path: str
    version_key: tuple[str, ...] = ()
    parse_version: Callable[[object], str] = require_version

    def version(self, root: Path) -> str:
        path = root / self.version_path
        if not self.version_key:
            return require_version(path.read_text(encoding="utf-8").strip())
        value = tomllib.loads(path.read_text(encoding="utf-8"))
        for key in self.version_key:
            value = value[key]
        return self.parse_version(value)

    def queue(self, root: Path) -> Path:
        settings = tomllib.loads((root / self.towncrier).read_text(encoding="utf-8"))
        return root / settings["tool"]["towncrier"]["directory"]

    def tag(self, version: str) -> str:
        return f"{self.tag_prefix}-v{version}"


STREAMS = {
    "skills": Stream(
        "skills",
        "CORPUS_CHANGELOG.md",
        "towncrier.corpus.toml",
        "pyproject.toml",
        ("tool", "svc", "corpus", "version"),
    ),
    "cli": Stream(
        "svc-cli",
        "CLI_CHANGELOG.md",
        "towncrier.cli.toml",
        "cli/pyproject.toml",
        ("project", "version"),
        cli_release_version,
    ),
    "macos": Stream(
        "macos", "MACOS_CHANGELOG.md", "towncrier.macos.toml", "macos/VERSION"
    ),
}


@dataclass(frozen=True)
class Plan:
    base: str
    date: date
    releases: dict[str, str]

    @classmethod
    def read(cls, content: bytes) -> Plan:
        value = json.loads(content)
        if not isinstance(value, dict) or set(value) != {"base", "date", "releases"}:
            raise ValueError(f"{PLAN_PATH} must specify base, date and releases")
        base = value["base"]
        if not isinstance(base, str) or re.fullmatch(r"[a-f0-9]{40}", base) is None:
            raise ValueError(f"{PLAN_PATH} must contain a full base commit SHA")
        day = value["date"]
        if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ValueError(f"{PLAN_PATH} date must be YYYY-MM-DD")
        releases = value["releases"]
        if not isinstance(releases, dict) or not releases or releases.keys() - STREAMS:
            raise ValueError(f"{PLAN_PATH} must select at least one supported stream")
        plan = cls(
            base,
            date.fromisoformat(day),
            {
                name: require_version(releases[name])
                for name in STREAMS
                if name in releases
            },
        )
        if content != plan.render().encode("utf-8"):
            raise ValueError(
                f"generate {PLAN_PATH} with the release preparation command"
            )
        return plan

    def render(self) -> str:
        return (
            json.dumps(
                {
                    "base": self.base,
                    "date": self.date.isoformat(),
                    "releases": self.releases,
                },
                indent=2,
            )
            + "\n"
        )


def git(root: Path, *arguments: str) -> bytes:
    return subprocess.check_output(("git", *arguments), cwd=root)


def commit(root: Path, ref: str) -> str:
    return (
        git(root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
        .decode()
        .strip()
    )


def at_ref(root: Path, ref: str, path: str) -> bytes:
    return git(root, "show", f"{ref}:{path}")


def previous_plan(root: Path, base: str) -> bytes:
    if git(root, "ls-tree", "--name-only", base, "--", PLAN_PATH):
        return at_ref(root, base, PLAN_PATH)
    return b""


def files_in_queue(root: Path, stream: Stream) -> list[Path]:
    directory = stream.queue(root)
    return sorted(directory.glob("*.md"))


def check_version(
    root: Path, revision: str | None, stream: Stream, version: str
) -> None:
    if version != stream.version(root):
        raise ValueError(
            f"{stream.version_path} disagrees with planned version {version}"
        )
    tag = stream.tag(version)
    prefix = stream.tag("")
    tags = git(root, "tag", "--list", f"{prefix}*").decode().splitlines()
    if tag in tags:
        if commit(root, f"refs/tags/{tag}") != revision:
            raise ValueError(f"{tag} already points to another commit")
        return
    version_parts = [int(part) for part in version.split(".")]
    for published in tags:
        try:
            existing = require_version(published.removeprefix(prefix))
        except ValueError:
            continue
        if [int(part) for part in existing.split(".")] > version_parts:
            raise ValueError(f"{tag} must advance the published release {published}")


def check_changelog(current: bytes, previous: bytes, version: str, day: date) -> None:
    if not previous or current == previous or not current.endswith(previous):
        raise ValueError(
            "must prepend one release and preserve the entire published history"
        )
    new = current[: -len(previous)].decode("utf-8")
    if (
        not new.startswith(f"## [{version}] - {day.isoformat()}\n")
        or sum(HEADING.match(line) is not None for line in new.splitlines()) != 1
    ):
        raise ValueError("must prepend exactly one release section")
    if any(
        heading and heading.group(1) == version
        for heading in map(HEADING.match, previous.decode("utf-8").splitlines())
    ):
        raise ValueError(f"version {version} is already in the changelog")
    section = release_section(new, version)
    if publication_date(section) != day or not any(
        line.startswith("- ") for line in section.splitlines()[1:]
    ):
        raise ValueError("must include the planned date and at least one release note")


def check(root: Path, base_ref: str, *, pr_branch: str | None = None) -> Plan | None:
    base = commit(root, base_ref)
    path = root / PLAN_PATH
    prior = previous_plan(root, base)
    current = path.read_bytes() if path.exists() else b""
    if current != prior and not current:
        raise ValueError(f"{PLAN_PATH} cannot be removed or emptied")
    plan = Plan.read(current) if current != prior else None
    if pr_branch is not None and pr_branch.startswith(BRANCH_PREFIX) != (
        plan is not None
    ):
        raise ValueError(
            f"only a {BRANCH_PREFIX}* PR may change {PLAN_PATH}, and it must do so"
        )
    if plan is not None and plan.base != base:
        raise ValueError(f"{PLAN_PATH} was prepared against a different main commit")
    planned = plan.releases if plan is not None else {}
    revision = commit(root, "HEAD")
    for name, stream in STREAMS.items():
        previous = at_ref(root, base, stream.changelog)
        changelog = (root / stream.changelog).read_bytes()
        if name not in planned:
            if changelog != previous:
                raise ValueError(
                    f"{stream.changelog} changes require a prepared {name} release"
                )
            continue
        assert plan is not None
        version = planned[name]
        check_version(root, revision, stream, version)
        try:
            check_changelog(changelog, previous, version, plan.date)
        except ValueError as error:
            raise ValueError(f"{stream.changelog}: {error}") from error
        if files_in_queue(root, stream):
            raise ValueError(
                f"{name} release must consume its Towncrier fragment queue"
            )
    return plan


def prepare(root: Path, base_ref: str, selected: list[str], day: date) -> Plan:
    if git(root, "status", "--porcelain"):
        raise ValueError(
            "commit the release source and fragments before preparing the PR"
        )
    if check(root, base_ref) is not None:
        raise ValueError(
            f"reset the existing unpublished {PLAN_PATH} before preparing again"
        )
    base = commit(root, base_ref)
    revision = commit(root, "HEAD")
    git(root, "merge-base", "--is-ancestor", base, revision)
    releases = {
        name: STREAMS[name].version(root) for name in STREAMS if name in selected
    }
    plan = Plan(base, day, releases)
    rendered = []
    for name, version in releases.items():
        stream = STREAMS[name]
        fragments = files_in_queue(root, stream)
        if not fragments:
            raise ValueError(f"{name} has no queued Towncrier fragments")
        settings = tomllib.loads((root / stream.towncrier).read_text(encoding="utf-8"))
        kinds = {kind["directory"] for kind in settings["tool"]["towncrier"]["type"]}
        for fragment in fragments:
            if fragment.is_symlink() or not kinds.intersection(
                fragment.name.split(".")[1:-1]
            ):
                raise ValueError(
                    f"invalid Towncrier fragment: {fragment.relative_to(root)}"
                )
        check_version(root, None, stream, version)
        section = subprocess.check_output(
            (
                sys.executable,
                "-m",
                "towncrier",
                "build",
                "--draft",
                "--config",
                stream.towncrier,
                "--version",
                version,
                "--date",
                day.isoformat(),
            ),
            cwd=root,
        )
        previous = at_ref(root, base, stream.changelog)
        changelog = section.rstrip() + b"\n\n\n" + previous
        check_changelog(changelog, previous, version, day)
        rendered.append((root / stream.changelog, changelog, fragments))
    for path, changelog, fragments in rendered:
        path.write_bytes(changelog)
        for fragment in fragments:
            fragment.unlink()
    (root / PLAN_PATH).write_text(plan.render(), encoding="utf-8")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare")
    preparation.add_argument("streams", choices=STREAMS, nargs="+")
    preparation.add_argument("--base", default="origin/main")
    preparation.add_argument("--date", type=date.fromisoformat, default=date.today())
    validation = commands.add_parser("check")
    validation.add_argument("--base", default="origin/main")
    validation.add_argument("--pr-branch")
    validation.add_argument("--require-plan", action="store_true")
    validation.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    plan: Plan | None
    try:
        if args.command == "prepare":
            plan = prepare(root, args.base, args.streams, args.date)
        else:
            plan = check(root, args.base, pr_branch=args.pr_branch)
            if args.require_plan and plan is None:
                raise ValueError("this commit introduces no new release plan")
            if args.github_output is not None and plan is not None:
                with args.github_output.open("a", encoding="utf-8") as output:
                    for name, version in plan.releases.items():
                        print(f"{name}={version}", file=output)
        if plan is not None:
            print(plan.render(), end="")
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"release PR: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

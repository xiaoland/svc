from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from svc_cli.cli import EXIT_CONFLICT, EXIT_OK, main
from svc_cli.errors import SvcError
from svc_cli.task_packet import grow_task_packet


def invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(arguments)
    return code, stdout.getvalue(), stderr.getvalue()


def test_init_creates_only_an_absent_packet_and_reports_canonical_routes(
    tmp_path: Path,
) -> None:
    code, output, error = invoke(
        ["task", "init", "small", "--repo", str(tmp_path)]
    )

    packet = tmp_path / "tasks" / "small" / "packet.md"
    assert (code, error) == (EXIT_OK, "")
    assert packet.is_file()
    original = packet.read_bytes()
    assert "# small" in original.decode("utf-8")
    assert "task-packet/index.md" in output
    assert "templates/task-packet/packet.template.md" in output
    assert "shape-preflight" in output
    assert "svc task grow small" in output

    code, _, error = invoke(
        ["task", "init", "small", "--repo", str(tmp_path)]
    )
    assert code == EXIT_CONFLICT
    assert "task-packet-exists" in error
    assert packet.read_bytes() == original


def test_grow_sorts_observed_bounded_entries_and_reports_unknown_entries(
    tmp_path: Path,
) -> None:
    packet = tmp_path / "tasks" / "mixed"
    packet.mkdir(parents=True)
    (packet / "packet.md").write_text("# mixed\n", encoding="utf-8")
    (packet / "track-build.md").write_text("# build\n", encoding="utf-8")
    (packet / "track-build").mkdir()
    (packet / "track-build" / "slice.md").write_text("slice\n", encoding="utf-8")
    (packet / "cells").mkdir()
    (packet / "cells" / "build-verify.md").write_text("cell\n", encoding="utf-8")
    (packet / "cells" / "build-verify").mkdir()
    (packet / "cells" / "build-verify" / "receipt.md").write_text(
        "receipt\n", encoding="utf-8"
    )
    (packet / "mystery.md").write_text("unknown\n", encoding="utf-8")

    output = grow_task_packet(tmp_path, "mixed").decode("utf-8")
    assert "track-build [directory]" in output
    assert "track-build/slice.md" in output
    assert "cells/build-verify/receipt.md" in output
    assert "mystery.md" in output
    assert "Work-topology questions:" in output
    assert "Information-topology questions:" in output
    assert "No semantic decision was made" in output
    assert "No file was changed" in output
    assert "task-packet/growth.md" in output
    assert "templates/task-packet/index.md" in output

    inventory = output.split("Observed inventory (", 1)[1].split(
        "Inventory truncated:", 1
    )[0]
    listed = [line.strip().split(" [", 1)[0] for line in inventory.splitlines() if line.startswith("  ")]
    assert listed == sorted(listed)


def test_grow_reports_symlinks_without_following_and_does_not_write(
    tmp_path: Path,
) -> None:
    packet = tmp_path / "tasks" / "links"
    packet.mkdir(parents=True)
    (packet / "packet.md").write_text("# links\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("outside-secret\n", encoding="utf-8")
    (packet / "outside.md").symlink_to(outside)
    before = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if not path.is_symlink()
    )

    output = grow_task_packet(tmp_path, "links").decode("utf-8")

    assert "outside.md [symlink (not followed)]" in output
    assert "outside-secret" not in output
    after = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if not path.is_symlink()
    )
    assert after == before


def test_grow_reports_explicit_truncation_at_100_entries(tmp_path: Path) -> None:
    packet = tmp_path / "tasks" / "many"
    packet.mkdir(parents=True)
    (packet / "packet.md").write_text("# many\n", encoding="utf-8")
    for index in range(105):
        (packet / f"entry-{index:03d}.md").write_text("x\n", encoding="utf-8")

    output = grow_task_packet(tmp_path, "many").decode("utf-8")
    inventory = output.split("Observed inventory (", 1)[1].split(
        "Inventory truncated:", 1
    )[0]
    listed = [line for line in inventory.splitlines() if line.startswith("  ")]
    assert len(listed) == 100
    assert (
        "Inventory truncated: yes (showing 100 entries; at least 101 exist; "
        "scan stopped at the observation limit)."
    ) in output


def test_grow_stops_scanning_at_the_observation_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet = tmp_path / "tasks" / "bounded"
    packet.mkdir(parents=True)
    (packet / "packet.md").write_text("# bounded\n", encoding="utf-8")
    for index in range(500):
        (packet / f"entry-{index:03d}.md").write_text("x\n", encoding="utf-8")

    real_scandir = __import__("os").scandir
    observations = 0

    class CountingScandir:
        def __init__(self, path: Path) -> None:
            self._iterator = real_scandir(path)

        def __enter__(self) -> CountingScandir:
            self._iterator.__enter__()
            return self

        def __exit__(self, *args: object) -> None:
            self._iterator.__exit__(*args)

        def __iter__(self) -> CountingScandir:
            return self

        def __next__(self):  # type: ignore[no-untyped-def]
            nonlocal observations
            observations += 1
            if observations > 101:
                raise AssertionError("inventory exceeded its observation budget")
            return next(self._iterator)

    monkeypatch.setattr(
        "svc_cli.task_packet.os.scandir", lambda path: CountingScandir(path)
    )

    output = grow_task_packet(tmp_path, "bounded").decode("utf-8")

    assert observations <= 101
    assert "Inventory truncated: yes" in output
    assert "packet.md [regular file]" in output


def test_grow_requires_a_regular_packet_and_rejects_symlinked_parent(
    tmp_path: Path,
) -> None:
    with pytest.raises(SvcError) as missing:
        grow_task_packet(tmp_path, "missing")
    assert missing.value.code == "task-packet-not-found"

    packet = tmp_path / "tasks" / "not-file"
    packet.mkdir(parents=True)
    with pytest.raises(SvcError) as directory:
        grow_task_packet(tmp_path, "not-file")
    assert directory.value.code == "task-packet-not-found"

    unsafe_root = tmp_path / "unsafe-root"
    real_task = unsafe_root / "tasks" / "real"
    real_task.mkdir(parents=True)
    (real_task / "packet.md").write_text("# real\n", encoding="utf-8")
    (unsafe_root / "tasks" / "alias").symlink_to(real_task, target_is_directory=True)
    with pytest.raises(SvcError) as unsafe:
        grow_task_packet(unsafe_root, "alias")
    assert unsafe.value.code == "task-packet-parent-unsafe"

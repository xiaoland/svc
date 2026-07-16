from __future__ import annotations

import io
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from svc_cli.telemetry.agent_threads import (
    CaptureEvidence,
    ProviderContext,
    ResolvedThread,
    SourceArtifact,
    SourceSnapshot,
    TextOccurrence,
    ThreadSelection,
)
from svc_cli.telemetry import archive as archive_module
from svc_cli.telemetry.archive import write_agent_thread_archive
from svc_cli.telemetry.task_packets import _unsafe_link_info, copy_packet_file, iter_packet_files
from svc_cli.errors import SvcError


class FakeProvider:
    provider_id = "fake"

    def __init__(
        self,
        payload: bytes = b"native\n",
        error: Exception | None = None,
        occurrences=(),
        mutate_source: bool = False,
        replace_source_same_bytes: bool = False,
    ):
        self.payload = payload
        self.error = error
        self.occurrences = tuple(occurrences)
        self.mutate_source = mutate_source
        self.replace_source_same_bytes = replace_source_same_bytes

    def resolve(self, context, selection):
        return ResolvedThread(
            provider_id="fake",
            adapter_id="fixture",
            source_format="fixture-json",
            thread_id=selection.thread_id or "source",
            source_state="available",
            artifact=SourceArtifact(Path(context.home) / "native.json", "capture/native.json", "application/json"),
        )

    def stream_capture(self, resolved, raw_output, index_output):
        info = resolved.artifact.source_path.lstat()
        source_snapshot = SourceSnapshot(
            device=info.st_dev,
            inode=info.st_ino,
            size=info.st_size,
            mtime_ns=info.st_mtime_ns,
        )
        raw_output.write(self.payload)
        index_output.write(b'{"records":1}')
        if self.error:
            raise self.error
        if self.mutate_source:
            resolved.artifact.source_path.write_bytes(b"changed after capture")
        if self.replace_source_same_bytes:
            replacement = resolved.artifact.source_path.with_name("replacement-native.json")
            replacement.write_bytes(self.payload)
            replacement.replace(resolved.artifact.source_path)
        return CaptureEvidence(
            source_sha256=hashlib.sha256(self.payload).hexdigest(),
            source_bytes=len(self.payload),
            record_counts={"messages": 1},
            capabilities={"fixture": "full"},
            occurrences=self.occurrences,
            warnings=(),
            source_snapshot=source_snapshot,
        )


class TelemetryArchiveTests(unittest.TestCase):
    @staticmethod
    def output(root: Path, name: str) -> Path:
        destination = root.parent / "exports"
        destination.mkdir(exist_ok=True)
        return destination / name

    def archive(self, root: Path, provider: FakeProvider, name="capture.zip"):
        (root / "native.json").write_bytes(provider.payload)
        return write_agent_thread_archive(
            provider,
            ProviderContext(home=root),
            ThreadSelection(thread_id="thread-1"),
            root,
            self.output(root, name),
        )

    def test_archive_contains_provider_index_manifest_and_task_material(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            packet = root / "tasks" / "one"
            packet.mkdir(parents=True)
            (packet / "packet.md").write_text("objective", encoding="utf-8")
            provider = FakeProvider(occurrences=(TextOccurrence("see tasks/one/packet.md", 4, "message", "user", "text"),))

            manifest = self.archive(root, provider)
            with zipfile.ZipFile(self.output(root, "capture.zip")) as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "providers/fake/capture/native.json",
                        "thread/index.json",
                        "task-packets/tasks/one/packet.md",
                        "manifest.json",
                    ],
                )
                self.assertEqual(archive.read("providers/fake/capture/native.json"), b"native\n")
                self.assertEqual(archive.read("task-packets/tasks/one/packet.md"), b"objective")
                self.assertEqual(json.loads(archive.read("manifest.json")), manifest)
            self.assertEqual(manifest["artifact"]["sha256"], hashlib.sha256(b"native\n").hexdigest())
            self.assertEqual(manifest["artifact"]["bytes"], len(b"native\n"))
            self.assertEqual(manifest["task_packets"][0]["occurrences"][0]["source_line"], 4)
            self.assertEqual(manifest["task_packets"][0]["occurrences"][0]["field_path"], "text")
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(self.output(root, "capture.zip").stat().st_mode), 0o600)

    def test_archive_has_stable_evidence_layout_and_does_not_modify_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            packet = root / "tasks" / "one"
            packet.mkdir(parents=True)
            (packet / "packet.md").write_text("objective", encoding="utf-8")
            provider = FakeProvider(occurrences=(TextOccurrence("tasks/one"),))
            before = (packet / "packet.md").read_bytes()
            self.archive(root, provider, "one.zip")
            with zipfile.ZipFile(self.output(root, "one.zip")) as archive:
                first_manifest = json.loads(archive.read("manifest.json"))
                first_raw = archive.read("providers/fake/capture/native.json")
            self.archive(root, provider, "two.zip")
            with zipfile.ZipFile(self.output(root, "two.zip")) as archive:
                second_manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(first_raw, archive.read("providers/fake/capture/native.json"))
            first_manifest.pop("captured_at")
            second_manifest.pop("captured_at")
            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual((packet / "packet.md").read_bytes(), before)

    def test_existing_output_and_invalid_suffix_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            output = self.output(root, "capture.zip")
            output.write_bytes(b"sentinel")
            with self.assertRaises(FileExistsError):
                self.archive(root, FakeProvider())
            self.assertEqual(output.read_bytes(), b"sentinel")
            with self.assertRaises(ValueError):
                self.archive(root, FakeProvider(), "capture.tar")

    def test_provider_error_cleans_temporary_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            with self.assertRaisesRegex(RuntimeError, "capture failed"):
                self.archive(root, FakeProvider(error=RuntimeError("capture failed")))
            self.assertEqual(list(self.output(root, "capture.zip").parent.glob(".capture.zip.*.tmp")), [])
            self.assertEqual((root / "native.json").read_bytes(), b"native\n")

    def test_invalid_traversal_and_symlink_candidates_are_manifest_warnings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            packet = root / "tasks" / "safe"
            packet.mkdir(parents=True)
            (packet / "packet.md").write_text("safe", encoding="utf-8")
            outside = root.parent / "outside-task.md"
            outside.write_text("secret", encoding="utf-8")
            link = root / "tasks" / "escape"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlinks unavailable")
            occurrences = (
                TextOccurrence("tasks/../outside-task.md"),
                TextOccurrence("/tasks/safe/packet.md"),
                TextOccurrence("tasks/escape/packet.md"),
                TextOccurrence("tasks/safe/packet.md"),
            )
            manifest = self.archive(root, FakeProvider(occurrences=occurrences))
            codes = {warning["code"] for warning in manifest["warnings"]}
            self.assertIn("task_packet_invalid_path", codes)
            self.assertIn("task_packet_symlink_escape", codes)
            self.assertNotIn("task_packet_missing", codes)

    def test_multiple_roots_are_included_and_duplicate_occurrences_merge(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            for name in ("one", "two"):
                packet = root / "tasks" / name
                packet.mkdir(parents=True)
                (packet / "packet.md").write_text(name, encoding="utf-8")
            provider = FakeProvider(occurrences=(TextOccurrence("tasks/one tasks/one/packet.md tasks/two"),))
            manifest = self.archive(root, provider)
            self.assertEqual([item["root"] for item in manifest["task_packets"]], ["tasks/one", "tasks/two"])
            with zipfile.ZipFile(self.output(root, "capture.zip")) as archive:
                self.assertEqual(archive.read("task-packets/tasks/one/packet.md"), b"one")
                self.assertEqual(archive.read("task-packets/tasks/two/packet.md"), b"two")

    def test_nested_packet_tree_and_missing_reference_are_recorded_exactly(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            packet = root / "tasks" / "one"
            nested = packet / "evidence"
            nested.mkdir(parents=True)
            (packet / "packet.md").write_text("one", encoding="utf-8")
            (nested / "note.txt").write_text("nested", encoding="utf-8")
            manifest = self.archive(
                root,
                FakeProvider(
                    occurrences=(
                        TextOccurrence("tasks/one/evidence/note.txt", 7, "message", "assistant", "payload.content"),
                        TextOccurrence("tasks/missing/packet.md", 8, "message", "user", "payload.content"),
                    )
                ),
            )
            with zipfile.ZipFile(self.output(root, "capture.zip")) as archive:
                self.assertEqual(archive.read("task-packets/tasks/one/evidence/note.txt"), b"nested")
            self.assertEqual(manifest["task_packets"][0]["occurrences"][0]["path"], "tasks/one/evidence/note.txt")
            self.assertIn("task_packet_missing", {warning["code"] for warning in manifest["warnings"]})

    def test_output_inside_repository_is_refused_before_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            (root / "tasks").mkdir()
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                write_agent_thread_archive(
                    FakeProvider(),
                    ProviderContext(home=root),
                    ThreadSelection(thread_id="thread-1"),
                    root,
                    root / "tasks" / "capture.zip",
                )
            self.assertFalse((root / "tasks" / "capture.zip").exists())

    def test_symlink_output_parent_is_refused_before_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            exports = root.parent / "exports"
            exports.mkdir()
            linked = root.parent / "exports-link"
            try:
                linked.symlink_to(exports, target_is_directory=True)
            except OSError:
                self.skipTest("symlinks unavailable")
            (root / "native.json").write_bytes(b"native\n")
            with self.assertRaisesRegex(ValueError, "non-link directory"):
                write_agent_thread_archive(
                    FakeProvider(),
                    ProviderContext(home=root),
                    ThreadSelection(thread_id="thread-1"),
                    root,
                    linked / "capture.zip",
                )
            self.assertFalse((exports / "capture.zip").exists())

    def test_forced_non_dirfd_fallback_retains_no_overwrite_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            output = self.output(root, "capture.zip")
            with patch.object(archive_module, "_supports_anchored_publication", return_value=False):
                self.archive(root, FakeProvider())
                with self.assertRaises(FileExistsError):
                    self.archive(root, FakeProvider())
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read("providers/fake/capture/native.json"), b"native\n")

    def test_source_change_after_capture_prevents_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            with self.assertRaises(SvcError) as raised:
                self.archive(root, FakeProvider(mutate_source=True))
            self.assertEqual(raised.exception.code, "thread-source-mutated")
            self.assertFalse(self.output(root, "capture.zip").exists())

    def test_same_byte_source_replacement_after_capture_prevents_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            with self.assertRaises(SvcError) as raised:
                self.archive(root, FakeProvider(replace_source_same_bytes=True))
            self.assertEqual(raised.exception.code, "thread-source-mutated")
            self.assertFalse(self.output(root, "capture.zip").exists())

    def test_source_change_after_atomic_commit_keeps_the_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            output = self.output(root, "capture.zip")
            if archive_module._supports_anchored_publication():
                original_publish = archive_module._publish_anchored_without_overwrite

                def publish_then_mutate(parent_fd: int, temp_name: str, output_name: str) -> None:
                    original_publish(parent_fd, temp_name, output_name)
                    (root / "native.json").write_bytes(b"changed after publish")

                patch_target = "_publish_anchored_without_overwrite"
            else:
                original_publish = archive_module._publish_without_overwrite

                def publish_then_mutate(temp_path: Path, destination: Path) -> None:
                    original_publish(temp_path, destination)
                    (root / "native.json").write_bytes(b"changed after publish")

                patch_target = "_publish_without_overwrite"
            with patch.object(archive_module, patch_target, side_effect=publish_then_mutate):
                self.archive(root, FakeProvider())
            self.assertEqual((root / "native.json").read_bytes(), b"changed after publish")
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read("providers/fake/capture/native.json"), b"native\n")

    def test_source_change_after_zip_fsync_prevents_atomic_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            output = self.output(root, "capture.zip")
            original_verify_parent = archive_module._verify_output_parent
            checks = 0

            def mutate_before_final_source_check(parent, identity, repository):
                nonlocal checks
                checks += 1
                if checks == 2:
                    (root / "native.json").write_bytes(b"changed before commit")
                return original_verify_parent(parent, identity, repository)

            with patch.object(archive_module, "_verify_output_parent", side_effect=mutate_before_final_source_check):
                with self.assertRaises(SvcError) as raised:
                    self.archive(root, FakeProvider())
            self.assertEqual(raised.exception.code, "thread-source-mutated")
            self.assertFalse(output.exists())

    def test_output_replacement_during_publication_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            output = self.output(root, "capture.zip")
            if archive_module._supports_anchored_publication():
                original_publish = archive_module._publish_anchored_without_overwrite

                def publish_then_replace(parent_fd: int, temp_name: str, output_name: str) -> None:
                    original_publish(parent_fd, temp_name, output_name)
                    os.unlink(output_name, dir_fd=parent_fd)
                    replacement = os.open(
                        output_name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=parent_fd,
                    )
                    try:
                        os.write(replacement, b"replacement")
                    finally:
                        os.close(replacement)

                patch_target = "_publish_anchored_without_overwrite"
            else:
                original_publish = archive_module._publish_without_overwrite

                def publish_then_replace(temp_path: Path, destination: Path) -> None:
                    original_publish(temp_path, destination)
                    destination.unlink()
                    destination.write_bytes(b"replacement")

                patch_target = "_publish_without_overwrite"
            with patch.object(archive_module, patch_target, side_effect=publish_then_replace):
                with self.assertRaises(SvcError) as raised:
                    self.archive(root, FakeProvider())
            self.assertEqual(raised.exception.code, "archive-output-mutated")
            self.assertEqual(output.read_bytes(), b"replacement")

    def test_task_packet_change_after_enumeration_aborts_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            packet = root / "tasks" / "one"
            packet.mkdir(parents=True)
            packet_file = packet / "packet.md"
            packet_file.write_text("before", encoding="utf-8")
            output = self.output(root, "capture.zip")
            provider = FakeProvider(occurrences=(TextOccurrence("tasks/one/packet.md"),))
            original_copy = archive_module.copy_packet_file
            did_mutate = False

            def copy_after_mutation(packet_member, tasks_root, destination):
                nonlocal did_mutate
                if not did_mutate:
                    did_mutate = True
                    packet_file.write_text("after", encoding="utf-8")
                return original_copy(packet_member, tasks_root, destination)

            with patch.object(archive_module, "copy_packet_file", side_effect=copy_after_mutation):
                with self.assertRaises(SvcError) as raised:
                    self.archive(root, provider)
            self.assertEqual(raised.exception.code, "task-packet-mutated")
            self.assertFalse(output.exists())

    def test_provider_control_characters_and_invalid_evidence_are_refused(self):
        with self.assertRaises(ValueError):
            SourceArtifact(Path("native.json"), "capture\x00native.json", "application/json")

        class InvalidEvidenceProvider(FakeProvider):
            def stream_capture(self, resolved, raw_output, index_output):
                raw_output.write(self.payload)
                index_output.write(b"{}")
                return CaptureEvidence(
                    source_sha256="not-a-sha256",
                    source_bytes=len(self.payload),
                    record_counts={},
                    capabilities={},
                    occurrences=(),
                    warnings=(),
                )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                self.archive(root, InvalidEvidenceProvider())
            self.assertFalse(self.output(root, "capture.zip").exists())

    def test_tasks_directory_itself_is_not_a_packet_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            tasks = root / "tasks"
            tasks.mkdir()
            (tasks / "packet.md").write_text("container marker", encoding="utf-8")
            manifest = self.archive(root, FakeProvider(occurrences=(TextOccurrence("see tasks/packet.md"),)))
            self.assertEqual(manifest["task_packets"], [])
            self.assertIn("task_packet_invalid_candidate", {item["code"] for item in manifest["warnings"]})

    def test_invalid_windows_lexical_components_are_warnings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            (root / "tasks").mkdir()
            occurrences = (
                TextOccurrence("tasks/bad:name/packet.md"),
                TextOccurrence("tasks/CON/packet.md"),
                TextOccurrence("tasks/has*wildcard/packet.md"),
            )
            manifest = self.archive(root, FakeProvider(occurrences=occurrences))
            warnings = manifest["warnings"]
            self.assertEqual(manifest["task_packets"], [])
            self.assertEqual(
                {warning["details"]["path"] for warning in warnings if warning["code"] == "task_packet_invalid_path"},
                {"tasks/bad:name/packet.md", "tasks/CON/packet.md", "tasks/has*wildcard/packet.md"},
            )

    def test_packet_file_identity_and_tree_snapshot_reject_changes_after_enumeration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            tasks = root / "tasks"
            packet = tasks / "one"
            packet.mkdir(parents=True)
            member = packet / "packet.md"
            member.write_text("before", encoding="utf-8")
            enumeration = iter_packet_files(packet, tasks)

            replacement = packet / "replacement.tmp"
            replacement.write_text("after", encoding="utf-8")
            replacement.replace(member)
            with self.assertRaises(ValueError):
                copy_packet_file(next(iter(enumeration)), tasks, io.BytesIO())

            with self.assertRaises(ValueError):
                enumeration.verify(tasks)

    def test_packet_tree_snapshot_rejects_added_member(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repository"
            root.mkdir()
            tasks = root / "tasks"
            packet = tasks / "one"
            packet.mkdir(parents=True)
            (packet / "packet.md").write_text("before", encoding="utf-8")
            enumeration = iter_packet_files(packet, tasks)
            (packet / "new.md").write_text("new", encoding="utf-8")
            with self.assertRaises(ValueError):
                enumeration.verify(tasks)

    def test_reparse_point_attribute_is_rejected(self):
        fixture = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0x0400)
        self.assertTrue(_unsafe_link_info(fixture))

    def test_source_artifact_rejects_windows_separator(self):
        with self.assertRaises(ValueError):
            SourceArtifact(Path("native.json"), "capture\\native.json", "application/json")


if __name__ == "__main__":
    unittest.main()

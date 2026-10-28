"""One bounded sampling set, attributed before execution/project aggregation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import psutil  # type: ignore[import-untyped]

from .._execution import ACTIVE_STATES, ExecutionRecord
from ..errors import SvcError
from .darwin import DarwinMetrics, ProcessCounters
from .models import ProcessUsage, ProjectActivity, ResourceActivity
from .process_group import ProcessGroup
from .provenance import ExecutionOrigin

ProcessKey = tuple[int, float]
MAX_ROOTS = 64
MAX_PROCESSES = 256


def _counter_rate(
    before: ProcessCounters | None,
    after: ProcessCounters | None,
    name: str,
    interval: float,
) -> float | None:
    if before is None or after is None:
        return None
    delta = getattr(after, name) - getattr(before, name)
    return round(delta / interval, 2) if delta >= 0 else None


@dataclass
class Candidate:
    record: ExecutionRecord
    origin: ExecutionOrigin | None
    root: Any
    key: ProcessKey
    issues: list[str] = field(default_factory=list)


@dataclass
class PendingProcess:
    process: Any
    owners: list[str]
    parent: int
    native: ProcessCounters | None
    sampled_at: float


def aggregate(
    usages: list[ProcessUsage], issues: tuple[str, ...] = ()
) -> ProcessUsage | None:
    if not usages:
        return None

    def total(name: str) -> Any:
        values = [getattr(item, name) for item in usages]
        return None if any(value is None for value in values) else sum(values)

    all_issues = tuple(
        dict.fromkeys((*issues, *(issue for item in usages for issue in item.issues)))
    )
    return ProcessUsage(
        cpu_percent=round(sum(item.cpu_percent for item in usages), 1),
        rss_bytes=sum(item.rss_bytes for item in usages),
        process_count=sum(item.process_count for item in usages),
        memory_footprint_bytes=total("memory_footprint_bytes"),
        disk_read_bytes_per_second=total("disk_read_bytes_per_second"),
        disk_write_bytes_per_second=total("disk_write_bytes_per_second"),
        pageins_per_second=total("pageins_per_second"),
        complete=not all_issues and all(item.complete for item in usages),
        issues=all_issues,
    )


class UsageSampler:
    def __init__(self, native: DarwinMetrics | None) -> None:
        self.native = native
        self.candidates: dict[str, Candidate] = {}
        self.pending: dict[ProcessKey, PendingProcess] = {}
        self.processes: dict[int, Any] = {}
        self.issues: list[str] = []

    def prepare(
        self,
        record: ExecutionRecord,
        origin: ExecutionOrigin | None,
        created_at: float | None,
        *,
        managed_owner_live: bool,
    ) -> None:
        if not record.process_id or created_at is None:
            return
        if record.state not in ACTIVE_STATES | {"released", "owner-lost"}:
            return
        if len(self.candidates) >= MAX_ROOTS:
            self.issues.append("用量观察限于 64 个已验证执行根，其余未统计。")
            return
        try:
            root = psutil.Process(record.process_id)
            if root.create_time() != created_at:
                if record.state in ACTIVE_STATES:
                    self.issues.append(
                        f"{record.execution_id}: 进程身份已变化，未采样历史 PID。"
                    )
                return
            candidate = Candidate(record, origin, root, (root.pid, created_at))
            self.candidates[record.execution_id] = candidate
            # An unreaped managed leader can be a zombie while its workers have
            # been reparented. Its reserved process group retains that relation.
            if self.native is not None and (
                managed_owner_live or record.domain == "dev"
            ):
                pids, truncated = ProcessGroup().sample_members(root.pid, MAX_PROCESSES)
                if truncated:
                    candidate.issues.append("当前进程组超过 256 项，统计不完整。")
            elif self.native is not None:
                pids, truncated = self.native.descendants(root.pid, MAX_PROCESSES)
                if truncated:
                    candidate.issues.append("后代超过本轮观察预算，统计不完整。")
            else:
                family = [root, *root.children(recursive=True)]
                pids = [process.pid for process in family[:MAX_PROCESSES]]
                if len(family) > MAX_PROCESSES:
                    candidate.issues.append("后代超过本轮观察预算，统计不完整。")
            self.processes[root.pid] = root
            for pid in pids:
                try:
                    if len(self.pending) >= MAX_PROCESSES and pid not in self.processes:
                        candidate.issues.append(
                            "本轮达到 256 个进程采样上限，统计不完整。"
                        )
                        continue
                    process = self.processes.get(pid)
                    if process is None:
                        process = psutil.Process(pid)
                        self.processes[pid] = process
                    if process.status() == psutil.STATUS_ZOMBIE:
                        continue
                    key = (process.pid, process.create_time())
                    if key in self.pending:
                        self.pending[key].owners.append(record.execution_id)
                        continue
                    if len(self.pending) >= MAX_PROCESSES:
                        candidate.issues.append(
                            "本轮达到 256 个进程采样上限，统计不完整。"
                        )
                        break
                    process.cpu_percent(None)
                    before = None
                    if self.native is not None:
                        try:
                            before = self.native.process(process.pid)
                        except OSError as error:
                            candidate.issues.append(str(error))
                    self.pending[key] = PendingProcess(
                        process,
                        [record.execution_id],
                        process.ppid(),
                        before,
                        time.monotonic(),
                    )
                except psutil.Error as error:
                    candidate.issues.append(str(error))
        except (psutil.Error, SvcError, OSError) as error:
            if record.state in ACTIVE_STATES:
                self.issues.append(f"{record.execution_id}: {error}")

    def finish(self) -> dict[str, ProcessUsage | None]:
        collected: dict[str, list[ProcessUsage]] = {key: [] for key in self.candidates}
        roots = {item.key: key for key, item in self.candidates.items()}
        parents = {key[0]: item.parent for key, item in self.pending.items()}
        for key, pending in self.pending.items():
            owner = self._closest_owner(key, pending, roots, parents)
            if owner is None:
                self.issues.append(
                    f"PID {key[0]}: 来源重叠且无法判定最近执行根，未重复计入项目。"
                )
                continue
            candidate = self.candidates[owner]
            try:
                process = pending.process
                if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                    candidate.issues.append("部分进程在采样期间结束，统计不完整。")
                    continue
                memory = process.memory_info()
                cpu = process.cpu_percent(None)
                after = None
                if self.native is not None and pending.native is not None:
                    try:
                        after = self.native.process(process.pid)
                        if after.start != pending.native.start:
                            candidate.issues.append("进程身份在采样期间变化，未计入。")
                            continue
                    except OSError as error:
                        candidate.issues.append(str(error))
                interval = time.monotonic() - pending.sampled_at

                collected[owner].append(
                    ProcessUsage(
                        cpu_percent=cpu,
                        rss_bytes=memory.rss,
                        process_count=1,
                        memory_footprint_bytes=after.footprint
                        if after is not None
                        else None,
                        disk_read_bytes_per_second=_counter_rate(
                            pending.native, after, "read", interval
                        ),
                        disk_write_bytes_per_second=_counter_rate(
                            pending.native, after, "write", interval
                        ),
                        pageins_per_second=_counter_rate(
                            pending.native, after, "pageins", interval
                        ),
                        complete=after is not None,
                    )
                )
            except psutil.Error as error:
                candidate.issues.append(str(error))
        results: dict[str, ProcessUsage | None] = {}
        for execution_id, candidate in self.candidates.items():
            try:
                root_live = candidate.root.is_running()
            except psutil.Error as error:
                root_live = False
                candidate.issues.append(str(error))
            if not root_live:
                candidate.issues.append("执行根在采样期间结束，未继续归属其后代。")
                collected[execution_id] = []
            results[execution_id] = aggregate(
                collected[execution_id], tuple(candidate.issues)
            )
            self.issues.extend(f"{execution_id}: {issue}" for issue in candidate.issues)
        return results

    def _closest_owner(
        self,
        key: ProcessKey,
        pending: PendingProcess,
        roots: dict[ProcessKey, str],
        parents: dict[int, int],
    ) -> str | None:
        direct = roots.get(key)
        if direct in pending.owners:
            return direct
        parent = pending.parent
        seen: set[int] = set()
        while parent > 1 and parent not in seen:
            seen.add(parent)
            matching = [
                owner
                for root, owner in roots.items()
                if root[0] == parent and owner in pending.owners
            ]
            if len(matching) == 1:
                return matching[0]
            parent = parents.get(parent, 0)
        return pending.owners[0] if len(pending.owners) == 1 else None

    def resources(
        self, usages: dict[str, ProcessUsage | None]
    ) -> tuple[ResourceActivity, ...]:
        return tuple(
            ResourceActivity(
                execution_id,
                item.origin.project_path,
                item.origin.resource_entry_id,
                item.origin.resource_key,
                usages[execution_id],
            )
            for execution_id, item in self.candidates.items()
            if item.record.state == "released"
            and item.origin is not None
            and item.origin.resource_entry_id is not None
            and item.origin.resource_key is not None
            and usages.get(execution_id) is not None
        )


def projects(
    records: list[ExecutionRecord],
    origins: dict[str, ExecutionOrigin | None],
    resources: tuple[ResourceActivity, ...],
    usages: dict[str, ProcessUsage | None],
) -> tuple[ProjectActivity, ...]:
    groups: dict[str | None, list[ExecutionRecord]] = {}
    observed_ids = set(usages)
    for record in records:
        if record.state in ACTIVE_STATES or record.execution_id in observed_ids:
            origin = origins.get(record.execution_id)
            groups.setdefault(origin.project_path if origin else None, []).append(
                record
            )
    result = []
    for project, members in groups.items():
        notes = tuple(
            f"{item.subject}: 未取得可验证的进程用量。"
            for item in members
            if usages.get(item.execution_id) is None
        )
        measured = [
            value
            for item in members
            if (value := usages.get(item.execution_id)) is not None
        ]
        result.append(
            ProjectActivity(
                project,
                sum(
                    item.state in ACTIVE_STATES
                    or (
                        item.state == "owner-lost"
                        and usages.get(item.execution_id) is not None
                    )
                    for item in members
                ),
                sum(item.project_path == project for item in resources),
                aggregate(measured, notes),
                notes,
            )
        )
    return tuple(result)

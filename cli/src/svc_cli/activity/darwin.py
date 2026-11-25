"""Bounded macOS accounting without task ports or address-space walks."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass


class _RUsageV2(ctypes.Structure):
    _fields_ = [("uuid", ctypes.c_ubyte * 16)] + [
        (name, ctypes.c_uint64)
        for name in (
            "user",
            "system",
            "wakes",
            "interrupts",
            "pageins",
            "wired",
            "rss",
            "footprint",
            "start",
            "exit",
            "child_user",
            "child_system",
            "child_wakes",
            "child_interrupts",
            "child_pageins",
            "child_elapsed",
            "read",
            "write",
        )
    ]


class _VMStatistics64(ctypes.Structure):
    _fields_ = (
        [(name, ctypes.c_uint32) for name in ("free", "active", "inactive", "wired")]
        + [
            (name, ctypes.c_uint64)
            for name in (
                "zero_fill",
                "reactivations",
                "pageins",
                "pageouts",
                "faults",
                "cow_faults",
                "lookups",
                "hits",
                "purges",
            )
        ]
        + [(name, ctypes.c_uint32) for name in ("purgeable", "speculative")]
        + [
            (name, ctypes.c_uint64)
            for name in (
                "decompressions",
                "compressions",
                "swapins",
                "swapouts",
            )
        ]
        + [
            (name, ctypes.c_uint32)
            for name in (
                "compressor_pages",
                "throttled",
                "external",
                "internal",
            )
        ]
        + [("uncompressed_pages", ctypes.c_uint64)]
    )


@dataclass(frozen=True)
class ProcessCounters:
    start: int
    footprint: int
    read: int
    write: int
    pageins: int


@dataclass(frozen=True)
class VMCounters:
    page_size: int
    compressed_bytes: int
    pageins: int
    pageouts: int
    swapins: int
    swapouts: int
    compressions: int
    decompressions: int


class DarwinMetrics:
    def __init__(self) -> None:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        self._usage = libproc.proc_pid_rusage
        self._usage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        self._usage.restype = ctypes.c_int
        self._children = libproc.proc_listchildpids
        self._children.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        self._children.restype = ctypes.c_int
        self._child_cache: dict[int, tuple[list[int], bool]] = {}
        self._system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        self._system.mach_host_self.argtypes = []
        self._system.mach_host_self.restype = ctypes.c_uint32
        self._system.host_statistics64.argtypes = [
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        self._system.host_statistics64.restype = ctypes.c_int
        self._system.host_page_size.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self._system.host_page_size.restype = ctypes.c_int
        self._system.mach_port_deallocate.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self._system.mach_port_deallocate.restype = ctypes.c_int

    def process(self, pid: int) -> ProcessCounters:
        value = _RUsageV2()
        ctypes.set_errno(0)
        if self._usage(pid, 2, ctypes.byref(value)) != 0:
            raise OSError(ctypes.get_errno(), "proc_pid_rusage 无法读取进程用量")
        return ProcessCounters(
            value.start, value.footprint, value.read, value.write, value.pageins
        )

    def descendants(self, pid: int, limit: int) -> tuple[list[int], bool]:
        members = [pid]
        seen = {pid}
        cursor = 0
        truncated = False
        while cursor < len(members):
            parent = members[cursor]
            cursor += 1
            if parent not in self._child_cache:
                buffer = (ctypes.c_int * (limit + 1))()
                ctypes.set_errno(0)
                count = self._children(parent, buffer, ctypes.sizeof(buffer))
                if count < 0:
                    raise OSError(ctypes.get_errno(), "无法读取进程后代")
                self._child_cache[parent] = (
                    list(buffer[: min(count, limit)]),
                    count > limit,
                )
            children, partial = self._child_cache[parent]
            truncated |= partial
            for child in children:
                if child in seen:
                    continue
                if len(members) >= limit:
                    return members, True
                seen.add(child)
                members.append(child)
        return members, truncated

    def virtual_memory(self) -> VMCounters:
        host = self._system.mach_host_self()
        if not host:
            raise OSError("无法取得 Mach host port")
        try:
            value = _VMStatistics64()
            count = ctypes.c_uint32(ctypes.sizeof(value) // ctypes.sizeof(ctypes.c_int))
            result = self._system.host_statistics64(
                host, 4, ctypes.byref(value), ctypes.byref(count)
            )
            if result != 0 or count.value < ctypes.sizeof(value) // 4:
                raise OSError(f"host_statistics64 不可用（{result}）")
            page_size = ctypes.c_size_t()
            if (
                self._system.host_page_size(host, ctypes.byref(page_size)) != 0
                or not page_size.value
            ):
                raise OSError("无法读取内核页面大小")
            return VMCounters(
                page_size.value,
                value.compressor_pages * page_size.value,
                value.pageins,
                value.pageouts,
                value.swapins,
                value.swapouts,
                value.compressions,
                value.decompressions,
            )
        finally:
            task = ctypes.c_uint32.in_dll(self._system, "mach_task_self_").value
            self._system.mach_port_deallocate(task, host)

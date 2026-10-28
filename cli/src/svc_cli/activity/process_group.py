"""macOS group observation while the owner retains its unreaped child PID."""

from __future__ import annotations

import ctypes
import sys

import psutil  # type: ignore[import-untyped]

from ..errors import SvcError


class ProcessGroup:
    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise SvcError(
                "managed-platform-unsupported", "受管临时执行目前支持 macOS。"
            )
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        self._list = library.proc_listpgrppids
        self._list.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        self._list.restype = ctypes.c_int

    def members(self, leader: int) -> list[int]:
        # libproc returns a PID count, not a byte count. Keep room for fork races.
        for capacity in (512, 2048, 8192, 32768):
            buffer = (ctypes.c_int * capacity)()
            ctypes.set_errno(0)
            count = self._list(leader, buffer, ctypes.sizeof(buffer))
            if count <= 0:
                raise SvcError("managed-group-unknown", "无法确认受管进程组的成员。")
            if count < capacity:
                break
        else:
            raise SvcError(
                "managed-group-too-large", "受管进程组过大，无法确认完整成员。"
            )
        return list(buffer[:count])

    def sample_members(self, leader: int, limit: int) -> tuple[list[int], bool]:
        # Accounting may truncate; completion proof still requires members().
        # Never expand a busy group into thousands of process objects here.
        buffer = (ctypes.c_int * (limit + 1))()
        count = self._list(leader, buffer, ctypes.sizeof(buffer))
        if count <= 0:
            raise SvcError("managed-group-unknown", "无法采样受管进程组的成员。")
        return list(buffer[: min(count, limit)]), count > limit

    def complete(self, leader: int) -> bool:
        # Check the zombie first: a live leader could fork after an earlier
        # snapshot. Once zombie it cannot add new members to the group.
        try:
            if psutil.Process(leader).status() != psutil.STATUS_ZOMBIE:
                return False
        except psutil.Error as error:
            raise SvcError(
                "managed-group-unknown", "无法读取受管主进程状态。"
            ) from error
        return self.members(leader) == [leader]

from __future__ import annotations

import asyncio
import unittest

from github_agent_bridge.app_server import (
    AppServerExited,
    AppServerProtocolError,
    AppServerRemoteError,
)
from github_agent_bridge.runtime import (
    ProviderConnectionSupervisor,
    _provider_error_requires_operator,
    _provider_operator_status,
    _provider_retry_delay,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FakeProvider:
    def __init__(self, thread_address: str) -> None:
        self.thread_address = thread_address
        self.closed = False
        self.termination = asyncio.get_running_loop().create_future()

    async def wait_terminated(self):
        return await asyncio.shield(self.termination)

    async def close(self) -> None:
        self.closed = True


class RuntimeProviderTests(unittest.TestCase):
    def test_reconnect_backoff_is_continuous_and_capped(self) -> None:
        self.assertEqual(
            [_provider_retry_delay(value) for value in range(8)],
            [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0],
        )
        with self.assertRaises(ValueError):
            _provider_retry_delay(-1)

    def test_provider_failures_have_bounded_operator_classification(self) -> None:
        self.assertFalse(
            _provider_error_requires_operator(AppServerExited("stdout EOF"))
        )
        self.assertTrue(
            _provider_error_requires_operator(
                AppServerProtocolError("unexpected schema")
            )
        )
        unauthorized = AppServerRemoteError(
            code=-32000,
            message="request failed",
            data={"error": {"codexErrorInfo": "unauthorized"}},
        )
        self.assertTrue(_provider_error_requires_operator(unauthorized))
        self.assertEqual(
            _provider_operator_status(unauthorized),
            "authentication-required",
        )

    def test_supervisor_observes_idle_exit_and_resets_connection_age(self) -> None:
        async def scenario() -> None:
            clock = FakeClock()
            first = FakeProvider("thread-1")
            supervisor = ProviderConnectionSupervisor(
                first,  # type: ignore[arg-type]
                clock=clock,
            )
            clock.now = 140.0
            self.assertEqual(supervisor.connected_seconds(), 40.0)
            failure = AppServerExited("stdout EOF")
            first.termination.set_result(failure)
            self.assertIs(
                await supervisor.next_transport_failure(timeout=0.1), failure
            )

            mismatched = FakeProvider("thread-2")
            with self.assertRaises(AppServerProtocolError):
                await supervisor.replace(mismatched)  # type: ignore[arg-type]
            self.assertTrue(mismatched.closed)
            self.assertEqual(supervisor.thread_address, "thread-1")

            replacement = FakeProvider("thread-1")
            await supervisor.replace(replacement)  # type: ignore[arg-type]
            self.assertTrue(first.closed)
            self.assertEqual(supervisor.thread_address, "thread-1")
            self.assertEqual(supervisor.connected_seconds(), 0.0)
            await supervisor.close()
            self.assertTrue(replacement.closed)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()

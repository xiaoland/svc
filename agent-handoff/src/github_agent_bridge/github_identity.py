"""Mechanical normalization for GitHub actor identities."""

from __future__ import annotations

from collections.abc import Collection


_BOT_SUFFIX = "[bot]"


def canonical_github_login(login: str) -> str:
    """Return one comparison key for REST/webhook and GraphQL bot logins.

    GitHub webhook and REST payloads expose GitHub App actors as
    ``app-slug[bot]`` while GraphQL currently exposes the same actor as
    ``app-slug``. The suffix is presentation metadata, not a distinct actor.
    """

    normalized = login.casefold()
    if normalized.endswith(_BOT_SUFFIX):
        return normalized[: -len(_BOT_SUFFIX)]
    return normalized


def is_self_login(login: str | None, self_logins: Collection[str]) -> bool:
    if login is None:
        return False
    candidate = canonical_github_login(login)
    return any(
        candidate == canonical_github_login(self_login)
        for self_login in self_logins
    )

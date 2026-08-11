from __future__ import annotations

import unittest

from github_agent_bridge.github_identity import (
    canonical_github_login,
    is_self_login,
)


class GitHubIdentityTests(unittest.TestCase):
    def test_bot_presentation_suffix_is_not_part_of_actor_identity(self) -> None:
        self.assertEqual(canonical_github_login("Wrapper-Bot[bot]"), "wrapper-bot")
        self.assertTrue(
            is_self_login("wrapper-bot[bot]", frozenset({"WRAPPER-BOT"}))
        )
        self.assertTrue(
            is_self_login("wrapper-bot", frozenset({"WRAPPER-BOT[bot]"}))
        )

    def test_normalization_does_not_match_a_different_login(self) -> None:
        self.assertFalse(
            is_self_login("wrapper-bot-helper", frozenset({"wrapper-bot[bot]"}))
        )
        self.assertFalse(is_self_login(None, frozenset({"wrapper-bot"})))


if __name__ == "__main__":
    unittest.main()

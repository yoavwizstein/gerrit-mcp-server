# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest.mock import patch, AsyncMock
import asyncio
import json

from gerrit_mcp_server import main


class TestListUnresolvedComments(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_only_unresolved_threads_are_returned(self, mock_run_curl):
        async def run_test():
            # Arrange: one resolved thread and one unresolved thread on different files.
            change_id = "11223"
            mock_response = {
                "src/main.py": [
                    {
                        "id": "abc123",
                        "line": 10,
                        "author": {"name": "user1@example.com"},
                        "message": "Please rename this variable.",
                        "unresolved": True,
                        "updated": "2025-07-15T10:00:00Z",
                    },
                    {
                        "id": "def456",
                        "in_reply_to": "abc123",
                        "line": 10,
                        "author": {"name": "user2@example.com"},
                        "message": "Done.",
                        "unresolved": False,
                        "updated": "2025-07-15T10:05:00Z",
                    },
                ],
                "README.md": [
                    {
                        "id": "ghi789",
                        "line": 5,
                        "author": {"name": "user1@example.com"},
                        "message": "Still needs work.",
                        "unresolved": True,
                        "updated": "2025-07-15T10:10:00Z",
                    }
                ],
            }
            mock_run_curl.return_value = json.dumps(mock_response)

            # Act
            result = await main.list_unresolved_comments(
                change_id, gerrit_base_url="https://my-gerrit.com"
            )

            # Assert
            text = result[0]["text"]
            self.assertIn("Unresolved comments for CL 11223", text)
            # The resolved thread on src/main.py should be skipped entirely.
            self.assertNotIn("File: src/main.py", text)
            self.assertNotIn("Please rename this variable.", text)
            self.assertNotIn("Done.", text)
            # The unresolved thread on README.md should be present.
            self.assertIn("File: README.md", text)
            self.assertIn(
                "L5 [id: ghi789]: [user1@example.com] (2025-07-15T10:10:00Z) - UNRESOLVED",
                text,
            )
            self.assertIn("Still needs work.", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_thread_resolution_uses_latest_comment(self, mock_run_curl):
        async def run_test():
            # Arrange: the original comment is unresolved but the latest reply
            # marks it resolved. The thread should NOT show up.
            change_id = "11223"
            mock_response = {
                "src/main.py": [
                    {
                        "id": "abc123",
                        "line": 10,
                        "author": {"name": "user1@example.com"},
                        "message": "Fix this.",
                        "unresolved": True,
                        "updated": "2025-07-15T10:00:00Z",
                    },
                    {
                        "id": "def456",
                        "in_reply_to": "abc123",
                        "line": 10,
                        "author": {"name": "user2@example.com"},
                        "message": "Fixed.",
                        "unresolved": False,
                        "updated": "2025-07-15T10:05:00Z",
                    },
                ]
            }
            mock_run_curl.return_value = json.dumps(mock_response)

            # Act
            result = await main.list_unresolved_comments(
                change_id, gerrit_base_url="https://my-gerrit.com"
            )

            # Assert
            self.assertIn(
                f"No unresolved comments for CL {change_id}.", result[0]["text"]
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_unresolved_thread_includes_full_context(self, mock_run_curl):
        async def run_test():
            # Arrange: original is resolved, but a follow-up reopens the thread.
            change_id = "11223"
            mock_response = {
                "src/main.py": [
                    {
                        "id": "abc123",
                        "line": 10,
                        "author": {"name": "reviewer@example.com"},
                        "message": "Why this magic number?",
                        "unresolved": True,
                        "updated": "2025-07-15T10:00:00Z",
                    },
                    {
                        "id": "def456",
                        "in_reply_to": "abc123",
                        "line": 10,
                        "author": {"name": "author@example.com"},
                        "message": "Added a comment explaining it.",
                        "unresolved": False,
                        "updated": "2025-07-15T10:05:00Z",
                    },
                    {
                        "id": "ghi789",
                        "in_reply_to": "def456",
                        "line": 10,
                        "author": {"name": "reviewer@example.com"},
                        "message": "Comment is misleading, please rephrase.",
                        "unresolved": True,
                        "updated": "2025-07-15T10:10:00Z",
                    },
                ]
            }
            mock_run_curl.return_value = json.dumps(mock_response)

            # Act
            result = await main.list_unresolved_comments(
                change_id, gerrit_base_url="https://my-gerrit.com"
            )

            # Assert: all three messages of the reopened thread are surfaced
            # so the agent can read the full conversation.
            text = result[0]["text"]
            self.assertIn("Why this magic number?", text)
            self.assertIn("Added a comment explaining it.", text)
            self.assertIn("Comment is misleading, please rephrase.", text)
            # The resolved reply is still tagged RESOLVED to preserve fidelity.
            self.assertIn(
                "L10 [id: def456] (in_reply_to: abc123): [author@example.com] (2025-07-15T10:05:00Z) - RESOLVED",
                text,
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_no_comments_at_all(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = json.dumps({})

            result = await main.list_unresolved_comments(
                "11223", gerrit_base_url="https://my-gerrit.com"
            )

            self.assertEqual(
                result[0]["text"], "No unresolved comments for CL 11223."
            )

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_invalid_json_response(self, mock_run_curl):
        async def run_test():
            mock_run_curl.return_value = "not json at all"

            result = await main.list_unresolved_comments(
                "11223", gerrit_base_url="https://my-gerrit.com"
            )

            self.assertIn("Failed to parse JSON", result[0]["text"])

        asyncio.run(run_test())


class TestThreadHelpers(unittest.TestCase):
    def test_group_comments_into_threads_links_replies_to_root(self):
        comments = [
            {"id": "root1", "updated": "2025-07-15T10:00:00Z"},
            {
                "id": "reply1",
                "in_reply_to": "root1",
                "updated": "2025-07-15T10:05:00Z",
            },
            {
                "id": "reply2",
                "in_reply_to": "reply1",
                "updated": "2025-07-15T10:10:00Z",
            },
            {"id": "root2", "updated": "2025-07-15T11:00:00Z"},
        ]

        threads = main._group_comments_into_threads(comments)

        thread_ids = sorted([[c["id"] for c in t] for t in threads])
        self.assertEqual(thread_ids, [["root1", "reply1", "reply2"], ["root2"]])

    def test_group_comments_handles_dangling_in_reply_to(self):
        # Reply points to an id we never received -> treated as its own root.
        comments = [
            {
                "id": "orphan",
                "in_reply_to": "missing_parent",
                "updated": "2025-07-15T10:00:00Z",
            }
        ]

        threads = main._group_comments_into_threads(comments)

        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0][0]["id"], "orphan")

    def test_is_thread_unresolved_uses_latest_by_timestamp(self):
        # Ordering matters: the helper should rely on already-sorted threads.
        thread = [
            {"updated": "2025-07-15T10:00:00Z", "unresolved": True},
            {"updated": "2025-07-15T10:05:00Z", "unresolved": False},
        ]
        self.assertFalse(main._is_thread_unresolved(thread))

        thread_reopened = [
            {"updated": "2025-07-15T10:00:00Z", "unresolved": False},
            {"updated": "2025-07-15T10:05:00Z", "unresolved": True},
        ]
        self.assertTrue(main._is_thread_unresolved(thread_reopened))


if __name__ == "__main__":
    unittest.main()

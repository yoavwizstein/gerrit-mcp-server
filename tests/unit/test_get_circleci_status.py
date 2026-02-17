import unittest
from unittest.mock import patch, AsyncMock
import asyncio
import json

from gerrit_mcp_server import main


SAMPLE_CHANGE_DETAIL = {
    "_number": 11286,
    "change_id": "Ie9b66b1368ac166ae4d04d0dfbcaebb7f36af464",
    "project": "sensor",
    "branch": "master",
    "subject": "dns_cache: populate cache from DnsResponse events",
    "status": "NEW",
}

SAMPLE_WORKFLOWS = [
    {
        "project_slug": "gh/wiz-sec/sensor",
        "pipeline_number": 36754,
        "pipeline_id": "9e6c3db8-0166-4a9e-a0b7-8ad3ee9bfbab",
        "name": "build-windows-app",
        "id": "d1123c75-c453-4748-b815-febf00cf56bb",
        "status": "failed",
        "created_at": "2026-02-12T22:09:51Z",
        "stopped_at": "2026-02-12T22:21:39Z",
        "jobs": [
            {
                "name": "cargo fmt check",
                "job_number": 737631,
                "id": "351d65d1-e639-4bc9-8926-9f0bb700befa",
                "status": "success",
                "started_at": "2026-02-12T22:09:53Z",
                "stopped_at": "2026-02-12T22:10:21Z",
            },
            {
                "name": "build-windows-amd64",
                "job_number": 737632,
                "id": "375864f5-a3db-4779-b085-f5e25f73c4cf",
                "status": "failed",
                "started_at": "2026-02-12T22:09:58Z",
                "stopped_at": "2026-02-12T22:21:39Z",
            },
            {
                "name": "sign-windows-artifacts",
                "job_number": 737633,
                "id": "d11158cd-a207-4b08-8046-9af107c3cb31",
                "status": "blocked",
                "started_at": None,
            },
        ],
    },
    {
        "project_slug": "gh/wiz-sec/sensor",
        "pipeline_number": 36754,
        "pipeline_id": "9e6c3db8-0166-4a9e-a0b7-8ad3ee9bfbab",
        "name": "build-linux-ebpf",
        "id": "2944ecf3-26da-4caa-b4fc-acbf9cb527e6",
        "status": "success",
        "created_at": "2026-02-12T22:09:50Z",
        "stopped_at": "2026-02-12T22:32:40Z",
        "jobs": [
            {
                "name": "cargo fmt check",
                "job_number": 737615,
                "id": "383bdaa9-5c6e-497a-a44b-9591f8cca168",
                "status": "success",
                "started_at": "2026-02-12T22:09:52Z",
                "stopped_at": "2026-02-12T22:10:19Z",
            },
        ],
    },
]


class TestGetCircleciStatus(unittest.TestCase):
    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_mixed_workflow_statuses(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [
                json.dumps(SAMPLE_CHANGE_DETAIL),
                json.dumps(SAMPLE_WORKFLOWS),
            ]
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_circleci_status(
                "11286", gerrit_base_url=gerrit_base_url
            )

            text = result[0]["text"]
            self.assertIn("CircleCI Status for CL 11286", text)
            self.assertIn("[FAILED] build-windows-app", text)
            self.assertIn("[SUCCESS] build-linux-ebpf", text)
            self.assertIn("[success] cargo fmt check", text)
            self.assertIn("[failed] build-windows-amd64", text)
            self.assertIn("[blocked] sign-windows-artifacts", text)
            # Failed jobs should have URLs
            self.assertIn("URL: https://app.circleci.com/pipelines/gh/wiz-sec/sensor/36754/workflows/", text)
            # Summary
            self.assertIn("1 failed", text)
            self.assertIn("1 success", text)
            self.assertIn("2 workflows", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_job_duration_formatting(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [
                json.dumps(SAMPLE_CHANGE_DETAIL),
                json.dumps(SAMPLE_WORKFLOWS),
            ]
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_circleci_status(
                "11286", gerrit_base_url=gerrit_base_url
            )

            text = result[0]["text"]
            # cargo fmt check: 22:09:53 -> 22:10:21 = 28s
            self.assertIn("(28s)", text)
            # build-windows-amd64: 22:09:58 -> 22:21:39 = 11m41s
            self.assertIn("(11m41s)", text)

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_empty_workflows(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [
                json.dumps(SAMPLE_CHANGE_DETAIL),
                json.dumps([]),
            ]
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_circleci_status(
                "11286", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("No CircleCI workflows found for CL 11286", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_plugin_not_installed(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = [
                json.dumps(SAMPLE_CHANGE_DETAIL),
                Exception("curl command failed with exit code 1.\nSTDERR:\n404 Not Found"),
            ]
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_circleci_status(
                "11286", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("No CircleCI status endpoint found", result[0]["text"])
            self.assertIn("CircleCI plugin may not be installed", result[0]["text"])

        asyncio.run(run_test())

    @patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock)
    def test_change_detail_fetch_failure(self, mock_run_curl):
        async def run_test():
            mock_run_curl.side_effect = Exception(
                "curl command failed with exit code 1.\nSTDERR:\nConnection refused"
            )
            gerrit_base_url = "https://my-gerrit.com"

            result = await main.get_circleci_status(
                "99999", gerrit_base_url=gerrit_base_url
            )

            self.assertIn("Failed to fetch change details for CL 99999", result[0]["text"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()

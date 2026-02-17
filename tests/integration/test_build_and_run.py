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
import tempfile
import shutil
import subprocess
import os
import sys
import time
import json


class TestBuildAndRun(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory for the test."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

        # Files and directories to copy to the temporary directory
        self.files_to_copy = [
            "build.py",
            "pyproject.toml",
            "server.py",
            "run_tests.py",
            "uv-requirements.txt",
        ]
        self.dirs_to_copy = ["gerrit_mcp_server"]

        for file_name in self.files_to_copy:
            shutil.copy(os.path.join(self.project_root, file_name), self.test_dir.name)

        for dir_name in self.dirs_to_copy:
            shutil.copytree(
                os.path.join(self.project_root, dir_name),
                os.path.join(self.test_dir.name, dir_name),
            )

        # Create a dummy gerrit_config.json for the test environment
        dummy_config = {
            "default_gerrit_base_url": "https://test-gerrit.com/",
            "gerrit_hosts": [
                {
                    "name": "Test Gerrit",
                    "external_url": "https://test-gerrit.com/",
                    "authentication": {"type": "gob_curl"},
                }
            ],
        }
        gerrit_config_path = os.path.join(
            self.test_dir.name, "gerrit_mcp_server", "gerrit_config.json"
        )
        with open(gerrit_config_path, "w") as f:
            json.dump(dummy_config, f)

        # Modify server.py to use a different port for testing
        server_script_path = os.path.join(self.test_dir.name, "server.py")
        with open(server_script_path, "r") as f:
            server_script_content = f.read()

        # Use a high, static port for testing to avoid conflicts
        server_script_content = server_script_content.replace(
            'PORT = "6322"', 'PORT = "8999"'
        )

        with open(server_script_path, "w") as f:
            f.write(server_script_content)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir.cleanup()

    def test_build_and_run_server(self):
        """
        Tests the full build and server run lifecycle using the Python scripts.
        """
        # 1. Run the build script
        build_script_path = os.path.join(self.test_dir.name, "build.py")
        build_process = subprocess.run(
            [sys.executable, build_script_path],
            cwd=self.test_dir.name,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            build_process.returncode,
            0,
            f"Build script failed with output:\n{build_process.stdout}\n{build_process.stderr}",
        )
        self.assertTrue(os.path.exists(os.path.join(self.test_dir.name, ".venv")))
        self.assertTrue(
            os.path.exists(os.path.join(self.test_dir.name, "requirements.txt"))
        )

        # 2. Run the server using server.py
        server_script_path = os.path.join(self.test_dir.name, "server.py")

        server_env = os.environ.copy()
        server_env["PYTHONPATH"] = self.test_dir.name

        # Start the server with platform-aware process creation
        popen_kwargs = {}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["preexec_fn"] = os.setsid

        start_process = subprocess.Popen(
            [sys.executable, server_script_path, "start"],
            cwd=self.test_dir.name,
            **popen_kwargs,
        )
        start_process.wait()

        if start_process.returncode != 0:
            log_path = os.path.join(self.test_dir.name, "server.log")
            log_content = ""
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    log_content = f.read()
            self.fail(
                f"server.py start failed with exit code {start_process.returncode}.\n"
                f"STDOUT:\n{start_process.stdout}\n"
                f"STDERR:\n{start_process.stderr}\n"
                f"SERVER LOG (server.log):\n{log_content}"
            )

        # Give the server a moment to start up
        time.sleep(2)

        # 3. Verify the server is running with server.py status
        status_process = subprocess.run(
            [sys.executable, server_script_path, "status"],
            cwd=self.test_dir.name,
            capture_output=True,
            text=True,
            env=server_env,
        )
        self.assertEqual(
            status_process.returncode,
            0,
            f"server.py status failed:\n{status_process.stderr}",
        )
        self.assertIn("Server is RUNNING", status_process.stdout)

        # 4. Stop the server
        stop_process = subprocess.run(
            [sys.executable, server_script_path, "stop"],
            cwd=self.test_dir.name,
            capture_output=True,
            text=True,
            env=server_env,
        )
        self.assertEqual(
            stop_process.returncode, 0, f"server.py stop failed:\n{stop_process.stderr}"
        )
        self.assertIn("Server stopped", stop_process.stdout)

        # 5. Verify the server is stopped
        status_after_stop_process = subprocess.run(
            [sys.executable, server_script_path, "status"],
            cwd=self.test_dir.name,
            capture_output=True,
            text=True,
            env=server_env,
        )
        self.assertIn("Server is STOPPED", status_after_stop_process.stdout)

    def test_run_tests_fails_on_broken_build(self):
        """
        Tests that run_tests.py fails gracefully when the build cannot complete.
        """
        # Remove uv-requirements.txt so the build will fail at the uv install step
        uv_req_path = os.path.join(self.test_dir.name, "uv-requirements.txt")
        if os.path.exists(uv_req_path):
            os.remove(uv_req_path)

        test_script_path = os.path.join(self.test_dir.name, "run_tests.py")
        test_process = subprocess.run(
            [sys.executable, test_script_path],
            cwd=self.test_dir.name,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(
            test_process.returncode,
            0,
            "run_tests.py should fail when build prerequisites are missing",
        )


if __name__ == "__main__":
    unittest.main()
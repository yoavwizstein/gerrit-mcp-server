"""Cross-platform test runner for the Gerrit MCP server.

Bootstraps config from sample if needed, ensures the venv is built,
and runs the pytest suite.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

VENV_DIR = ".venv"
CONFIG_FILE = Path("gerrit_mcp_server") / "gerrit_config.json"
SAMPLE_CONFIG_FILE = Path("gerrit_mcp_server") / "gerrit_config.sample.json"

# --- Color helpers ---
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def venv_executable(name: str) -> Path:
    """Return path to an executable inside the venv, platform-aware."""
    if sys.platform == "win32":
        return Path(VENV_DIR) / "Scripts" / f"{name}.exe"
    return Path(VENV_DIR) / "bin" / name


def run_tests():
    # Config bootstrap -- create from sample if it doesn't exist
    if not CONFIG_FILE.exists():
        print(f"{YELLOW}Configuration file not found. Creating from sample...{NC}")
        try:
            shutil.copy(SAMPLE_CONFIG_FILE, CONFIG_FILE)
        except OSError:
            print(f"{RED}Failed to create configuration file. Aborting tests.{NC}")
            sys.exit(1)

    # Ensure the virtual environment exists
    if not Path(VENV_DIR).exists():
        print(f"{YELLOW}Virtual environment not found. Running the build script...{NC}")
        result = subprocess.run([sys.executable, "build.py"])
        if result.returncode != 0:
            print(f"{RED}Build script failed. Aborting tests.{NC}")
            sys.exit(1)

    # Run tests using pytest via the venv python
    project_root = str(Path.cwd())
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root
    env["GERRIT_CONFIG_PATH"] = str(Path(project_root) / "tests" / "test_config.json")

    python = str(venv_executable("python"))

    print(f"\n{YELLOW}Running tests with pytest...{NC}")
    result = subprocess.run([python, "-m", "pytest"], env=env)
    if result.returncode != 0:
        print(f"{RED}Tests failed.{NC}")
        sys.exit(1)

    print(f"\n{GREEN}All tests passed successfully.{NC}")


if __name__ == "__main__":
    run_tests()

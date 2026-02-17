
"""Cross-platform build script for the Gerrit MCP server.

Sets up the Python virtual environment, installs dependencies via uv,
and builds the gerrit_mcp_server package.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

VENV_DIR = ".venv"
REQUIREMENTS_FILE = "requirements.txt"

# --- Color helpers (ANSI codes work on modern Windows terminals too) ---
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def venv_executable(name: str) -> Path:
    """Return path to an executable inside the venv, platform-aware."""
    if sys.platform == "win32":
        return Path(VENV_DIR) / "Scripts" / f"{name}.exe"
    return Path(VENV_DIR) / "bin" / name


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess, raising on failure."""
    return subprocess.run(args, check=True, **kwargs)


def build():
    print(f"\n{YELLOW}Setting up the Python environment for the Gerrit MCP server...{NC}")

    # Create a build directory to indicate the server is "installed"
    Path("build").mkdir(exist_ok=True)

    # Create a virtual environment
    print(f"Creating virtual environment in {VENV_DIR}...")
    try:
        run([sys.executable, "-m", "venv", VENV_DIR])
    except subprocess.CalledProcessError:
        print(f"{RED}Failed to create virtual environment.{NC}")
        sys.exit(1)

    pip = str(venv_executable("pip"))
    uv = str(venv_executable("uv"))

    # Install uv into the virtual environment
    print("Installing uv...")
    try:
        run([pip, "install", "-r", "uv-requirements.txt", "--require-hashes"])
    except subprocess.CalledProcessError:
        print(f"{RED}Failed to install uv.{NC}")
        sys.exit(1)

    # Use uv to compile dependencies into a requirements.txt file with hashes
    print("Compiling dependencies and generating hashes...")
    try:
        run([
            uv, "pip", "compile", "pyproject.toml",
            "--generate-hashes",
            "--output-file", REQUIREMENTS_FILE,
            "--extra", "dev",
            "--extra-index-url", "https://pypi.org/simple",
        ])
    except subprocess.CalledProcessError:
        print(f"\n{RED}Failed to compile dependencies.{NC}")
        sys.exit(1)

    # Use uv to install dependencies from the requirements.txt file
    print(f"Installing dependencies from {REQUIREMENTS_FILE}...")
    try:
        run([uv, "pip", "sync", REQUIREMENTS_FILE])
    except subprocess.CalledProcessError:
        print(f"\n{RED}Failed to set up the Python environment.{NC}")
        sys.exit(1)

    # Build the gerrit_mcp_server package
    print("Building and installing the gerrit_mcp_server package...")
    try:
        run([uv, "build"])
    except subprocess.CalledProcessError:
        print(f"\n{RED}Failed to build the gerrit_mcp_server package.{NC}")
        sys.exit(1)

    # Find the wheel, compute its hash, and install with hash verification
    wheel_file = next(Path("dist").glob("*.whl"))
    wheel_hash = hashlib.sha256(wheel_file.read_bytes()).hexdigest()

    local_req = Path("local-requirements.txt")
    local_req.write_text(f"{wheel_file} --hash=sha256:{wheel_hash}\n")

    try:
        run([uv, "pip", "install", "-r", str(local_req), "--no-deps", "--require-hashes"])
    except subprocess.CalledProcessError:
        print(f"\n{RED}Failed to install the gerrit_mcp_server package.{NC}")
        local_req.unlink(missing_ok=True)
        sys.exit(1)

    local_req.unlink(missing_ok=True)

    print(f"\n{GREEN}Successfully set up the Gerrit MCP server environment.{NC}")


if __name__ == "__main__":
    build()

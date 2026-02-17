"""Cross-platform server management script for the Gerrit MCP server.

Manages the server lifecycle: starting, stopping, and monitoring
the uvicorn process.

Usage: python server.py {start|stop|restart|status|logs}
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

VENV_DIR = ".venv"
HOST = "localhost"
PORT = "6322"

SCRIPT_DIR = Path(__file__).resolve().parent
PID_FILE = SCRIPT_DIR / "server.pid"
LOG_FILE = SCRIPT_DIR / "server.log"


def venv_executable(name: str) -> Path:
    """Return path to an executable inside the venv, platform-aware."""
    if sys.platform == "win32":
        return Path(VENV_DIR) / "Scripts" / f"{name}.exe"
    return Path(VENV_DIR) / "bin" / name


def is_process_running(pid: int) -> bool:
    """Check whether a process with the given PID is alive."""
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True,
        )
        return str(pid) in result.stdout
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def read_pid() -> int | None:
    """Read the PID from the PID file, or None if absent/stale."""
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def is_running() -> bool:
    pid = read_pid()
    return pid is not None and is_process_running(pid)


def start_server():
    if is_running():
        print(f"Server is already running with PID {read_pid()}.")
        sys.exit(1)

    print("Starting server...")

    uvicorn = str(venv_executable("uvicorn"))
    cmd = [uvicorn, "gerrit_mcp_server.main:app", "--host", HOST, "--port", PORT]

    log_handle = open(LOG_FILE, "w")

    if sys.platform == "win32":
        proc = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        proc = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )

    PID_FILE.write_text(str(proc.pid))
    # Give it a moment to ensure it started correctly.
    time.sleep(1)

    if is_running():
        print(f"Server started successfully with PID {read_pid()}.")
        print(f"Logs are being written to {LOG_FILE}.")
    else:
        print(f"Error: Server failed to start. Check '{LOG_FILE}' for details.")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)


def _terminate_process(pid: int):
    """Terminate a process (and its children) in a platform-aware way."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
        )
    else:
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            pass


def _force_kill_process(pid: int):
    """Force-kill a process in a platform-aware way."""
    if sys.platform == "win32":
        # taskkill /F already force-kills; call again just in case
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
        )
    else:
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            pass


def stop_server():
    if not is_running():
        print("Server is not running.")
        if PID_FILE.exists():
            print(f"Cleaning up stale PID file: {PID_FILE}")
            PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    pid = read_pid()
    print(f"Stopping server with PID {pid}...")
    _terminate_process(pid)

    # Wait for the process to actually terminate
    for _ in range(5):
        if not is_process_running(pid):
            print("Server stopped successfully.")
            PID_FILE.unlink(missing_ok=True)
            sys.exit(0)
        time.sleep(1)

    print("Warning: Server did not stop gracefully. Forcing shutdown.")
    _force_kill_process(pid)
    PID_FILE.unlink(missing_ok=True)
    print("Server shutdown forced.")


def check_status():
    if is_running():
        print(f"Server is RUNNING with PID {read_pid()}.")
    else:
        print("Server is STOPPED.")


def tail_logs():
    if not LOG_FILE.exists():
        print(f"Log file not found: {LOG_FILE}")
        print("Has the server been started at least once?")
        sys.exit(1)

    print(f"Tailing logs from {LOG_FILE}... (Press Ctrl+C to stop)")
    try:
        with open(LOG_FILE, "r") as f:
            # Seek to end
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.3)
    except KeyboardInterrupt:
        pass


def restart_server():
    print("Restarting server...")
    if is_running():
        stop_server()
    start_server()


def main():
    commands = {
        "start": start_server,
        "stop": stop_server,
        "restart": restart_server,
        "status": check_status,
        "logs": tail_logs,
    }

    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print(f"Usage: {sys.argv[0]} {{{'|'.join(commands)}}}")
        sys.exit(1)

    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()

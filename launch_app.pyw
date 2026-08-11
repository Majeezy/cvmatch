"""
Job Application Assistant — silent launcher (runs with pythonw, no console window).
Starts the Flask server then opens the browser.
"""
import subprocess
import sys
import time
import webbrowser
import socket
import os
from pathlib import Path

ROOT = Path(__file__).parent
PYTHON = sys.executable.replace("pythonw.exe", "python.exe")  # server needs stdout
PORT = 8080


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def main():
    if port_in_use(PORT):
        # Server already running — just open the browser
        webbrowser.open(f"http://localhost:{PORT}")
        return

    # Start the Flask server as a detached background process
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    subprocess.Popen(
        [PYTHON, str(ROOT / "server.py")],
        cwd=str(ROOT),
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )

    # Wait for the server to be ready (up to 10 seconds)
    for _ in range(20):
        time.sleep(0.5)
        if port_in_use(PORT):
            break

    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    main()

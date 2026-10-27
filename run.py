"""
Basketball XOX - One-Click Launcher
Runs the FastAPI backend and opens the game directly in your web browser.
"""

import sys
import os
import webbrowser
import threading
import time

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

def launch_server():
    try:
        import uvicorn
    except ImportError:
        print("Uvicorn is required. Installing dependencies...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        import uvicorn

    def open_browser():
        time.sleep(1.2)
        url = "http://localhost:8000"
        print(f"Opening Basketball XOX in browser: {url}")
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    print("==================================================")
    print("BASKETBALL XOX - 2-PLAYER GRID TRIVIA")
    print("Server running at: http://localhost:8000")
    print("Press Ctrl+C to stop.")
    print("==================================================")

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    launch_server()

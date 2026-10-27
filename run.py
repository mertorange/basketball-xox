"""
Basketball XOX - One-Click Launcher
Runs the FastAPI backend and opens the game directly in your web browser.
"""

import sys
import webbrowser
import threading
import time
from pathlib import Path

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
        print(f"\n🏀 Opening Basketball XOX at {url} ...")
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    print("==================================================")
    print("🏀 BASKETBALL XOX - 2-PLAYER GRID TRIVIA 🏀")
    print("Starting server at http://localhost:8000")
    print("Press Ctrl+C to stop.")
    print("==================================================")

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    launch_server()

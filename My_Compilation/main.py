"""
main.py — Project ARJUNA (SIH 26170)
Integrated Mission Control Engine and Production Uvicorn Entrypoint.
Conforms to ECSS-Q-ST-60-02C. Supports both local desktop and Docker orchestration.
"""

import os
import threading
import time
import webbrowser

import uvicorn


def open_browser(host: str, port: int) -> None:
    time.sleep(1.5)
    url = f"http://127.0.0.1:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
    print(f"\n[Project ARJUNA] Opening Mission Control in browser: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    no_browser = os.getenv("NO_BROWSER", "0").lower() in ("1", "true", "yes")

    print("==========================================================================")
    print("  PROJECT ARJUNA (SIH 26170): INTEGRATED MISSION CONTROL ENGINE")
    print("==========================================================================")
    print(f"  Binding Address:           http://{host}:{port}")
    print("  Hardware Physics Engine:   Active (125°C MIL-STD-883)")
    print("  AI/ML Engine (Mod A & B):  Active (Dynamic Outlier & 168h OLS)")
    print("  Time-Series CUSUM Engine:  Active (Thermal Creep Tracking)")
    print(f"  Streaming WebSocket on:    ws://{host}:{port}/ws")
    print("  Standard: ECSS-Q-ST-60-02C Space Product Assurance")
    print("==========================================================================\n")

    # Launch browser automatically in background unless disabled or headless container
    if not no_browser and host not in ("0.0.0.0", "::"):
        threading.Thread(target=open_browser, args=(host, port), daemon=True).start()

    # Run FastAPI server
    uvicorn.run("Backend.server:app", host=host, port=port, log_level="info")

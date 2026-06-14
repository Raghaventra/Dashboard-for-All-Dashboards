"""Convenience launcher. Reads HOST/PORT from env (defaults below).

Run:  python run.py
Or:   uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import os

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)

"""
local_engine — the entrypoint for the engine bundled inside the desktop app.

This is what makes "everything runs on the user's own hardware" literally
true. In the web app the seven server-assisted tools (OCR, full-fidelity
Office conversion, Ghostscript compression, PDF/A, background removal,
chat) are invisible unless someone has stood up a backend. Here the same
FastAPI app runs as a child process of the desktop app, on the user's own
machine, so those tools light up with no server involved anywhere.

Security posture — this is a server running on someone's laptop, so it is
deliberately unreachable from anywhere else:

  * binds 127.0.0.1 only, never 0.0.0.0, so nothing off-machine can reach it
  * binds port 0, letting the OS pick a free port, so it is not sitting on a
    predictable one
  * mints a random 256-bit token per launch and requires it on every request,
    so another *local* process cannot drive it either
  * exits when its parent does

It prints one line on stdout when ready, which the Tauri shell parses:

    DOCKBENCH_READY <port> <token>

Run standalone for debugging:  python3 local_engine.py
"""

import os
import secrets
import sys
import threading

# Mark this as the local, user-owned deployment *before* importing the app:
# apikeys.py reads DOCKBENCH_LOCAL at import time to disable business-tier
# key enforcement. Someone running the engine on their own machine is not a
# customer of ours to be metered.
os.environ["DOCKBENCH_LOCAL"] = "1"
os.environ.setdefault("UPLOAD_SPOOL_DIR", os.path.join(
    os.environ.get("TMPDIR") or "/tmp", "dockbench-spool"))

SESSION_TOKEN = os.environ.get("DOCKBENCH_SESSION_TOKEN") or secrets.token_urlsafe(32)

import uvicorn  # noqa: E402
from fastapi import Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

import main  # noqa: E402

app = main.app

# Paths that must work before a caller can possibly know the token, plus the
# OpenAPI docs, which are useful when debugging a local engine.
_OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"}


@app.middleware("http")
async def require_session_token(request: Request, call_next):
    """Reject anything that does not present this launch's token.

    Without this, any process on the machine — including a web page in a
    browser tab, via a form POST — could drive the engine. Compared with
    secrets.compare_digest so the check is not timing-dependent.
    """
    if request.url.path not in _OPEN_PATHS:
        auth = request.headers.get("authorization") or ""
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if not secrets.compare_digest(token, SESSION_TOKEN):
            return JSONResponse({"detail": "Invalid or missing session token."}, status_code=401)
    return await call_next(request)


def _watch_parent():
    """Exit when the desktop app goes away.

    Tauri kills sidecars on a clean shutdown, but a crash or a SIGKILL would
    otherwise leave an orphaned engine listening on loopback. Reading stdin
    to EOF is the portable way to notice the parent is gone.
    """
    try:
        sys.stdin.read()
    except Exception:
        pass
    os._exit(0)


def main_entry():
    import socket

    # Claim a free port ourselves so it can be printed before uvicorn starts;
    # uvicorn is then handed the bound socket rather than racing for it.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]

    # The Tauri shell blocks on this line. Flush explicitly: stdout is a pipe
    # here, so it is block-buffered and would otherwise deadlock the launch.
    print(f"DOCKBENCH_READY {port} {SESSION_TOKEN}", flush=True)

    threading.Thread(target=_watch_parent, daemon=True).start()

    uvicorn.run(app, fd=sock.fileno(), log_level="warning", access_log=False)


if __name__ == "__main__":
    main_entry()

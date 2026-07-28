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
    os.environ.get("TMPDIR") or "/tmp", "pdflove-spool"))

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


# ---------------------------------------------------------------------
# Local path-based endpoints — the 100 GB path.
#
# Uploading a 100 GB file over HTTP would mean copying it through the
# browser, through a multipart encoder, and onto disk again. These take a
# *path* the OS file picker already gave the desktop app, so the bytes are
# never copied anywhere. Only reachable on the loopback engine, behind the
# session token.
# ---------------------------------------------------------------------
from typing import List, Optional  # noqa: E402

from pydantic import BaseModel  # noqa: E402

import premium_pdf  # noqa: E402
from errors import EngineError  # noqa: E402


class PathJob(BaseModel):
    op: str                                   # merge | split | extract | rotate | npages
    inputs: List[str]                         # absolute source paths
    output: Optional[str] = None              # destination file or directory
    angle: int = 0
    first: int = 1
    last: int = 1
    # Cap pages per output file on a merge. Peak memory tracks the page
    # count, so this is the lever that keeps a very large job inside a
    # device's memory ceiling. None means one output file, whatever it costs.
    max_pages_per_part: Optional[int] = None
    # Or state the ceiling and let the engine pick the part size for you.
    memory_budget_mb: Optional[int] = None


def _engine_error(e: EngineError):
    return JSONResponse({"detail": e.detail}, status_code=e.status)


@app.post("/local/process")
async def local_process(job: PathJob):
    """Run a page operation directly against paths on this machine.

    Peak memory is decoupled from file size — bytes are nearly free — but it
    does scale with the page count, at roughly 17-23 KB per page, because
    the output document holds an entry for every page until the writer
    finishes. A merge of 48,000 pages costs ~810 MB in one file; pass
    max_pages_per_part (or memory_budget_mb) to cap that. The same job
    written in parts of 3,000 pages costs 75 MB and runs faster.
    """
    try:
        if not job.inputs:
            raise EngineError(422, "No input paths given.")

        if job.op == "npages":
            return {"pages": premium_pdf.npages_path(job.inputs[0])}

        if not job.output:
            raise EngineError(422, "An output path is required for this operation.")

        # Fail before starting rather than halfway through, leaving a
        # truncated 60 GB file behind.
        out_dir = job.output if job.op == "split" else os.path.dirname(job.output) or "."
        needed = sum(os.path.getsize(p) for p in job.inputs if os.path.isfile(p))
        if not premium_pdf.free_space_ok(out_dir, needed):
            raise EngineError(
                507,
                f"Not enough free space in {out_dir} — this needs roughly "
                f"{needed / 1e9:.1f} GB plus headroom.",
            )

        if job.op == "merge":
            per_part = job.max_pages_per_part
            if per_part is None and job.memory_budget_mb:
                per_part = premium_pdf.pages_per_part_for(job.memory_budget_mb)
            pages = premium_pdf.merge_paths(job.inputs, job.output,
                                            max_pages_per_part=per_part)
        elif job.op == "split":
            pages = premium_pdf.split_path(job.inputs[0], job.output)
        elif job.op == "extract":
            pages = premium_pdf.extract_path(job.inputs[0], job.output, job.first, job.last)
        elif job.op == "rotate":
            pages = premium_pdf.rotate_path(job.inputs[0], job.output, job.angle)
        else:
            raise EngineError(422, f"Unknown op {job.op!r}. Valid: merge, split, extract, rotate, npages.")

        return {"op": job.op, "output": job.output, "pages": pages}

    except EngineError as e:
        return _engine_error(e)


@app.get("/local/capabilities")
async def local_capabilities():
    """What this machine can actually do — reported to the UI so it can
    show real limits instead of guessing."""
    import shutil as _shutil

    try:
        free = _shutil.disk_usage(os.path.expanduser("~")).free
    except OSError:
        free = None
    return {
        "local": True,
        "streaming": premium_pdf.streaming_available(),
        "pdf_backend": premium_pdf.pdf_backend(),
        # No byte cap: bounded by disk, not by RAM or an arbitrary limit.
        "max_file_bytes": None,
        "free_disk_bytes": free,
    }


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

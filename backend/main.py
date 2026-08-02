"""
Dockbench backend — optional, self-hosted, zero-per-call-cost API.

Every dependency here is free and open-source. There is no paid vendor
API anywhere in this file. You run this yourself (a VPS, a Docker
container, a Raspberry Pi with enough RAM) and it costs whatever your
own hosting costs — never a per-request fee.

The heavy lifting is done by battle-tested C/C++ engines driven from
Python — "C for the hot path, Python for the orchestration". The engine
logic itself lives in engines.py; this module is the HTTP layer.

Two ways to run a job:
  Synchronous  POST /ocr, /convert, /compress-pdf, /pdfa, /remove-bg
               — processed inline; fine for dev and small deployments.
  Queued       POST /jobs/{kind} -> {job_id}, GET /jobs/{id},
               GET /jobs/{id}/result — requires Redis (REDIS_URL) and the
               ARQ worker (see worker.py). This is the production path:
               the API answers instantly and the grinding happens in
               worker containers you can scale independently.

Also here:
  POST /summarize, /chat  -> local Ollama (self-hosted LLM)
  GET  /capabilities      -> which engines/queue this deployment has
  GET  /health            -> liveness;  GET /metrics -> Prometheus (opt-in)

Ops environment variables:
  REDIS_URL          enable the job queue (e.g. redis://redis:6379)
  TRUST_PROXY=1      rate-limit real client IPs from X-Forwarded-For
                     (set this when running behind the bundled nginx/Caddy)
  METRICS_ENABLED=1  expose GET /metrics
  LOG_JSON=1         structured JSON request logs
  MAX_FILE_MB        upload cap (default 50)

Privacy contract:
  - Nothing is ever logged about file contents or filenames.
  - Uploads for queued jobs live in Redis only until the worker reads
    them; results expire after 15 minutes (JOB_RESULT_TTL).
  - The external engines (LibreOffice, Ghostscript) require real files,
    so they use a private per-request temporary directory that is
    deleted the moment the response is built.
"""

import json
import logging
import os
import time
import uuid

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import engines
import native_ops
from engines import EngineError
from typing import List
from premium_pdf import run_merge_pdf, run_split_pdf, run_rotate_pdf, run_watermark_pdf

# ---------------------------------------------------------------------
# Logging: human-readable by default, JSON lines with LOG_JSON=1.
# ---------------------------------------------------------------------
LOG_JSON = os.environ.get("LOG_JSON") == "1"


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for k in ("request_id", "method", "path", "status", "ms"):
            if hasattr(record, k):
                entry[k] = getattr(record, k)
        return json.dumps(entry)


class _TextFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"  # records from libs/startup have no request
        return super().format(record)


_handler = logging.StreamHandler()
_handler.setFormatter(
    _JsonFormatter() if LOG_JSON
    else _TextFormatter("%(asctime)s %(levelname)s [%(request_id)s] %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger("dockbench")


# ---------------------------------------------------------------------
# Rate limiting that survives a reverse proxy.
# ---------------------------------------------------------------------
TRUST_PROXY = os.environ.get("TRUST_PROXY") == "1"


def client_ip(request: Request) -> str:
    """The bundled nginx/Caddy sit in front of this API in production, so
    request.client is always the proxy. With TRUST_PROXY=1 we take the
    first hop of X-Forwarded-For (set by our own proxy, so trustworthy);
    without it we fall back to the socket peer — never trust the header
    when any client can reach the API directly."""
    if TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip, default_limits=["60/minute"])
app = FastAPI(title="Dockbench API", version="0.3.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Lock this down to your actual frontend origin in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

if os.environ.get("METRICS_ENABLED") == "1":
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(excluded_handlers=["/metrics", "/health"]).instrument(app).expose(app)


@app.middleware("http")
async def request_id_and_timing(request: Request, call_next):
    """Tags every request with a short ID for tracing in logs, and times it.
    Never logs file contents or filenames — only method, path, status, timing."""
    req_id = uuid.uuid4().hex[:8]
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.0f}ms)",
        extra={"request_id": req_id, "method": request.method,
               "path": request.url.path, "status": response.status_code,
               "ms": round(duration_ms)},
    )
    response.headers["X-Request-ID"] = req_id
    return response


MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "50"))
REDIS_URL = os.environ.get("REDIS_URL", "")

# New configuration for large files (in MB). Default is 100 GB = 102400 MB.
LARGE_FILE_THRESHOLD_MB = int(os.environ.get("LARGE_FILE_THRESHOLD_MB", "102400"))
UPLOAD_TMP_DIR = os.environ.get("UPLOAD_TMP_DIR", "/tmp/uploads")
RESULT_TMP_DIR = os.environ.get("RESULT_TMP_DIR", "/tmp/results")

# Ensure temporary directories exist
import os as _os
_os.makedirs(UPLOAD_TMP_DIR, exist_ok=True)
_os.makedirs(RESULT_TMP_DIR, exist_ok=True)


def _check_size(data: bytes):
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_FILE_MB}MB limit.")


def _engine(fn, *args, **kwargs):
    """Run an engine function, translating EngineError to HTTP."""
    try:
        return fn(*args, **kwargs)
    except EngineError as e:
        raise HTTPException(e.status, e.detail)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/capabilities")
def capabilities():
    """Lets the frontend discover which optional engines this deployment
    has, so it can enable exactly the tools that will actually work."""
    return {
        "version": app.version,
        "native_c_kernel": native_ops.native_available(),
        "ocr": engines.which("tesseract") is not None,
        "ghostscript": engines.which("gs") is not None,
        "libreoffice": engines.which("soffice") is not None,
        "queue": bool(REDIS_URL),
        "ollama_configured": bool(os.environ.get("OLLAMA_URL", "http://localhost:11434")),
        "max_file_mb": MAX_FILE_MB,
    }


# ---------------------------------------------------------------------
# Queued jobs (production path). Requires REDIS_URL + the ARQ worker.
# ---------------------------------------------------------------------
_arq_pool = None


async def _pool():
    global _arq_pool
    if not REDIS_URL:
        raise HTTPException(501, "Job queue not configured on this server (REDIS_URL unset) — use the synchronous endpoint.")
    if _arq_pool is None:
        from arq import create_pool
        from arq.connections import RedisSettings

        _arq_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    return _arq_pool


@app.post("/jobs/{kind}")
@limiter.limit("20/minute")
async def submit_job(request: Request, kind: str, file: UploadFile = File(...)):
    if kind not in engines.JOB_KINDS:
        raise HTTPException(404, f"Unknown job kind '{kind}'. Valid: {sorted(engines.JOB_KINDS)}")
    pool = await _pool()
    data = await file.read()
    # Large file handling – bypass the small‑file size cap and store on disk.
    job_id = uuid.uuid4().hex
    upload_ttl = int(os.environ.get("JOB_RESULT_TTL", "900"))
    if len(data) > LARGE_FILE_THRESHOLD_MB * 1024 * 1024:
        # Store the upload as a temporary file on the fast SSD.
        upload_path = os.path.join(UPLOAD_TMP_DIR, f"{job_id}.bin")
        with open(upload_path, "wb") as f:
            f.write(data)
        await pool.set(f"dockbench:upload_path:{job_id}", upload_path, ex=upload_ttl)
    else:
        # Regular small file – keep the existing in‑memory flow and enforce the cap.
        _check_size(data)
        await pool.set(f"dockbench:upload:{job_id}", data, ex=upload_ttl)
    # Any extra multipart fields (language, target, level, ...) become
    # engine options — same names as the synchronous endpoints.
    form = await request.form()
    options = {k: v for k, v in form.items() if k != "file" and isinstance(v, str)}
    await pool.enqueue_job("process_job", kind, file.filename or "input",
                           options, _job_id=job_id)
    return JSONResponse({"job_id": job_id, "status": "queued"})


@app.get("/jobs/{job_id}")
@limiter.limit("240/minute")
async def job_status(request: Request, job_id: str):
    if not job_id.isalnum():
        raise HTTPException(422, "Invalid job id.")
    pool = await _pool()
    if await pool.exists(f"dockbench:result:{job_id}"):
        return JSONResponse({"job_id": job_id, "status": "complete"})

    from arq.jobs import Job, JobStatus

    job = Job(job_id, pool)
    status = await job.status()
    if status == JobStatus.not_found:
        raise HTTPException(404, "Unknown or expired job.")
    if status == JobStatus.complete:
        info = await job.result_info()
        if info and not info.success:
            return JSONResponse({"job_id": job_id, "status": "failed",
                                 "error": str(info.result)[:500]})
        return JSONResponse({"job_id": job_id, "status": "complete"})
    return JSONResponse({
        "job_id": job_id,
        "status": "running" if status == JobStatus.in_progress else "queued",
    })


@app.get("/jobs/{job_id}/result")
@limiter.limit("60/minute")
async def job_result(request: Request, job_id: str):
    if not job_id.isalnum():
        raise HTTPException(422, "Invalid job id.")
    pool = await _pool()
    payload = await pool.get(f"dockbench:result:{job_id}")
    if payload is None:
        raise HTTPException(404, "Result not ready or expired.")
    media_type = await pool.get(f"dockbench:resultmeta:{job_id}")
    media_type = media_type.decode() if isinstance(media_type, bytes) else (media_type or "application/octet-stream")
    if media_type == "text/plain":
        return JSONResponse({"text": payload.decode("utf-8", "replace")})
    return Response(content=payload, media_type=media_type)


# ---------------------------------------------------------------------
# Synchronous endpoints — same engines, processed inline. Fine for dev
# and small deployments; the frontend prefers /jobs when available.
# ---------------------------------------------------------------------
@app.post("/ocr")
@limiter.limit("10/minute")
async def ocr(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("eng"),
    output: str = Form("text"),
    enhance: bool = Form(True),
):
    data = await file.read()
    _check_size(data)
    payload, media_type = _engine(engines.run_ocr, data, file.filename or "",
                                  language=language, output=output, enhance=enhance)
    if media_type == "text/plain":
        return JSONResponse({"text": payload})
    return Response(content=payload, media_type=media_type)


@app.post("/remove-bg")
@limiter.limit("10/minute")
async def remove_bg(request: Request, file: UploadFile = File(...)):
    data = await file.read()
    _check_size(data)
    payload, media_type = _engine(engines.run_remove_bg, data)
    return Response(content=payload, media_type=media_type)


@app.post("/convert")
@limiter.limit("10/minute")
async def convert(request: Request, file: UploadFile = File(...), target: str = Form(...)):
    data = await file.read()
    _check_size(data)
    payload, media_type = _engine(engines.run_convert, data, file.filename or "input", target)
    return Response(content=payload, media_type=media_type)


@app.post("/compress-pdf")
@limiter.limit("10/minute")
async def compress_pdf(request: Request, file: UploadFile = File(...), level: str = Form("strong")):
    data = await file.read()
    _check_size(data)
    level = level.lower()
    logging.info("Compress endpoint called with level=%s, size=%d bytes", level, len(data))
    payload, media_type = _engine(engines.run_compress_pdf, data, level)
    headers = {"X-Compression": "already-optimal" if payload is data else f"{len(data)}->{len(payload)}"}
    return Response(content=payload, media_type=media_type, headers=headers)


@app.post("/pdfa")
@limiter.limit("10/minute")
async def pdfa(request: Request, file: UploadFile = File(...)):
    data = await file.read()
    _check_size(data)
    payload, media_type = _engine(engines.run_pdfa, data)
    return Response(content=payload, media_type=media_type)


# ---------------------------------------------------------------------
# Video processing endpoint – uses FFmpeg
# ---------------------------------------------------------------------
@app.post("/video-process")
@limiter.limit("10/minute")
async def video_process(request: Request, file: UploadFile = File(...), codec: str = Form("h264"), quality: str = Form("23")):
    """Process a video file with FFmpeg.

    * ``codec`` – video codec (e.g., ``h264`` or ``vp9``).
    * ``quality`` – CRF value (0‑51, lower = higher quality)."""
    data = await file.read()
    _check_size(data)
    payload, media_type = _engine(engines.run_video_process, data, file.filename or "input", codec, quality)
    return Response(content=payload, media_type=media_type)


# ---------------------------------------------------------------------
# Premium PDF endpoints
@app.post("/merge-pdf")
@limiter.limit("10/minute")
async def merge_pdf(request: Request, files: List[UploadFile] = File(...)):
    """Merge multiple PDF files into a single PDF.
    Supports very large inputs by streaming them from disk."""
    import tempfile, os
    from fastapi.responses import StreamingResponse
    from premium_pdf import run_merge_pdf_files

    input_paths = []
    try:
        for f in files:
            data = await f.read()
            _check_size(data)
            # Write each upload to a temporary file (required for the C engine)
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="upload_")
            os.close(tmp_fd)
            with open(tmp_path, "wb") as out:
                out.write(data)
            input_paths.append(tmp_path)

        # Perform the merge using the streaming implementation
        output_path, media_type = _engine(run_merge_pdf_files, input_paths)
    finally:
        # Clean up the temporary input files even if a upload/merge failed.
        for p in input_paths:
            try:
                os.remove(p)
            except OSError:
                pass

    def iterfile():
        with open(output_path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk
        try:
            os.remove(output_path)
        except OSError:
            pass

    return StreamingResponse(iterfile(), media_type=media_type)

@app.post("/split-pdf")
@limiter.limit("10/minute")
async def split_pdf(request: Request, file: UploadFile = File(...)):
    """Split a PDF into individual pages and return a ZIP archive."""
    data = await file.read()
    _check_size(data)
    payload, media_type = _engine(run_split_pdf, data)
    return Response(content=payload, media_type=media_type)

@app.post("/rotate-pdf")
@limiter.limit("10/minute")
async def rotate_pdf(request: Request, file: UploadFile = File(...), angle: int = Form(0)):
    """Rotate all pages of a PDF by the given angle (multiple of 90)."""
    data = await file.read()
    _check_size(data)
    payload, media_type = _engine(run_rotate_pdf, data, angle)
    return Response(content=payload, media_type=media_type)

@app.post("/watermark-pdf")
@limiter.limit("10/minute")
async def watermark_pdf(request: Request, file: UploadFile = File(...), watermark: UploadFile = File(...)):
    """Apply a PDF watermark to each page of the input PDF."""
    data = await file.read()
    wm_data = await watermark.read()
    _check_size(data)
    _check_size(wm_data)
    payload, media_type = _engine(run_watermark_pdf, data, wm_data)
    return Response(content=payload, media_type=media_type)

# ---------------------------------------------------------------------

# Batch PDF processing endpoint (no size caps as requested)
from batch_pdf import run_batch_pdf

@app.post("/batch-pdf")
@limiter.limit("10/minute")
async def batch_pdf(request: Request, job: str = Form(...), files: List[UploadFile] = File(...), angle: int = Form(0)):
    """Process multiple PDF jobs in one request.
    `job` can be: merge, split, rotate, watermark.
    For rotate, provide `angle`. For watermark, upload two files: base PDF and watermark PDF.
    """
    # Read all uploaded files
    data_list = []
    for f in files:
        data = await f.read()
        _check_size(data)
        data_list.append(data)
    # Dispatch to the appropriate helper
    payload, media_type = _engine(run_batch_pdf, job, data_list, angle=angle)
    return Response(content=payload, media_type=media_type)

# ---------------------------------------------------------------------
# Summarize / Chat — local LLM via Ollama (self-hosted, no API key, no
# per-token cost). Requires `ollama serve` running with a pulled model,
# e.g. `ollama pull llama3.2`.
# ---------------------------------------------------------------------
async def _ollama_generate(prompt: str) -> str:
    import httpx

    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            return r.json().get("response", "").strip()
    except Exception as e:
        raise HTTPException(
            503,
            f"Local model unavailable — is Ollama running with a pulled model? ({e})",
        )


@app.post("/summarize")
@limiter.limit("20/minute")
async def summarize(request: Request, text: str = Form(...), max_words: int = Form(150)):
    max_words = max(20, min(int(max_words), 1000))
    summary = await _ollama_generate(
        f"Summarize the following text in no more than {max_words} words. "
        f"Be concise and factual.\n\n{text[:60000]}"
    )
    return JSONResponse({"summary": summary})


@app.post("/chat")
@limiter.limit("20/minute")
async def chat(request: Request, question: str = Form(...), context: str = Form(...)):
    """Chat-with-your-document. The frontend extracts the text on-device and
    sends only the question plus the relevant excerpt — never the file."""
    answer = await _ollama_generate(
        "You are a helpful assistant answering questions about a document. "
        "Use ONLY the document excerpt below. If the answer is not in the "
        "excerpt, say so plainly.\n\n"
        f"DOCUMENT EXCERPT:\n{context[:60000]}\n\nQUESTION: {question[:2000]}\n\nANSWER:"
    )
    return JSONResponse({"answer": answer})

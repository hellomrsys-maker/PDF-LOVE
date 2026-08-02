"""
worker — ARQ background worker for the heavy engines.

Runs in its own container (same image as the API):

    arq worker.WorkerSettings

The API enqueues jobs (see the /jobs endpoints in main.py); this worker
picks them up, runs the matching engine from engines.py, and writes the
result back to Redis with a TTL. Per-engine semaphores keep one class of
job (e.g. LibreOffice conversions) from monopolizing the box while still
letting cheap jobs through.

Scale out with:  docker compose up -d --scale worker=3
"""

import asyncio
import base64
import os

from arq.connections import RedisSettings

import engines

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
RESULT_TTL = int(os.environ.get("JOB_RESULT_TTL", "900"))          # seconds
MAX_RESULT_MB = int(os.environ.get("JOB_MAX_RESULT_MB", "100"))

# How many of each engine may run at once *per worker process*. LibreOffice
# and OCR are the heavy ones; Ghostscript is comparatively cheap.
ENGINE_LIMITS = {
    "convert": int(os.environ.get("LIMIT_CONVERT", "2")),
    "ocr": int(os.environ.get("LIMIT_OCR", "2")),
    "compress-pdf": int(os.environ.get("LIMIT_GS", "3")),
    "pdfa": int(os.environ.get("LIMIT_GS", "3")),
    "remove-bg": int(os.environ.get("LIMIT_REMBG", "1")),
}
_semaphores = {}


def _sem(kind):
    if kind not in _semaphores:
        _semaphores[kind] = asyncio.Semaphore(ENGINE_LIMITS.get(kind, 2))
    return _semaphores[kind]


async def process_job(ctx, kind: str, filename: str, options: dict):
    """Fetch the uploaded bytes from Redis, run the engine, store the result.
    The upload is deleted the moment it has been read; results expire after
    RESULT_TTL. Nothing about file contents is ever logged."""
    redis = ctx["redis"]
    job_id = ctx["job_id"]

    # Try to fetch in‑memory upload first.
    data = await redis.get(f"pdflove:upload:{job_id}")
    if data is not None:
        # In‑memory payload – delete the key and continue.
        await redis.delete(f"pdflove:upload:{job_id}")
    else:
        # Fallback to a temporary file path (large upload).
        path_key = f"pdflove:upload_path:{job_id}"
        upload_path = await redis.get(path_key)
        if not upload_path:
            raise RuntimeError("Upload expired before the job started — resubmit.")
        # Delete the path reference from Redis.
        await redis.delete(path_key)
        upload_path = upload_path.decode() if isinstance(upload_path, bytes) else upload_path
        # Read the file contents into memory for the engine.
        with open(upload_path, "rb") as f:
            data = f.read()
        # Remove the temporary file now that it has been consumed.
        try:
            os.remove(upload_path)
        except OSError:
            pass

    if kind not in engines.JOB_KINDS:
        raise RuntimeError(f"Unknown job kind: {kind}")

    async with _sem(kind):
        # Engines are synchronous (subprocess/C calls) — run them off the
        # event loop so one job never blocks the worker's heartbeat.
        payload, media_type = await asyncio.to_thread(
            engines.JOB_KINDS[kind], data, filename, **options
        )

    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if len(payload) > MAX_RESULT_MB * 1024 * 1024:
        raise RuntimeError(f"Result exceeds {MAX_RESULT_MB}MB limit.")

    await redis.set(f"pdflove:result:{job_id}", payload, ex=RESULT_TTL)
    await redis.set(f"pdflove:resultmeta:{job_id}", media_type, ex=RESULT_TTL)
    return {"media_type": media_type, "bytes": len(payload)}


class WorkerSettings:
    functions = [process_job]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = int(os.environ.get("WORKER_MAX_JOBS", "6"))
    job_timeout = int(os.environ.get("JOB_TIMEOUT", "300"))
    keep_result = RESULT_TTL
    health_check_interval = 30

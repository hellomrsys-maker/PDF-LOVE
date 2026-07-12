"""
Dockbench backend — optional, self-hosted, zero-per-call-cost API.

Every dependency here is free and open-source. There is no paid vendor
API anywhere in this file. You run this yourself (a VPS, a Docker
container, a Raspberry Pi with enough RAM) and it costs whatever your
own hosting costs — never a per-request fee.

Endpoints:
  POST /ocr          -> extract text from an image or scanned PDF (Tesseract)
  POST /remove-bg     -> remove image background (rembg, open-weight model)
  POST /summarize      -> summarize text using a local Ollama model
  GET  /health        -> liveness check

Every endpoint:
  - never writes the uploaded file to disk (processed in-memory)
  - never logs file contents
  - returns the result and immediately discards the input from memory
"""

import io
import logging
import os
import time
import uuid

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(request_id)s] %(message)s",
)
logger = logging.getLogger("dockbench")

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app = FastAPI(title="Dockbench API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Lock this down to your actual frontend origin in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_timing(request: Request, call_next):
    """Tags every request with a short ID for tracing in logs, and times it.
    Never logs file contents or filenames — only method, path, status, timing."""
    req_id = uuid.uuid4().hex[:8]
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logging.LoggerAdapter(logger, {"request_id": req_id}).info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.0f}ms)"
    )
    response.headers["X-Request-ID"] = req_id
    return response


MAX_FILE_MB = 25
# Per-endpoint rate limits are applied below via @limiter.limit(...).
# The heavy endpoints (ocr, remove-bg, summarize) get a tighter cap since
# they're the ones that can actually load a CPU/GPU; health/static-ish
# checks are unlimited beyond the global default above.


def _check_size(data: bytes):
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_FILE_MB}MB limit.")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------
# OCR  — open-source Tesseract (pytesseract). Zero per-call cost.
# For higher accuracy on tables/multilingual docs, swap in PaddleOCR
# (see requirements.txt for the alternative install).
# ---------------------------------------------------------------------
@app.post("/ocr")
@limiter.limit("10/minute")
async def ocr(request: Request, file: UploadFile = File(...), language: str = Form("eng")):
    import pytesseract
    from PIL import Image

    data = await file.read()
    _check_size(data)

    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".pdf"):
            # Render each PDF page to an image, then OCR each page.
            import fitz  # PyMuPDF — open-source, MIT license

            doc = fitz.open(stream=data, filetype="pdf")
            pages_text = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                pages_text.append(pytesseract.image_to_string(img, lang=language))
            doc.close()
            text = "\n\n--- page break ---\n\n".join(pages_text)
        else:
            img = Image.open(io.BytesIO(data))
            text = pytesseract.image_to_string(img, lang=language)
    except Exception as e:
        raise HTTPException(422, f"Could not process file: {e}")
    finally:
        # Explicitly drop references so the file isn't retained in memory
        # longer than necessary.
        del data

    return JSONResponse({"text": text})


# ---------------------------------------------------------------------
# Background removal — open-source rembg (Apache-2.0), self-hosted.
# ---------------------------------------------------------------------
@app.post("/remove-bg")
@limiter.limit("10/minute")
async def remove_bg(request: Request, file: UploadFile = File(...)):
    from rembg import remove

    data = await file.read()
    _check_size(data)

    try:
        output = remove(data)
    except Exception as e:
        raise HTTPException(422, f"Could not process image: {e}")
    finally:
        del data

    from fastapi.responses import Response
    return Response(content=output, media_type="image/png")


# ---------------------------------------------------------------------
# Summarize — local LLM via Ollama (self-hosted, no API key, no
# per-token cost). Requires `ollama serve` running with a pulled model,
# e.g. `ollama pull llama3.2`.
# ---------------------------------------------------------------------
@app.post("/summarize")
@limiter.limit("20/minute")
async def summarize(request: Request, text: str = Form(...), max_words: int = Form(150)):
    import httpx

    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")

    prompt = (
        f"Summarize the following text in no more than {max_words} words. "
        f"Be concise and factual.\n\n{text}"
    )

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            result = r.json()
    except Exception as e:
        raise HTTPException(
            503,
            f"Local summarization model unavailable — is Ollama running? ({e})",
        )

    return JSONResponse({"summary": result.get("response", "").strip()})

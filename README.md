# Dockbench

A 100-tool PDF, image & video workbench that processes files **on your device by
default**, with an optional self-hosted backend for the handful of jobs
that genuinely need server compute. Every dependency in this project is
free and open-source — there is no paid API anywhere in the stack, and
after the first page load the core app runs **fully offline**.

## Why it beats the alternatives

| | Dockbench | iLovePDF / Smallpdf (paid) | Stirling-PDF (self-hosted) |
|---|---|---|---|
| Files stay on-device | ✅ for ~90 of 100 tools | ❌ every tool uploads | ❌ every tool goes to the server |
| Works by double-clicking the HTML file | ✅ no server needed at all | ❌ | ❌ |
| Video tools (GIF, trim, slideshow, screen rec.) | ✅ on-device | partial, cloud | ❌ |
| Works offline (PWA) | ✅ core app + encryption | ❌ | ❌ needs the server |
| Daily limits / subscription | none | 1-2 free tasks/day, then $4-10/mo | none |
| Real AES-256 encrypt/decrypt in the browser | ✅ (qpdf → WebAssembly) | server-side | server-side |
| OCR → searchable PDF | ✅ (self-hosted, C-accelerated cleanup) | ✅ (their cloud) | ✅ |
| Office ↔ PDF (full fidelity) | ✅ (self-hosted LibreOffice) | ✅ (their cloud) | ✅ |
| AI summarize/translate/chat | ✅ on-device (Transformers.js) or your own Ollama | ☁ their cloud AI | partial |
| External services required | none (one optional: live FX rates) | their cloud | none |

The design principle: **keep the high-frequency tools 100% local** for the
trust story and zero hosting cost, and reserve the server for jobs where
real engines (Tesseract, LibreOffice, Ghostscript) are the difference
between a toy and a tool — while keeping that server yours, free, and
open-source.

## Structure

```
├── frontend/
│   ├── index.html        ← the entire client-side app (100 tools)
│   ├── vendor/           ← all JS/WASM libraries, self-hosted (no CDN needed)
│   ├── manifest.json, sw.js  ← installable PWA, offline-capable
│   ├── nginx.conf        ← production static hosting + /api/ reverse proxy
│   └── Dockerfile        ← nginx-based image
├── backend/               ← optional, for the server-assisted tools
│   ├── main.py           ← FastAPI app (see endpoints below)
│   ├── native/imgproc.c  ← C scan-cleanup kernel (compiled in Docker)
│   ├── native_ops.py     ← ctypes bridge with pure-Python fallback
│   └── Dockerfile        ← gunicorn + Tesseract + Ghostscript + LibreOffice
├── docker-compose.yml    ← frontend + backend + local LLM (Ollama)
└── .github/workflows/validate.yml  ← CI: syntax, wiring, C kernel tests
```

## 1. Frontend — no setup, no build step, no CDN

**The simplest way to run Dockbench: download the `frontend/` folder and
double-click `index.html`.** Everything works straight from the file —
PDF rendering runs on the main thread via the bundled worker script, and
even AES-256 encryption works offline (the WASM engine ships as an
embedded base64 copy in `vendor/qpdf.wasm.b64.js`, because browsers block
fetching local `.wasm` files). Only the server-assisted section needs
more than that.

`frontend/index.html` plus `frontend/vendor/` is the complete client-side
app. Every library it uses (pdf-lib, pdf.js, JSZip, mammoth, jsPDF,
html2canvas, qrcode, jsQR, JsBarcode, and qpdf compiled to WebAssembly)
is **self-hosted in `vendor/`** — zero external requests, and each script
tag still carries a pinned-version CDN fallback in case a stray copy of
the HTML is served without the vendor directory.

- **Serve it statically**:
  ```bash
  cd frontend
  python3 -m http.server 5500   # visit http://localhost:5500
  ```
- **Deploy it anywhere that hosts static files** — Netlify, GitHub Pages,
  S3, your own nginx. Hosting cost is effectively zero.
- **Install it as an app** — the service worker precaches everything, so
  after one visit the whole toolbox (including AES-256 encryption) works
  in airplane mode.
- **Navigate fast** — category tabs act like separate pages, Ctrl/Cmd+K
  jumps to search, ★ pins favorites to the top, and a "recently used"
  row remembers your workflow (both stored only in your browser). The
  whole UI follows your system's light/dark preference.

On-device highlights (~85 tools): merge, split (range or per-page),
organize, crop, rotate, N-up, compress, repair, compare, scan-to-PDF,
extract images, **flatten forms**, **sanitize (strip scripts/attachments/
metadata)**, grayscale, Bates numbering, headers/footers, watermark,
search-&-redact (SSNs/emails/phones), sign, stamp, forms, **protect/unlock
with real AES-256 in the browser**, PDF↔Word/Markdown/text, Markdown→PDF,
images↔PDF (JPG/PNG/WebP/GIF/BMP), image compress/resize/convert/rotate,
**EXIF viewer & stripper**, passport photos, ID/business cards, favicon
generator, QR/barcode, plus text, utility, finance, and fully on-device AI
tools (summarize, translate, voice-to-text, image captioning via
Transformers.js — model downloads once, then offline).

**Video tools** (new, all on-device): images → slideshow video with
crossfades, video → GIF (gifenc, pure JS), trim video (keeps audio),
screen recorder, and extract-audio-to-WAV. Recording uses the browser's
MediaRecorder — MP4 where the browser supports it, WebM otherwise, and
the button label tells you which before you click.

Every on-device tool reads the file with the File API, processes it in
memory, and triggers a browser download — the bytes never touch a network
request. Verify it yourself: devtools → Network tab → use any tool → no
request fires.

## 2. Backend — optional, self-hosted, C-accelerated

The server-assisted tools use real engines, all C/C++ under a Python
orchestration layer — "C for the hot path, Python for the glue":

| Tool | Engine | License |
|---|---|---|
| OCR (text or **searchable PDF**) | Tesseract 5 (C++) + `native/imgproc.c` cleanup kernel | Apache-2.0 |
| Office → PDF (full fidelity) | LibreOffice headless (C++) | MPL-2.0 |
| PDF → Word (layout-aware) | pdf2docx on MuPDF (C) | GPL-3 / AGPL-3 |
| PDF → PowerPoint / Excel | PyMuPDF rendering / table detection (C) | AGPL-3 |
| Deep PDF compression | Ghostscript (C) | AGPL-3 |
| PDF/A archival conversion | Ghostscript (C) | AGPL-3 |
| Background removal | rembg + onnxruntime (C++) | Apache-2.0 |
| Summarize / Chat with PDF | Ollama running Llama 3.2 locally | Llama license (free for this use) |

### The native C kernel

`backend/native/imgproc.c` is this project's own scan-cleanup kernel,
compiled with `-O3` in the Docker build and driven from Python via ctypes
(`native_ops.py`). It preprocesses every scanned page before OCR —
grayscale → percentile contrast stretch → inverted-scan detection → Otsu
binarization — in exactly **two passes over the pixels**; everything in
between is computed on a 256-bin histogram and folded into a single
lookup table. Faded scans, photographed documents, and white-on-black
pages all come out clean, which is what actually moves Tesseract's
accuracy. If the shared library isn't built, `native_ops.py` silently
falls back to a pure-Pillow implementation, so the API runs anywhere.

### Run it

```bash
docker compose up -d
docker exec -it $(docker compose ps -q ollama) ollama pull llama3.2
```

This starts:
- `frontend` on `http://localhost` (nginx, proxies `/api/*` to the backend
  so the browser only ever talks to one origin — no CORS setup needed)
- `backend` on port 8000 inside the compose network (FastAPI, docs at `/docs`)
- `ollama` for the local LLM tools

The frontend auto-detects the backend at `/api`. Pointing it somewhere
else takes one line in the browser console:
`localStorage.setItem('dockbench.apiBase', 'https://your-server:8000')`.

### Endpoints

- `POST /ocr` — `file`, `language` (default `eng`), `output` (`text` |
  `pdf` for a searchable PDF), `enhance` (C kernel cleanup, default on)
- `POST /convert` — `file`, `target` (`pdf` from any Office format;
  `docx` / `pptx` / `xlsx` from PDF)
- `POST /compress-pdf` — `file`, `level` (`balanced` | `strong` | `extreme`);
  never returns a bigger file than the input
- `POST /pdfa` — `file` → ISO 19005 PDF/A-2b
- `POST /remove-bg` — `file` → transparent PNG
- `POST /summarize` — `text`, `max_words`
- `POST /chat` — `question`, `context` (the frontend extracts text
  on-device and sends only relevant excerpts, never the file)
- `GET /capabilities` — which engines this deployment has (the frontend
  can use it to enable exactly what will work)
- `GET /health` — liveness check

Privacy contract: nothing about file contents or names is ever logged;
pure-Python endpoints work entirely in memory; the engines that require
real files (LibreOffice, Ghostscript) get a private per-request temp
directory deleted the moment the response is built. Rate limits
(10-20/min/IP on heavy endpoints) keep one user from starving the box.
`MAX_FILE_MB` (default 50) caps upload size.

## Production notes

- **Set `ALLOWED_ORIGINS`** in `docker-compose.yml` to your real domain.
- **HTTPS**: put Caddy / nginx + Let's Encrypt or a cloud LB in front.
- **Scale out**: `docker compose up -d --scale backend=3` — Docker's DNS
  round-robins across replicas on one host; use a real LB across hosts.
- **Structured logs**: every request gets an `X-Request-ID`, logged with
  method/path/status/timing only.
- **Health checks** are wired into compose so the frontend won't route to
  a backend that isn't ready.
- **Heavy traffic?** Consider a task queue (Celery/RQ) in front of `/ocr`
  and `/convert` so slow jobs don't hold workers hostage.
- The backend image includes LibreOffice + Ghostscript + Tesseract, so it
  is a few GB — that is the price of full-fidelity conversion with zero
  per-call cost. Strip engines you don't need from `backend/Dockerfile`
  and `/capabilities` will report accordingly.
- Extra OCR languages: add e.g. `tesseract-ocr-deu` to the Dockerfile.

## CI

`.github/workflows/validate.yml` runs on every push: JS syntax of the
whole inline app, every tool card resolving to a real function, no
duplicate tool names, all 14 vendor assets present and precached by the
service worker (including a freshness check that the base64 WASM copy
matches the real binary), Python syntax, a real import of the backend app, a
`-Wall -Wextra -Werror` compile of the C kernel, and an end-to-end
binarization test of both the C path and the Pillow fallback (including
inverted-scan correction).

## Roadmap (not yet built)

- PaddleOCR as a swap-in for better table/multilingual accuracy
- Batch/queue support on the backend for bulk processing
- A visual pipeline builder (chain tools like "split → OCR → compress")
- WebGPU acceleration for the on-device AI models as browser support lands

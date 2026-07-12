# Dockbench

A PDF & image toolkit that processes files on-device by default, with an
optional self-hosted backend for the handful of tools that genuinely need
server compute (OCR, background removal, AI summarize). Every dependency
in this project is free and open-source — there is no paid API anywhere
in the stack.

## Structure

```
docktool/
├── frontend/
│   └── index.html      ← the entire client-side app (open it in a browser, done)
├── backend/
│   ├── main.py          ← FastAPI app: /ocr, /remove-bg, /summarize
│   ├── requirements.txt
│   └── Dockerfile
└── docker-compose.yml   ← backend + local LLM (Ollama), one command
```

## 1. Frontend — no setup required

`frontend/index.html` is a complete, self-contained web app. It uses
`pdf-lib`, `pdf.js`, and `JSZip` from a CDN, and does everything else
with the browser's Canvas API. There is no build step.

- **Open it directly** by double-clicking the file, or
- **Serve it statically** (recommended, avoids some browser file:// restrictions):
  ```bash
  cd frontend
  python3 -m http.server 5500
  # visit http://localhost:5500
  ```
- **Deploy it anywhere that hosts static files** — Netlify, Vercel, GitHub
  Pages, S3+CloudFront, your own nginx box. There is no server-side
  rendering and no backend dependency for the tools in the first two
  sections (PDF tools, image tools). Hosting cost is effectively zero.

Working today, fully client-side:
- Merge PDF, Split PDF, Organize PDF (reorder/remove pages), Crop PDF, Rotate PDF
- Images → PDF, PDF → JPG
- PDF → Word (.docx, text-only), PDF → Markdown, Word (.docx) → PDF
- PDF Editor (click-to-place text), Add Watermark, Redact/remove watermark (rasterized), Add Page Numbers, Sign PDF (draw + place signature)
- Compress Image, Resize Image

Every one of these tools reads the file with the File API, processes it
in memory, and triggers a browser download — the bytes never touch a
`fetch()` or `XMLHttpRequest` call. You can verify this yourself: open
devtools → Network tab → use any tool above → no request fires.

## 2. Backend — optional, only for OCR / background removal / AI summarize

These three tools need real compute that doesn't fit in a browser tab
(large OCR models, background-removal neural nets, LLM inference). They
are **not required** to use the rest of the app, and the frontend labels
them clearly as "server-assisted" so users always know which bucket a
tool falls into before they use it.

Everything here is open-source and self-hosted, so there's no per-call
API bill — you pay only for your own server:

| Tool | Engine | License |
|---|---|---|
| OCR | Tesseract 5 (via pytesseract) + PyMuPDF for PDF rendering | Apache-2.0 |
| Background removal | rembg | Apache-2.0 (models MIT/Apache) |
| Summarize | Ollama running Llama 3.2 locally | Llama license (free for this use) |

### Run it

```bash
docker compose up -d
docker exec -it $(docker compose ps -q ollama) ollama pull llama3.2
```

This starts:
- `backend` on `http://localhost:8000` (FastAPI, auto docs at `/docs`)
- `ollama` on `http://localhost:11434` (local LLM runtime)

Then in `frontend/index.html`, set `API_BASE` (top of the `<script>`
block) to your backend's URL, and wire the three server-assisted tool
stubs (`toolServerStub` calls) to `fetch()` the corresponding endpoint —
each stub already documents exactly which endpoint it needs.

### Endpoints

- `POST /ocr` — form fields: `file`, `language` (default `eng`) → `{ "text": "..." }`
- `POST /remove-bg` — form field: `file` → PNG image bytes
- `POST /summarize` — form fields: `text`, `max_words` → `{ "summary": "..." }`
- `GET /health` — liveness check

Files are processed entirely in memory and never written to disk or
logged. Set `ALLOWED_ORIGINS` in the environment to your real frontend
domain before going to production (defaults to `*` for local dev).

## Why this split

This mirrors what the current wave of privacy-first PDF/image tools
(BentoPDF, PDFCraft, DropFile, and others) have converged on in 2026:
keep the high-frequency, low-compute tools 100% local for the trust
story and near-zero hosting cost, and reserve a server only for the
handful of tools where server compute is genuinely the difference
between a toy feature and a useful one — while keeping that server
free/open-source so it never becomes a per-request cost center.

## Production deployment & scaling

```
docktool/
├── frontend/
│   ├── index.html
│   ├── manifest.json, sw.js
│   ├── nginx.conf        ← production static hosting + /api/ reverse proxy
│   └── Dockerfile        ← nginx-based image
├── backend/
│   ├── main.py           ← rate-limited, structured-logging FastAPI app
│   ├── Dockerfile        ← gunicorn + multiple uvicorn workers
│   └── requirements.txt
├── docker-compose.yml    ← frontend + backend + ollama, health-checked
└── .github/workflows/validate.yml  ← CI: syntax, duplicate, and import checks
```

**Run it in production:**
```bash
docker compose up -d
docker exec -it $(docker compose ps -q ollama) ollama pull llama3.2
```
This builds the frontend behind nginx (port 80) and proxies `/api/*` straight
to the backend container, so the browser only ever talks to one origin —
no CORS configuration needed once deployed this way.

**What changed for real production use, and why:**
- **CDN libraries load with `defer`, not blocking initial paint** — the
  page renders before pdf-lib/pdf.js/etc. finish downloading. The app's
  main script waits for `DOMContentLoaded` (which fires after deferred
  scripts run, per spec) before touching any of them, so nothing breaks.
- **Rate limiting** on the three heavy backend endpoints (`/ocr`, `/remove-bg`,
  `/summarize`) via slowapi — 10–20 requests/minute per IP — so one user
  can't accidentally (or deliberately) starve the CPU/GPU for everyone else.
- **Structured logging with request IDs** — every request gets a short ID,
  logged with method/path/status/timing (never file contents or names),
  and returned as an `X-Request-ID` response header for tracing.
- **Multi-worker backend** — `gunicorn` manages several `uvicorn` worker
  processes so the API uses more than one CPU core. Tune `--workers` in
  `backend/Dockerfile` to your box; more workers means more memory since
  each one can hold its own model instance.
- **Horizontal scaling** — `docker compose up -d --scale backend=3` runs
  three backend replicas; Docker's internal DNS round-robins between them
  automatically on a single host. For multi-host, put a real load balancer
  (nginx, traefik, or a cloud LB) in front.
- **Health checks** — the backend's `/health` endpoint is wired into
  `docker-compose.yml` so `frontend` won't start routing traffic to it
  until it's actually ready, and orchestrators (Docker, Kubernetes) can
  restart it automatically if it stops responding.
- **CI validation** — `.github/workflows/validate.yml` runs the exact
  checks used throughout development: JS syntax, every tool card resolving
  to a real function, no duplicate tool names, Python syntax, and a real
  import of the backend app. All of these were run and passed locally
  before this was written, not just assumed.

**What's still your call to configure before going fully live:**
- Set `ALLOWED_ORIGINS` in `docker-compose.yml` to your real domain, not `localhost`
- Put the whole thing behind HTTPS (e.g. Caddy or nginx + Let's Encrypt in front of this stack, or a cloud load balancer that terminates TLS)
- If you expect real traffic, consider a task queue (Celery/RQ) in front of `/ocr` and `/remove-bg` instead of handling them inline, so slow requests don't hold a worker hostage

## Roadmap (not yet built)

- Wire the three server-assisted stubs to the live backend
- PDF password protect/unlock, watermark, page numbers (client-side, pdf-lib)
- Office ↔ PDF conversion via a self-hosted LibreOffice-headless service
- PaddleOCR as a swap-in for better table/multilingual accuracy
- Batch/queue support on the backend for bulk processing
- PWA manifest + service worker for offline installability

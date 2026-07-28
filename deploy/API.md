# PDF Love API

The HTTP API exposes the server-side engines — OCR, full-fidelity Office
conversion, Ghostscript compression, PDF/A, background removal — for
programmatic use.

> **The on-device app is not this API.** The 94 on-device tools in
> `frontend/` run entirely in the browser and never call anything. They are
> free, unlimited and unauthenticated, and this document does not apply to
> them.

## Two deployments, two rules

| Running it | API key required |
|---|---|
| **Self-hosted** (your VPS, your Docker) | **No.** It is your server. |
| **Desktop app's bundled engine** | **No.** Loopback-only, session-token guarded. |
| **Our hosted API** | **Yes** — business tier. |

Enforcement is opt-in via `REQUIRE_API_KEY=1`. Self-hosters never set it.

## Authentication

Send the key as a bearer token:

```bash
curl -X POST https://api.pdflove.co.in/ocr \
  -H "Authorization: Bearer dkb_live_eyJzdWIi..." \
  -F file=@scan.pdf \
  -F output=pdf
```

Keys look like `dkb_live_<payload>.<signature>` and are ECDSA P-256
signatures over the payload, using the same signing identity as the offline
licence system in `licensing/`.

Verification happens **offline**, in-process, against a public key. There is
no database lookup and no licence server on the request path, so an
air-gapped deployment works normally and a key check costs microseconds.

### Issuing keys

```bash
node licensing/mint-api-key.js --sub=acme-corp --tier=business \
     --quota=50000 --expires=2027-12-31
```

Then point the backend at the public half:

```bash
DOCKBENCH_API_PUBLIC_KEY_FILE=/run/secrets/pdflove-api-public-key.json
REQUIRE_API_KEY=1
```

Starting with `REQUIRE_API_KEY=1` and no verifying key configured is a fatal
error rather than a silent no-op — a deployment that believes it is
protected must not accept every request.

### Revocation

Signature verification alone cannot un-issue a key. Either keep `--expires`
short and reissue periodically (simplest, and enough for most customers), or
add a deny-list of `sub` values checked in `apikeys.verify`.

## Rate limits

Requests are bucketed by the key's `sub`, not by IP — a customer calling
from a fleet gets one quota, and customers behind a shared NAT don't
collide. Unkeyed traffic falls back to per-IP.

Defaults: 60/min overall, 10/min on the heavy endpoints (`/ocr`,
`/convert`, `/compress-pdf`, `/pdfa`, `/remove-bg`), 20/min on `/summarize`
and `/chat`. Exceeding a limit returns `429`.

## Endpoints

Interactive docs (OpenAPI) are served at `/docs` on any running instance.

### Open — no key, ever

| Method | Path | Returns |
|---|---|---|
| `GET` | `/health` | `{"status":"ok"}` — for monitoring |
| `GET` | `/capabilities` | which engines and backends this instance has |

`/capabilities` reports `imgproc_backend` and `pdf_backend` as either
`extension` (the fused in-process C path) or a fallback name, so you can
verify what a deployment is actually running.

### Gated when `REQUIRE_API_KEY=1`

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/ocr` | `file`, `language=eng`, `output=text\|pdf`, `enhance=true` | text JSON or searchable PDF |
| `POST` | `/convert` | `file`, `target=pdf\|docx\|pptx\|xlsx` | converted file |
| `POST` | `/compress-pdf` | `file`, `level=balanced\|strong\|extreme` | PDF, never larger than input |
| `POST` | `/pdfa` | `file` | ISO 19005 PDF/A-2b |
| `POST` | `/remove-bg` | `file` | transparent PNG |
| `POST` | `/video-process` | `file`, `codec=h264`, `quality=23` | re-encoded video |
| `POST` | `/merge-pdf` | `files[]` | merged PDF (streamed) |
| `POST` | `/split-pdf` | `file` | ZIP, one PDF per page |
| `POST` | `/rotate-pdf` | `file`, `angle` (multiple of 90) | rotated PDF |
| `POST` | `/watermark-pdf` | `file`, `watermark` | stamped PDF |
| `POST` | `/batch-pdf` | `job`, `files[]`, `angle` | depends on `job` |
| `POST` | `/summarize` | `text`, `max_words` | `{"summary": "..."}` |
| `POST` | `/chat` | `question`, `context` | `{"answer": "..."}` |

### Queued jobs

Long jobs should go through the queue so the API answers immediately:

```bash
# submit
curl -X POST https://api.pdflove.co.in/jobs/ocr \
  -H "Authorization: Bearer $KEY" -F file=@big.pdf -F output=pdf
# -> {"job_id":"a1b2...","status":"queued"}

# poll
curl -H "Authorization: Bearer $KEY" https://api.pdflove.co.in/jobs/a1b2...
# -> {"job_id":"a1b2...","status":"running"|"complete"|"failed"}

# collect
curl -H "Authorization: Bearer $KEY" https://api.pdflove.co.in/jobs/a1b2.../result -o out.pdf
```

Valid kinds: `ocr`, `convert`, `compress-pdf`, `pdfa`, `remove-bg`,
`video-process`, `split-pdf`, `rotate-pdf`.

Merge and watermark are **not** queueable — a queued job carries exactly one
upload and its options arrive as form strings, so there is nowhere for a
second PDF to come from. Use the synchronous endpoints, which take real
multi-file uploads.

Results expire after `JOB_RESULT_TTL` (default 900s).

## Errors

| Status | Meaning |
|---|---|
| `401` | missing, malformed, expired or unsigned API key |
| `413` | upload exceeds `MAX_FILE_MB` (or `MAX_SPOOL_MB` for queued jobs) |
| `422` | bad input — unreadable PDF, invalid angle, unknown job kind |
| `429` | rate limit exceeded |
| `501` / `503` | engine not installed on this deployment — check `/capabilities` |
| `504` | engine timed out |

Every response carries an `X-Request-ID` for correlating with server logs.

## Privacy

The backend logs method, path, status and timing only. File contents and
filenames are never logged. Engines that need real files (LibreOffice,
Ghostscript) get a per-request temp directory deleted as soon as the
response is built. Queued uploads live in Redis until the worker reads
them, and are deleted at that point.

# Dockbench in production

One VPS, docker compose, automatic HTTPS. Total operating cost: the
server. There are no external services and nothing to subscribe to.

## Architecture

```
                    ┌──────────────────────── VPS ───────────────────────┐
 users ── 443 ──▶ Caddy ──▶ nginx (frontend, static + /api proxy)        │
                    │                 │                                  │
                    │                 ▼                                  │
                    │          FastAPI backend ──▶ Redis ◀── ARQ workers │
                    │          (answers instantly)   (queue)  (OCR/Office│
                    │                                          /Ghostscr.│
                    │                                          — scale N)│
                    └─────────────────────────────────────────────────────┘
```

- The **API never blocks**: heavy jobs (OCR, Office conversion, PDF/A,
  deep compression, background removal) are queued in Redis and executed
  by worker containers; the frontend polls job status.
- Everything is **stateless** — Redis holds only in-flight jobs (15-min
  TTL). Losing the box loses nothing but the TLS cert cache.

## Quickstart (fresh Ubuntu/Debian VPS)

```bash
# 1. Docker
curl -fsSL https://get.docker.com | sh

# 2. DNS: point an A (and AAAA) record for your domain at this server.

# 3. Dockbench
git clone https://github.com/hellomrsys-maker/Dockbench && cd Dockbench
cp .env.example .env
nano .env        # set DOMAIN, ACME_EMAIL, ALLOWED_ORIGINS

# 4. Up (pulls the CI-built images; TLS is automatic)
docker compose --profile prod up -d

# 5. Optional: the local-LLM tools (Chat with PDF / Summarize)
docker compose --profile prod --profile ai up -d
docker exec -it $(docker compose ps -q ollama) ollama pull llama3.2
```

Visit `https://your-domain` — done.

## Day-2 operations

**Update to the newest release**
```bash
docker compose pull && docker compose --profile prod up -d
```
(Compose replaces containers one service at a time; the stateless design
means no migrations, ever. Pin versions in `.env` via `FRONTEND_IMAGE` /
`BACKEND_IMAGE` for strictly reproducible deploys.)

**Watch it**
- Liveness: `GET /api/health` → `{"status":"ok"}` (wire into UptimeRobot etc.)
- Metrics: Prometheus format on the compose network at
  `backend:8000/metrics` (blocked from the public internet by nginx).
  Scrape config:
  ```yaml
  - job_name: dockbench
    static_configs: [{targets: ["backend:8000"]}]
  ```
- Logs: `docker compose logs -f backend worker` — JSON lines with
  request IDs (`LOG_JSON=1`), rotated automatically (10 MB × 3 files).

**Back up**
- `.env` is the only state worth saving. Certificates re-issue
  automatically; Redis content is disposable by design.

**When the queue backs up**
```bash
docker compose up -d --scale worker=3     # more muscle, same box
```
Then raise `WORKER_MAX_JOBS` cautiously (each LibreOffice/OCR job wants
~0.5-1 GB RAM). Rough capacity on a 4 vCPU / 8 GB VPS: ~40-60 OCR pages
per minute sustained, with the API staying <50 ms p95 throughout —
verify on your own box with the load test below.

**Load test**
```bash
python3 scripts/loadtest.py https://your-domain/api 20 15
```
Prints p50/p95/p99 for the hot endpoints plus one full queue round trip.

## Security checklist (what's already handled, what's yours)

Handled by the stack:
- TLS + HSTS (Caddy, auto-renewing Let's Encrypt)
- Strict Content-Security-Policy, nosniff, frame-ancestors none
- Non-root containers (`nginx-unprivileged`, backend `uid 10001`),
  `no-new-privileges`, tmpfs scratch space, memory limits
- Per-IP rate limits that see the *real* client IP behind the proxy
  (`TRUST_PROXY=1` + first-hop X-Forwarded-For)
- Upload caps at both nginx (60 MB body) and the app (`MAX_FILE_MB`)
- No accounts, no cookies, no stored documents — nothing to breach

Yours:
- Keep the box patched (`unattended-upgrades`), SSH keys only
- Set `ALLOWED_ORIGINS` to your exact origin
- A firewall allowing only 22/80/443 (e.g. `ufw`)

## Scaling beyond one box

1. **Vertical first** — this stack happily uses 8-16 vCPUs
   (`WEB_WORKERS`, `--scale worker=N`).
2. **Split the frontend** — it's static; serve it from any CDN or static host
   and point `localStorage dockbench.apiBase` (or a build-time edit) at
   the API box. ~90% of tool usage never reaches your server at all.
3. **Multi-host** — run Redis on one node, point several worker nodes'
   `REDIS_URL` at it, and put any load balancer in front of 2+ API
   containers. Everything is stateless, so this is configuration, not
   re-architecture.

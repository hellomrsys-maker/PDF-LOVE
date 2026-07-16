#!/usr/bin/env python3
"""
Dockbench load test — stdlib only, no external tooling required.

Usage:
    python3 scripts/loadtest.py https://tools.example.com/api [concurrency] [seconds]
    python3 scripts/loadtest.py http://localhost:8080/api 20 15

Hits /health and /capabilities at the given concurrency and, if the
deployment has a queue, runs one full /jobs/convert round trip to prove
the async path works under load. Prints p50/p95/p99 latency and error
rate per endpoint. Interpret with deploy/PRODUCTION.md's capacity notes.
"""

import asyncio
import io
import json
import statistics
import sys
import time
import urllib.request
import uuid


def _sync_get(url, timeout=10):
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read()
            return (time.perf_counter() - t0) * 1000, r.status
    except Exception:
        return (time.perf_counter() - t0) * 1000, 0


async def hammer(url, concurrency, seconds):
    results = []
    deadline = time.time() + seconds

    async def one():
        while time.time() < deadline:
            ms, status = await asyncio.to_thread(_sync_get, url)
            results.append((ms, status))

    await asyncio.gather(*[one() for _ in range(concurrency)])
    return results


def tiny_pdf() -> bytes:
    """A minimal valid one-page PDF, built by hand."""
    return (b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
            b"0000000052 00000 n \n0000000101 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n164\n%%EOF\n")


def multipart(fields, file_field, filename, data):
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()
    for k, v in fields.items():
        buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\n"
              f"Content-Type: application/pdf\r\n\r\n".encode())
    buf.write(data)
    buf.write(f"\r\n--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def job_round_trip(base):
    body, ctype = multipart({"target": "pptx"}, "file", "load.pdf", tiny_pdf())
    req = urllib.request.Request(base + "/jobs/convert", data=body,
                                 headers={"Content-Type": ctype}, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            job_id = json.load(r)["job_id"]
    except urllib.error.HTTPError as e:
        return None, f"queue unavailable (HTTP {e.code}) — sync-only deployment"
    for _ in range(120):
        time.sleep(1)
        with urllib.request.urlopen(f"{base}/jobs/{job_id}", timeout=10) as r:
            st = json.load(r)
        if st["status"] == "complete":
            with urllib.request.urlopen(f"{base}/jobs/{job_id}/result", timeout=30) as r:
                size = len(r.read())
            return (time.perf_counter() - t0), f"complete, result {size} bytes"
        if st["status"] == "failed":
            return (time.perf_counter() - t0), f"failed: {st.get('error','?')[:120]}"
    return None, "timed out"


def report(name, results):
    lat = sorted(ms for ms, _ in results)
    errors = sum(1 for _, status in results if status != 200)
    if not lat:
        print(f"  {name}: no samples")
        return
    q = lambda p: lat[min(len(lat) - 1, int(len(lat) * p))]
    print(f"  {name}: {len(lat)} reqs | p50 {q(0.50):.0f}ms  p95 {q(0.95):.0f}ms  "
          f"p99 {q(0.99):.0f}ms  max {lat[-1]:.0f}ms | errors {errors} "
          f"({errors / len(lat) * 100:.1f}%)")


async def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/api").rstrip("/")
    concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    seconds = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    print(f"Target {base} | concurrency {concurrency} | {seconds}s per endpoint\n")

    for path in ("/health", "/capabilities"):
        results = await hammer(base + path, concurrency, seconds)
        report(path, results)

    print("\nQueue round trip (one /jobs/convert pdf->pptx):")
    took, msg = job_round_trip(base)
    print(f"  {msg}" + (f" in {took:.1f}s" if took else ""))


if __name__ == "__main__":
    asyncio.run(main())

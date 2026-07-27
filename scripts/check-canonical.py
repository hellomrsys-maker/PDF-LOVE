#!/usr/bin/env python3
"""
Verify the canonical host actually exists.

Every page carries <link rel="canonical" href="https://HOST/...">, plus
og:url and a sitemap full of absolute URLs. If HOST does not resolve, that
markup tells Google the authoritative copy of every page lives at an
address nobody can reach — which is worse than shipping no canonical at
all, and it silently nullifies the whole SEO effort no matter how many
pages exist.

Nothing in the build catches this, because generating a canonical tag and
resolving its host are different things. This closes that gap.

    python scripts/check-canonical.py               # check what is in the files
    SITE_ORIGIN=https://x.workers.dev python scripts/check-canonical.py

Exits non-zero when the host does not resolve, so CI fails before a deploy
rather than after search engines have crawled it.
"""

import os
import re
import socket
import sys
import urllib.error
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")

CANONICAL = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.I)


def declared_origins():
    """Every distinct scheme://host used in a canonical tag on the site."""
    found = Counter()
    for dirpath, _dirs, files in os.walk(FRONTEND):
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            for url in CANONICAL.findall(text):
                m = re.match(r"(https?://[^/]+)", url)
                if m:
                    found[m.group(1)] += 1
    return found


def resolves(host):
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False


def responds(origin):
    """True if the origin answers an HTTP request at all."""
    req = urllib.request.Request(origin, method="HEAD",
                                 headers={"User-Agent": "dockbench-canonical-check"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code          # a 4xx still proves the host is serving
    except Exception:
        return None


def main():
    override = os.environ.get("SITE_ORIGIN")
    found = declared_origins()

    if override:
        origins = {override.rstrip("/"): sum(found.values())}
        print(f"checking SITE_ORIGIN={override}\n")
    elif found:
        origins = dict(found)
        print(f"found {len(origins)} canonical origin(s) across "
              f"{sum(found.values())} pages\n")
    else:
        print("No canonical tags found — nothing to check.")
        return 0

    failed = []
    for origin, count in sorted(origins.items(), key=lambda kv: -kv[1]):
        host = re.sub(r"^https?://", "", origin).split("/")[0].split(":")[0]
        dns = resolves(host)
        status = responds(origin) if dns else None
        mark = "OK  " if dns and status and status < 500 else "FAIL"
        detail = ("does not resolve (NXDOMAIN)" if not dns
                  else f"HTTP {status}" if status
                  else "resolves but does not answer")
        print(f"  {mark}  {origin:<44} {count:>4} page(s)   {detail}")
        if not dns:
            failed.append((origin, host))

    if failed:
        print("\nFAIL: canonical tags point at a host that does not exist.")
        for origin, host in failed:
            print(f"  {host} has no DNS record, so every canonical, og:url and")
            print(f"  sitemap entry naming {origin} is unreachable to a crawler.")
        print("\nFix by either registering/pointing the domain, or rebuilding")
        print("with the host the site is actually served from:")
        print("  SITE_ORIGIN=https://<real-host> python scripts/build-seo.py")
        return 1

    print("\nPASS: every canonical origin resolves and answers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

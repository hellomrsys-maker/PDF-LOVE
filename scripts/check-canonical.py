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
                                 headers={"User-Agent": "pdflove-canonical-check"})
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

    # Three distinct ways a canonical host can be wrong, and all three have
    # to reach the exit code. Until this domain existed only the NXDOMAIN
    # branch was ever taken, which hid a bug: a host that resolved but served
    # nothing printed FAIL in the table and still exited 0, under a closing
    # line that claimed every origin "resolves and answers".
    failed = []
    for origin, count in sorted(origins.items(), key=lambda kv: -kv[1]):
        host = re.sub(r"^https?://", "", origin).split("/")[0].split(":")[0]
        dns = resolves(host)
        status = responds(origin) if dns else None
        ok = bool(dns and status and status < 500)
        detail = ("does not resolve (NXDOMAIN)" if not dns
                  else f"HTTP {status}" if status
                  else "resolves but does not answer")
        print(f"  {'OK  ' if ok else 'FAIL'}  {origin:<44} {count:>4} page(s)   {detail}")
        if not ok:
            reason = ("no-dns" if not dns
                      else "server-error" if status
                      else "no-answer")
            failed.append((origin, host, reason, status))

    if failed:
        print("\nFAIL: canonical tags point at a host crawlers cannot use.")
        for origin, host, reason, status in failed:
            if reason == "no-dns":
                print(f"  {host} has no DNS record, so every canonical, og:url and")
                print(f"  sitemap entry naming {origin} is unreachable to a crawler.")
                print(f"  Fix: point the domain, or rebuild with the real host:")
                print(f"    SITE_ORIGIN=https://<real-host> python scripts/build-seo.py")
            elif reason == "server-error":
                print(f"  {host} resolves but returns HTTP {status}. DNS is done;")
                print(f"  the origin behind it is broken or nothing is deployed there.")
                print(f"  Fix: check the Worker is deployed and the Custom Domain is attached.")
            else:
                print(f"  {host} resolves but did not answer an HTTP request.")
                print(f"  Either nothing is serving it yet, or this machine cannot")
                print(f"  reach it (a sandboxed or firewalled network will look")
                print(f"  identical from here). Re-run from CI, which has real")
                print(f"  egress, before concluding the site is down.")
        return 1

    print("\nPASS: every canonical origin resolves and answers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

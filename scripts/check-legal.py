#!/usr/bin/env python3
"""
Refuse to ship legal pages that still contain placeholders.

    python scripts/check-legal.py

A privacy policy that says "[COMPANY LEGAL NAME]" is worse than none: app
stores and ad networks reject the listing, and any visitor who reads it
concludes — correctly — that nobody checked. This is the gate that stops
that reaching production, in the same spirit as check-canonical.py refusing
to let a dead canonical host go unnoticed.

Two kinds of problem are reported:

  * TO BE COMPLETED  — a generated page whose OPERATOR detail is unset in
                       scripts/build-legal.py
  * [BRACKETED]      — a hand-written page still carrying template text
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")
COMPANY = os.path.join(FRONTEND, "company")

# Pages outside frontend/company/ that carry the same kind of published
# commitment. This check originally walked only the company folder, which
# missed download.html — a page that promises SHA-256 checksums and states
# terms for the desktop and Android builds. A placeholder is exactly as
# visible there as it is in the privacy policy.
EXTRA_PAGES = [
    os.path.join(FRONTEND, "download.html"),
    os.path.join(FRONTEND, "index.html"),
]

# Legal pages must be complete. The rest of the company pages are marketing
# and are checked too, because a placeholder in the footer is just as visible.
REQUIRED_PAGES = [
    "legal.html", "privacy.html", "terms.html", "cookies.html",
    "grievance.html", "refund.html", "security.html",
]

# [BRACKETED] template text. Deliberately narrow so it cannot fire on ordinary
# prose, an array literal in a code sample, or a markdown-style link.
BRACKET = re.compile(r"\[([A-Z][A-Z0-9 _/@.\-]{2,})\]")


def main():
    problems = []
    checked = 0

    if not os.path.isdir(COMPANY):
        print(f"no company directory at {COMPANY}")
        return 1

    paths = [os.path.join(COMPANY, n) for n in sorted(os.listdir(COMPANY))
             if n.endswith(".html")]
    paths += [p for p in EXTRA_PAGES if os.path.isfile(p)]

    for path in paths:
        name = os.path.relpath(path, FRONTEND)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        checked += 1

        for m in re.finditer(r"\[TO BE COMPLETED: ([a-z_]+)\]", text):
            problems.append(
                f"{name}: operator detail '{m.group(1)}' is unset — "
                f"fill it in OPERATOR at the top of scripts/build-legal.py")

        for m in BRACKET.finditer(text):
            token = m.group(1)
            if token.startswith("TO BE COMPLETED"):
                continue          # already reported above, with better advice
            problems.append(f"{name}: placeholder [{token}] still present")

    for required in REQUIRED_PAGES:
        if not os.path.isfile(os.path.join(COMPANY, required)):
            problems.append(f"{required} is missing — run scripts/build-legal.py")

    print(f"\n  checked {checked} published page(s)\n")

    if problems:
        # Same placeholder repeats a lot; show each distinct one once.
        seen = []
        for p in problems:
            if p not in seen:
                seen.append(p)
        print(f"  {len(seen)} problem(s):")
        for p in seen:
            print("   - " + p)
        print("\n  These pages are not publishable. App stores and ad networks")
        print("  reject listings whose legal pages carry placeholder text.")
        return 1

    print("  Every legal page is complete. No placeholders remain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

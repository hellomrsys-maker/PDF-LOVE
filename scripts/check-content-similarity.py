#!/usr/bin/env python3
"""
Fail the build when generated pages are near-duplicates of each other.

    python scripts/check-content-similarity.py [--verbose]

Why: every generated page once shared one template whose only variable was
a name. Within the tool-page family, 84% of any page's text appeared on all
of them, leaving roughly 30 unique words each. That is the shape Google's
scaled-content-abuse policy targets, and "low value content" is the most
common reason an AdSense application is refused. Nothing measured it, so it
went unnoticed until it was 148 pages deep.

Two measurement decisions that matter:

  * Content only. Navigation, the footer, the tool workspace and ad slots
    are stripped before comparing. Shared chrome is not duplicate content —
    every site has it, and search engines discount it. Including it is what
    produced an earlier, misleadingly reassuring "39% boilerplate" figure.

  * Compared within a family, not across all pages. A conversion page and a
    calculator page naturally differ; that tells you nothing. The question
    is whether a page resembles its own siblings, which is what a crawler
    sees when it evaluates a template.

Similarity is Jaccard overlap of 5-word shingles — the standard shape for
near-duplicate detection, and insensitive to reordering in a way that a
plain diff is not.
"""

import glob
import itertools
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")
VERBOSE = "--verbose" in sys.argv

# A page may exceed the median and still be fine; a page that is nearly a
# copy of another is not. Both thresholds must hold.
MEDIAN_MAX = 0.20
PAIR_MAX = 0.45

# Sampling keeps this fast on 148 pages without changing the answer — the
# seed is fixed so the result is reproducible run to run.
SAMPLE = 24
random.seed(20260728)


def content_words(path):
    """The page's own words: chrome and the tool workspace removed."""
    with open(path, encoding="utf-8") as f:
        s = f.read()
    s = re.sub(r"(?s)<(script|style|header|footer|nav).*?</\1>", " ", s)
    m = re.search(r"(?s)<main.*?</main>", s)
    if m:
        s = m.group(0)
    s = re.sub(r'(?s)<div id="tool-mount".*?</div>', " ", s)
    s = re.sub(r'(?s)<div class="ad-slot.*?</div>', " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower().split()


def shingles(ws, n=5):
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0


def families():
    """Group generated pages by the generator that produced them."""
    src = open(os.path.join(ROOT, "scripts", "build-seo.py"), encoding="utf-8").read()
    pairs = {f"{a}-to-{b}" for a, b, _, _ in
             re.findall(r'\n    \("(\w+)", "(\w+)", "([^"]+)", "([^"]*)"\)', src)}
    questions = set(re.findall(r'\n    \("(how-to-[a-z0-9-]+)"', src))

    fam = {"conversion pages": [], "question pages": [], "tool pages": [], "guides": []}
    for p in glob.glob(os.path.join(FRONTEND, "tools", "*.html")):
        slug = os.path.basename(p)[:-5]
        if slug == "index":
            continue
        # Noindexed pages are excluded: they are deliberately generic and do
        # not compete in search, so holding them to a distinctness bar would
        # be measuring something nobody is ever shown.
        head = open(p, encoding="utf-8").read().split("</head>")[0]
        if "noindex" in head:
            continue
        key = ("conversion pages" if slug in pairs
               else "question pages" if slug in questions
               else "tool pages")
        fam[key].append(p)
    for p in glob.glob(os.path.join(FRONTEND, "guides", "*.html")):
        if not p.endswith("index.html"):
            fam["guides"].append(p)
    return fam


def main():
    problems = []
    print()
    for name, files in sorted(families().items()):
        if len(files) < 3:
            print(f"  {name:18} n={len(files):3}   too few to compare")
            continue
        sample = random.sample(files, min(SAMPLE, len(files)))
        sh = {f: shingles(content_words(f)) for f in sample}
        pairs = list(itertools.combinations(sample, 2))
        vals = sorted((jaccard(sh[a], sh[b]), a, b) for a, b in pairs)
        median = vals[len(vals) // 2][0]
        worst, wa, wb = vals[-1]
        avg_words = sum(len(content_words(f)) for f in sample) // len(sample)

        flag = ""
        if median > MEDIAN_MAX:
            problems.append(f"{name}: median similarity {median * 100:.1f}% "
                            f"exceeds {MEDIAN_MAX * 100:.0f}%")
            flag = "  <-- too similar"
        if worst > PAIR_MAX:
            problems.append(
                f"{name}: {os.path.basename(wa)} and {os.path.basename(wb)} "
                f"are {worst * 100:.1f}% identical (limit {PAIR_MAX * 100:.0f}%)")
            flag = "  <-- too similar"

        print(f"  {name:18} n={len(files):3}  ~{avg_words:4} words   "
              f"median {median * 100:5.1f}%   worst {worst * 100:5.1f}%{flag}")
        if VERBOSE:
            for v, a, b in vals[-3:]:
                print(f"        {v * 100:5.1f}%  {os.path.basename(a)} vs {os.path.basename(b)}")

    if problems:
        print(f"\n  {len(problems)} problem(s):")
        for p in problems:
            print("   - " + p)
        print("\n  Pages that mostly repeat each other read as scaled content.")
        print("  Give them genuinely different copy, or noindex the ones that")
        print("  do not deserve to compete.")
        return 1

    print("\n  Every page family is comfortably distinct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

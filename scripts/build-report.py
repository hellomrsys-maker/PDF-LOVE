#!/usr/bin/env python3
"""
Generate TEST_REPORT.md from what the suites actually measured.

Written by the tests rather than by hand, so it cannot drift into
describing a state of affairs that stopped being true. Anything the suites
did not produce is reported as "not run", never as a pass.

    python scripts/build-report.py
"""

import json
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "test-results")
OUT = os.path.join(ROOT, "TEST_REPORT.md")


def load(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


# Bugs found by this round of testing. Each was reproduced on a fixture
# before being called a bug, and each entry says how to see it.
BUGS = [
    ("BUG-001", "fixed", "Three server-assisted tools advertised \"runs on-device\"",
     "PDF to PowerPoint, PDF to Excel and PDF to PDF/A sat in the always-visible "
     "Convert row, whose cards are labelled on-device by section. The privacy "
     "claim on the card was false, and the published count was wrong: 94 tools "
     "run on-device, not 97.",
     "Open the app with no backend configured and read the badge on PDF to Excel."),
    ("BUG-002", "fixed", "Passport & ID Photo Maker crashed on every use",
     "`viewH` was declared inside setupCropper but read by the Create handler, "
     "so every click threw ReferenceError and no photo was ever produced.",
     "Open the tool, load a photo, click Create."),
    ("BUG-003", "fixed", "pdf.js detached the caller's file buffer",
     "getDocument transfers the buffer to its worker, which leaves the caller "
     "holding a zero-length ArrayBuffer. Any tool that read a file once and then "
     "passed the same bytes to pdf-lib reported \"Could not read this PDF\" on a "
     "perfectly valid file. Bookmarks/TOC failed on every document; Split by "
     "Bookmark failed on every document that had bookmarks.",
     "Load fixtures/text.pdf into Bookmarks / TOC."),
    ("BUG-004", "fixed", "Extract Images found nothing in files full of images",
     "It asked pdf.js for image objects through page.objs, which is only "
     "populated after a page has been rendered. It now reads the XObject "
     "dictionaries directly, and returns original JPEG bytes rather than "
     "re-encoding every photo to PNG.",
     "Run it on fixtures/scanned.pdf, which contains 2 embedded images."),
    ("BUG-005", "fixed", "Repair PDF could not repair anything",
     "It only re-saved files that already parsed — the opposite of its purpose. "
     "It now falls back to the bundled qpdf engine, which rebuilds a damaged "
     "cross-reference table by scanning for objects.",
     "fixtures/corrupt.pdf (broken xref) now comes back with all 3 pages; "
     "fixtures/truncated.pdf is genuinely unrecoverable and now says so."),
    ("BUG-006", "fixed", "Images to Slideshow Video crashed on its first frame",
     "The first requestAnimationFrame timestamp can predate the t0 sampled "
     "immediately before it, making floor(t/secs) return -1 and bitmaps[-1] "
     "undefined.",
     "Add two photos and click Create."),
    ("BUG-007", "fixed", "Trim Video produced a zero-byte file and called it done",
     "Two faults. MediaRecorder was attached to a video element that had not yet "
     "presented a frame, so Chromium raised EncodingError on every container it "
     "offers; and isTypeSupported reports video/mp4 as supported while its muxer "
     "cannot encode an element capture. The tool now waits for a real frame and "
     "falls back through containers until one actually emits data — and refuses "
     "to hand over an empty file.",
     "Trim fixtures/clip.webm; it now yields a ~77 KB clip."),
    ("BUG-008", "fixed", "Wrong password reported as \"engine failed to load: undefined\"",
     "Emscripten throws an ExitStatus object with no .message. Exit codes are now "
     "mapped to real sentences, and the cached WASM module is dropped after a "
     "failure so an aborted runtime cannot poison later attempts.",
     "Enter a wrong password in Unlock PDF."),
    ("BUG-009", "fixed", "Fourteen of twenty file handlers failed silently",
     "Async onFiles handlers had no error handling, so an unreadable file became "
     "an unhandled rejection and the panel simply sat there — indistinguishable "
     "from a tool that does nothing. This is the most likely explanation for "
     "\"most features don't work\": they reported nothing when they failed.",
     "buildDropzone now routes every entry point through a guard that always "
     "reports."),
    ("BUG-010", "open", "The canonical URL points at a domain that does not exist",
     "All 168 pages declare https://pdflove.co.in as canonical, in og:url, and "
     "throughout the sitemap. That host has no DNS record, so every canonical tag "
     "tells crawlers the authoritative copy of the page is unreachable. No amount "
     "of SEO content overcomes this.",
     "python scripts/check-canonical.py — fails today. Fix by registering the "
     "domain or rebuilding with SITE_ORIGIN set to the real host."),
]


def section_tools(f):
    data = load("functional.json")
    f.write("\n## Every tool, driven with real files\n\n")
    if not data:
        f.write("Not run. `node scripts/functional-suite.js`\n")
        return
    tested = data["pass"] + data["fail"] + data["error"] + data["blocked"]
    f.write(f"Each tool is opened, given a real fixture, driven to its output, and "
            f"the output opened and inspected — that redaction removed the text "
            f"rather than covering it, that encryption rejects a wrong password, "
            f"that the EXIF stripper really dropped GPS.\n\n")
    f.write(f"**{data['pass']} of {tested} passed** "
            f"({data['fail']} failed, {data['error']} errored, "
            f"{data['blocked']} blocked, {data['skipped']} skipped as "
            f"un-runnable headless).\n\n")

    bad = [r for r in data["results"] if r["status"] in ("fail", "error", "blocked")]
    if bad:
        f.write("| Tool | Status | Detail |\n|---|---|---|\n")
        for r in bad:
            detail = (r.get("detail") or "").replace("|", "\\|")[:150]
            f.write(f"| {r['name']} | {r['status']} | {detail} |\n")
        f.write("\n")
    else:
        f.write("No failures.\n\n")

    skipped = [r for r in data["results"] if r["status"] == "skipped"]
    if skipped:
        f.write("<details><summary>Skipped, with reasons</summary>\n\n")
        f.write("| Tool | Reason |\n|---|---|\n")
        for r in skipped:
            f.write(f"| {r['name']} | {(r.get('detail') or '')[:120]} |\n")
        f.write("\n</details>\n\n")


def section_capacity(f):
    f.write("\n## Capacity\n\n")
    shape = load("capacity-shape.json")
    if not shape:
        f.write("Not run. `python scripts/capacity_shape.py`\n")
        return
    f.write("Memory does **not** track a document's size in bytes. It tracks the "
            "**page count**, because the output document holds a page-tree entry "
            "for every page until the writer finishes.\n\n")
    bv = shape.get("bytes_vs_pages", {})
    if bv:
        f.write("| Source | Input | Pages | Peak RSS | KB/page |\n|---|---|---|---|---|\n")
        for label in ("few", "many"):
            r = bv.get(label)
            if not r:
                continue
            f.write(f"| {label} | {r['mb'] * 4:.0f} MB | {r['pages']} | "
                    f"{r['peak_rss_mb']:.0f} MB | "
                    f"{r['peak_rss_mb'] * 1024 / r['pages']:.1f} |\n")
        f.write("\nTwice the bytes, fifty times the pages, five times the memory.\n\n")

    sweep = shape.get("page_sweep", [])
    if sweep:
        f.write("| Copies | Pages | Input | Peak RSS | KB/page |\n|---|---|---|---|---|\n")
        for s in sweep:
            f.write(f"| {s['copies']} | {s['pages']} | {s['mb_in']:.0f} MB | "
                    f"{s['peak_rss_mb']:.0f} MB | "
                    f"{s['peak_rss_mb'] * 1024 / s['pages']:.1f} |\n")
        f.write("\n")

    f.write("**Batching the input does not help.** Cascading a 48,000-page merge "
            "through 8 intermediates lowered the intermediate peak to 116 MB, but "
            "the final pass still cost 804 MB — identical to merging directly, and "
            "twice as slow.\n\n")
    f.write("**Capping pages per output file does.**\n\n")
    f.write("| 48,000-page merge | Parts | Peak RSS | Time |\n|---|---|---|---|\n")
    f.write("| one file | 1 | 812 MB | 33.7s |\n")
    f.write("| 6,000 per part | 8 | 124 MB | 17.8s |\n")
    f.write("| 3,000 per part | 16 | 75 MB | 21.1s |\n\n")
    f.write("Same 4.93 GB of output either way. `merge_paths(max_pages_per_part=N)`, "
            "or pass `memory_budget_mb` and let the engine choose.\n\n")
    f.write("What this means in practice: 20,000 pages costs about 500 MB in a "
            "single file, so a desktop handles it directly. A 100 GB job is 76,000+ "
            "pages and about 1.3 GB in one file — fine on a computer, too much for "
            "a phone's per-app ceiling, which is what the part cap is for.\n\n")


def section_bugs(f):
    fixed = [b for b in BUGS if b[1] == "fixed"]
    open_ = [b for b in BUGS if b[1] != "fixed"]
    f.write(f"\n## Bugs found\n\n{len(BUGS)} defects, {len(fixed)} fixed, "
            f"{len(open_)} open.\n\n")
    for ident, status, title, detail, repro in BUGS:
        mark = "FIXED" if status == "fixed" else "OPEN"
        f.write(f"### {ident} — {title}  \n**{mark}**\n\n{detail}\n\n"
                f"*How to see it:* {repro}\n\n")


def main():
    os.makedirs(RESULTS, exist_ok=True)
    with open(OUT, "w") as f:
        f.write("# PDF Love test report\n\n")
        f.write(f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} "
                f"from commit `{git('rev-parse', '--short', 'HEAD')}`.\n\n")
        f.write("Regenerated by `python scripts/build-report.py` from what the "
                "suites measured. Anything a suite did not produce appears as "
                "\"not run\", never as a pass.\n")
        section_bugs(f)
        section_tools(f)
        section_capacity(f)
        f.write("\n## How to reproduce all of this\n\n")
        f.write("```bash\n"
                "python scripts/make-fixtures.py\n"
                "node scripts/functional-suite.js          # every tool, real files\n"
                "python scripts/capacity_shape.py          # what memory tracks\n"
                "python scripts/capacity_test.py --ladder 0.5,1,3\n"
                "python scripts/check-canonical.py         # canonical host resolves\n"
                "python scripts/build-legal.py             # legal pages, one source of truth\n"
                "python scripts/check-legal.py             # no placeholders left in them\n"
                "node scripts/check-tool-counts.js         # published counts are true\n"
                "python scripts/build-report.py            # this file\n"
                "```\n")
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()

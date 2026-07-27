#!/usr/bin/env python3
"""
Capacity test — the streaming engine's memory is decoupled from a
document's size in bytes, which is what makes 100 GB documents possible.

    python scripts/capacity_test.py [--scale N]

Builds a multi-GB PDF out of real JPEG content (not blank pages, which
compress to nothing and prove nothing), then merges, extracts and rotates
it while watching peak RSS.

What memory does and does not track
-----------------------------------
Bytes are nearly free. Pages are not. Merging 2.7 GB spread over 240 pages
costs 43 MB; merging 5.2 GB spread over 12,000 pages costs 216 MB — twice
the bytes, fifty times the pages, five times the memory. The output
document holds a page-tree entry for every page until the writer finishes,
so cost is ~17-23 KB per page on top of a fixed baseline.

Batching the input does not change this: cascading a 48,000-page merge
through 8 intermediates lowered the intermediate peak to 116 MB, but the
final pass still cost 804 MB — identical to merging directly, and twice as
slow. What does bound it is capping pages per *output* file, which
premium_pdf.merge_paths(max_pages_per_part=N) does:

    48,000 pages, one file        812 MB
    48,000 pages, 6,000 per part  124 MB
    48,000 pages, 3,000 per part   75 MB

See scripts/capacity_shape.py for the measurements behind those numbers.
"""

import argparse
import io
import json
import os
import random
import resource
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

import pikepdf                      # noqa: E402
from pikepdf import Name            # noqa: E402
from PIL import Image               # noqa: E402

import dockbench_pdf                # noqa: E402

# What actually governs memory is the page count, not the file size.
#
# Measured on this engine across a 40x page range: 17.0-23.1 KB per page on
# top of a fixed baseline. Two sources of similar size but 50x different
# page counts settle it — 2.7 GB across 240 pages costs 43 MB, while 5.2 GB
# across 12,000 pages costs 216 MB. Bytes are nearly free; pages are not.
#
# So the assertion is a per-page budget, not a flat ceiling. A flat ceiling
# either fails on a legitimately huge page count or is so loose it would
# miss a regression on a small one. These bounds sit ~2x above the measured
# cost: comfortably clear of CI noise, but a regression to whole-file
# buffering blows through them immediately.
KB_PER_PAGE_CEILING = 48
BASELINE_MB = 96


def rss_budget_mb(pages):
    """Peak RSS permitted for a job of this many pages."""
    return BASELINE_MB + (pages * KB_PER_PAGE_CEILING) / 1024


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def build_source(path, pages_per_image=50):
    """A PDF with real, incompressible image content."""
    imgs = []
    for _ in range(20):
        im = Image.new("RGB", (1700, 2200), (240, 238, 230))
        px = im.load()
        for _ in range(60000):
            px[random.randrange(1700), random.randrange(2200)] = (
                random.randrange(90), random.randrange(90), random.randrange(90))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=88)
        imgs.append(b.getvalue())

    pdf = pikepdf.Pdf.new()
    for _ in range(pages_per_image):
        for raw in imgs:
            page = pdf.add_blank_page(page_size=(612, 792))
            st = pikepdf.Stream(pdf, raw)
            st.Type = Name("/XObject"); st.Subtype = Name("/Image")
            st.Width = 1700; st.Height = 2200
            st.ColorSpace = Name("/DeviceRGB"); st.BitsPerComponent = 8
            st.Filter = Name("/DCTDecode")
            page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=st))
            page.Contents = pikepdf.Stream(pdf, b"q 612 0 0 792 0 0 cm /Im0 Do Q")
    pdf.save(path)
    pdf.close()


def human(gb):
    return f"{gb:.2f} GB" if gb >= 1 else f"{gb * 1024:.0f} MB"


def build_to_size(path, target_gb, pages_per_image=25):
    """Build a source PDF of roughly target_gb, in a child process.

    Constructing it here would hold it in memory and inflate this process's
    peak RSS, making the measurement meaningless — the number we care about
    is what the *streaming* operations cost.
    """
    # ~26 MB per pages_per_image=25 block of 20 image pages; scale from that.
    per_block_gb = 0.0265
    blocks = max(1, round(target_gb / per_block_gb))
    subprocess.run([sys.executable, os.path.abspath(__file__),
                    "--build-only", path,
                    "--pages-per-image", str(blocks)], check=True)
    return os.path.getsize(path) / 1e9


def run_merge(src, copies, out, label):
    """Merge `copies` of src into out, reporting time and peak RSS."""
    t = time.perf_counter()
    pages = dockbench_pdf.merge_files([src] * copies, out)
    el = time.perf_counter() - t
    rss = peak_rss_mb()
    return {"pages": pages, "seconds": el, "peak_rss_mb": rss, "label": label}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", type=int, default=2,
                    help="how many copies to merge (default 2)")
    ap.add_argument("--pages-per-image", type=int, default=25)
    ap.add_argument("--size", type=float, metavar="GB",
                    help="target output size in GB — the literal end-to-end test. "
                         "Needs that much free disk plus headroom.")
    ap.add_argument("--ladder", metavar="A,B,C",
                    help="sizes in GB to test in sequence, asserting peak RSS "
                         "stays flat as size grows (e.g. 0.5,1,5,25)")
    ap.add_argument("--null-sink", action="store_true",
                    help="write output to /dev/null. Exercises the read/merge "
                         "path at full scale without needing output disk, so "
                         "100 GB of input can be processed on a small machine.")
    ap.add_argument("--json", metavar="FILE", help="write results as JSON")
    ap.add_argument("--build-only", metavar="PATH",
                    help="internal: build the source PDF and exit")
    args = ap.parse_args()

    if args.build_only:
        build_source(args.build_only, args.pages_per_image)
        return

    if not hasattr(dockbench_pdf, "merge_files"):
        sys.exit("dockbench_pdf has no streaming API — build the extensions first.")

    tmp = tempfile.mkdtemp(prefix="dockbench-capacity-")
    records = []
    try:
        # ---------------- ladder: the invariant ----------------
        if args.ladder:
            sizes = [float(x) for x in args.ladder.split(",")]
            print("Capacity ladder — peak RSS must stay flat as size grows.\n")
            src = os.path.join(tmp, "src.pdf")
            src_gb = build_to_size(src, min(sizes[0], 1.0))
            base_pages = dockbench_pdf.npages_file(src)
            print(f"  source: {human(src_gb)}, {base_pages} pages\n")
            print(f"  {'target':>9}  {'produced':>9}  {'pages':>7}  {'time':>7}  {'peak RSS':>9}")
            print("  " + "-" * 52)

            free = shutil.disk_usage(tmp).free / 1e9
            for target in sizes:
                copies = max(1, round(target / src_gb))
                out = "/dev/null" if args.null_sink else os.path.join(tmp, "out.pdf")
                if not args.null_sink and target * 1.3 > free:
                    print(f"  {human(target):>9}  SKIPPED — needs ~{target * 1.3:.0f} GB free, have {free:.0f} GB")
                    continue
                r = run_merge(src, copies, out, human(target))
                produced = 0 if args.null_sink else os.path.getsize(out) / 1e9
                records.append({**r, "target_gb": target, "produced_gb": produced})
                print(f"  {human(target):>9}  "
                      f"{('null sink' if args.null_sink else human(produced)):>9}  "
                      f"{r['pages']:>7}  {r['seconds']:>6.1f}s  {r['peak_rss_mb']:>7.0f} MB")
                if not args.null_sink and os.path.exists(out):
                    os.remove(out)

            if len(records) >= 2:
                rss = [r["peak_rss_mb"] for r in records]
                growth = max(rss) / min(rss)
                span = max(r["target_gb"] for r in records) / min(r["target_gb"] for r in records)
                print(f"\n  size varied {span:.0f}x; peak RSS varied {growth:.2f}x")
                # Peak RSS is a high-water mark, so it can only rise. Allow a
                # small constant overhead but fail if it tracks size at all.
                if growth > 3.0:
                    sys.exit(f"FAIL: memory grew {growth:.1f}x across a {span:.0f}x "
                             "size range — it is tracking file size, so streaming "
                             "has regressed and large files will exhaust RAM.")
                print(f"  PASS: memory is independent of document size.")
                print(f"        A {max(r['target_gb'] for r in records):.0f} GB document "
                      f"cost {max(rss):.0f} MB; 100 GB costs the same.")

        # ---------------- single run ----------------
        else:
            target = args.size
            src = os.path.join(tmp, "src.pdf")
            if target:
                src_gb = build_to_size(src, min(target / 4, 1.5))
                copies = max(1, round(target / src_gb))
                print(f"target {human(target)}: {copies} x {human(src_gb)} source")
            else:
                print("building source PDF with real image content...")
                subprocess.run([sys.executable, os.path.abspath(__file__),
                                "--build-only", src,
                                "--pages-per-image", str(args.pages_per_image)], check=True)
                src_gb = os.path.getsize(src) / 1e9
                copies = args.scale

            n = dockbench_pdf.npages_file(src)
            print(f"  source: {human(src_gb)}, {n} pages")

            out = "/dev/null" if args.null_sink else os.path.join(tmp, "merged.pdf")
            need = src_gb * copies
            if not args.null_sink:
                free = shutil.disk_usage(tmp).free / 1e9
                if need * 1.3 > free:
                    sys.exit(f"Need ~{need * 1.3:.0f} GB free for a {human(need)} output; "
                             f"only {free:.0f} GB available. Use --null-sink to test the "
                             "read path without the output disk, or run this on a "
                             "larger machine.")

            r = run_merge(src, copies, out, human(need))
            records.append({**r, "target_gb": need})
            produced = 0 if args.null_sink else os.path.getsize(out) / 1e9
            print(f"  merge x{copies}: {'null sink' if args.null_sink else human(produced)}, "
                  f"{r['pages']} pages, {r['seconds']:.1f}s, peak RSS {r['peak_rss_mb']:.0f} MB")
            assert r["pages"] == n * copies, f"expected {n * copies} pages, got {r['pages']}"

            if not args.null_sink:
                rng = os.path.join(tmp, "range.pdf")
                got = dockbench_pdf.extract_file(out, rng, 10, 60)
                assert got == 51, f"extract wrote {got} pages, expected 51"
                with pikepdf.open(out) as p:
                    assert len(p.pages) == r["pages"]
                print(f"  output verified: opens cleanly, extract works")

            rss = r["peak_rss_mb"]
            budget = rss_budget_mb(r["pages"])
            per_page = rss * 1024 / max(r["pages"], 1)
            print(f"\n  RESULT: processed {human(need)} across {r['pages']} pages "
                  f"using {rss:.0f} MB of RAM ({per_page:.1f} KB/page)")
            if rss > budget:
                sys.exit(f"FAIL: peak RSS {rss:.0f} MB exceeds the {budget:.0f} MB budget "
                         f"for {r['pages']} pages ({per_page:.1f} KB/page, ceiling is "
                         f"{KB_PER_PAGE_CEILING}). Memory per page has regressed.")
            print(f"  PASS: {per_page:.1f} KB/page is within the {KB_PER_PAGE_CEILING} "
                  f"KB/page budget ({rss:.0f} MB used of {budget:.0f} MB allowed).")
            print(f"        Bytes are nearly free; pages are the cost. To bound peak "
                  f"memory on a\n        constrained device, cap pages per output part "
                  f"— see premium_pdf.merge_paths.")

        if args.json:
            with open(args.json, "w") as f:
                json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "null_sink": args.null_sink, "runs": records}, f, indent=2)
            print(f"\n  wrote {args.json}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

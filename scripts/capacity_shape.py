#!/usr/bin/env python3
"""
Isolate *what* streaming memory scales with.

The 100 GB run peaked at 1288 MB while the 0.5/1/3 GB ladder peaked at
37/43/68 MB. Both cannot be explained by "memory is independent of document
size" — so this measures the two candidate drivers separately:

    bytes      — two sources of near-identical size, one with 50 pages and
                 one with 3000, merged the same number of times
    page count — the same source merged with a rising number of copies

Run each measurement in a fresh child process, because peak RSS is a
high-water mark and a single process would carry the largest run's peak
into every later reading.

    python scripts/capacity_shape.py            # build + measure
    python scripts/capacity_shape.py --json out.json
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


def jpeg(w, h, speckles):
    from PIL import Image
    im = Image.new("RGB", (w, h), (240, 238, 230))
    px = im.load()
    for _ in range(speckles):
        px[random.randrange(w), random.randrange(h)] = (
            random.randrange(90), random.randrange(90), random.randrange(90))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=88)
    return b.getvalue(), w, h


def build(path, pages, img_w, img_h, speckles, pool=8):
    """A PDF of `pages` pages, each carrying a real JPEG of the given size."""
    import pikepdf
    from pikepdf import Name
    imgs = [jpeg(img_w, img_h, speckles) for _ in range(pool)]
    pdf = pikepdf.Pdf.new()
    for i in range(pages):
        raw, w, h = imgs[i % pool]
        page = pdf.add_blank_page(page_size=(612, 792))
        st = pikepdf.Stream(pdf, raw)
        st.Type = Name("/XObject"); st.Subtype = Name("/Image")
        st.Width = w; st.Height = h
        st.ColorSpace = Name("/DeviceRGB"); st.BitsPerComponent = 8
        st.Filter = Name("/DCTDecode")
        page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=st))
        page.Contents = pikepdf.Stream(pdf, b"q 612 0 0 792 0 0 cm /Im0 Do Q")
    pdf.save(path)
    pdf.close()


def measure(src, copies):
    """Merge `copies` of src to a null sink; report pages, seconds, peak RSS."""
    import dockbench_pdf
    t = time.perf_counter()
    pages = dockbench_pdf.merge_files([src] * copies, "/dev/null")
    el = time.perf_counter() - t
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(json.dumps({"pages": pages, "seconds": el, "peak_rss_mb": rss}))


def child_measure(src, copies):
    r = subprocess.run([sys.executable, os.path.abspath(__file__),
                        "--measure", src, str(copies)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"measure failed: {r.stderr[-400:]}")
    return json.loads(r.stdout.strip().split("\n")[-1])


def child_build(path, pages, w, h, speckles):
    subprocess.run([sys.executable, os.path.abspath(__file__),
                    "--build", path, str(pages), str(w), str(h), str(speckles)],
                   check=True)
    return os.path.getsize(path) / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", nargs=5, metavar=("PATH", "PAGES", "W", "H", "SPECKLES"))
    ap.add_argument("--measure", nargs=2, metavar=("SRC", "COPIES"))
    ap.add_argument("--json", metavar="FILE")
    args = ap.parse_args()

    if args.build:
        p, pages, w, h, sp = args.build
        build(p, int(pages), int(w), int(h), int(sp))
        return
    if args.measure:
        measure(args.measure[0], int(args.measure[1]))
        return

    tmp = tempfile.mkdtemp(prefix="pdflove-shape-")
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        # --- A: same bytes, very different page counts -------------------
        few = os.path.join(tmp, "few.pdf")
        many = os.path.join(tmp, "many.pdf")
        print("building two sources of similar size but 50x different page counts...")
        few_mb = child_build(few, 60, 4000, 5200, 900_000)
        many_mb = child_build(many, 3000, 800, 1040, 30_000)
        print(f"  few  : {few_mb:6.0f} MB, 60 pages")
        print(f"  many : {many_mb:6.0f} MB, 3000 pages\n")

        a_few = child_measure(few, 4)
        a_many = child_measure(many, 4)
        out["bytes_vs_pages"] = {
            "few": {"mb": few_mb, **a_few},
            "many": {"mb": many_mb, **a_many},
        }
        print(f"  {'source':>8}  {'MB in':>7}  {'pages out':>10}  {'peak RSS':>9}  {'KB/page':>8}")
        print("  " + "-" * 52)
        for label, mb, r in (("few", few_mb, a_few), ("many", many_mb, a_many)):
            print(f"  {label:>8}  {mb * 4:>7.0f}  {r['pages']:>10}  "
                  f"{r['peak_rss_mb']:>7.0f} MB  {r['peak_rss_mb'] * 1024 / r['pages']:>8.1f}")

        # --- B: page count held as the only variable ----------------------
        print("\n  page-count sweep on the many-page source:")
        print(f"  {'copies':>7}  {'pages':>8}  {'bytes in':>9}  {'peak RSS':>9}  {'KB/page':>8}")
        print("  " + "-" * 52)
        sweep = []
        for copies in (1, 4, 16, 40):
            r = child_measure(many, copies)
            sweep.append({"copies": copies, "mb_in": many_mb * copies, **r})
            print(f"  {copies:>7}  {r['pages']:>8}  {many_mb * copies:>7.0f} MB  "
                  f"{r['peak_rss_mb']:>7.0f} MB  {r['peak_rss_mb'] * 1024 / r['pages']:>8.1f}")
        out["page_sweep"] = sweep

        per_page = [s["peak_rss_mb"] * 1024 / s["pages"] for s in sweep]
        print(f"\n  KB per page across a {sweep[-1]['pages'] // sweep[0]['pages']}x page range: "
              f"{min(per_page):.1f}–{max(per_page):.1f}")
        print(f"  bytes-driven?  {a_few['peak_rss_mb']:.0f} MB for {few_mb * 4:.0f} MB in "
              f"vs {a_many['peak_rss_mb']:.0f} MB for {many_mb * 4:.0f} MB in")

        if args.json:
            with open(args.json, "w") as f:
                json.dump(out, f, indent=2)
            print(f"\n  wrote {args.json}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

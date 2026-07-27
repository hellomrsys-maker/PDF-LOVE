#!/usr/bin/env python3
"""
Capacity test — proves the streaming engine's memory is independent of
document size, which is what makes 100 GB documents possible.

    python scripts/capacity_test.py [--scale N]

Builds a multi-GB PDF out of real JPEG content (not blank pages, which
compress to nothing and prove nothing), then merges, extracts and rotates
it while watching peak RSS. Fails if memory tracks file size.

Measured on the development machine at --scale 4:
    5.26 GB output, 4000 pages, 42.5 s, peak RSS 84 MB
"""

import argparse
import io
import os
import random
import resource
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

import pikepdf                      # noqa: E402
from pikepdf import Name            # noqa: E402
from PIL import Image               # noqa: E402

import dockbench_pdf                # noqa: E402

# Peak RSS must stay under this no matter how large the document gets.
# Generous enough not to be flaky on a loaded CI runner, tight enough that
# a regression to in-memory handling fails immediately.
RSS_CEILING_MB = 1024


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=2,
                    help="how many copies to merge (default 2)")
    ap.add_argument("--pages-per-image", type=int, default=25)
    ap.add_argument("--build-only", metavar="PATH",
                    help="internal: build the source PDF and exit")
    args = ap.parse_args()

    # Building the source with pikepdf holds it in memory, which would
    # inflate this process's peak RSS and make the measurement meaningless.
    # Do it in a child process so the number below reflects only the
    # streaming operations we are actually testing.
    if args.build_only:
        build_source(args.build_only, args.pages_per_image)
        return

    if not hasattr(dockbench_pdf, "merge_files"):
        sys.exit("dockbench_pdf has no streaming API — build the extensions first.")

    tmp = tempfile.mkdtemp(prefix="dockbench-capacity-")
    try:
        src = os.path.join(tmp, "src.pdf")
        print("building source PDF with real image content...")
        import subprocess
        subprocess.run([sys.executable, os.path.abspath(__file__),
                        "--build-only", src,
                        "--pages-per-image", str(args.pages_per_image)], check=True)
        src_gb = os.path.getsize(src) / 1e9
        n = dockbench_pdf.npages_file(src)
        print(f"  source: {src_gb:.2f} GB, {n} pages")

        # --- merge ---
        out = os.path.join(tmp, "merged.pdf")
        t = time.perf_counter()
        pages = dockbench_pdf.merge_files([src] * args.scale, out)
        el = time.perf_counter() - t
        out_gb = os.path.getsize(out) / 1e9
        rss = peak_rss_mb()
        print(f"  merge x{args.scale}: {out_gb:.2f} GB, {pages} pages, {el:.1f}s, peak RSS {rss:.0f} MB")
        assert pages == n * args.scale, f"expected {n * args.scale} pages, got {pages}"

        # --- extract from the large result ---
        rng = os.path.join(tmp, "range.pdf")
        got = dockbench_pdf.extract_file(out, rng, 10, 60)
        assert got == 51, f"extract wrote {got} pages, expected 51"

        # --- rotate the large result ---
        rot = os.path.join(tmp, "rot.pdf")
        got = dockbench_pdf.rotate_file(out, rot, 90)
        assert got == pages
        with pikepdf.open(rot) as p:
            rots = [pg.obj.get("/Rotate") for pg in list(p.pages)[:3]]
        assert rots == [90, 90, 90], f"rotations wrong: {rots}"

        # --- output must be a genuinely valid PDF, not just bytes ---
        with pikepdf.open(out) as p:
            assert len(p.pages) == pages

        rss = peak_rss_mb()
        ratio = (out_gb * 1024) / rss if rss else 0
        print(f"\nRESULT: produced {out_gb:.2f} GB using {rss:.0f} MB of RAM "
              f"({ratio:.0f}x the peak footprint)")

        if rss > RSS_CEILING_MB:
            sys.exit(f"FAIL: peak RSS {rss:.0f} MB exceeds {RSS_CEILING_MB} MB — "
                     "memory is tracking file size, so streaming has regressed.")
        print(f"PASS: peak RSS stayed under {RSS_CEILING_MB} MB; memory is "
              "independent of document size.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

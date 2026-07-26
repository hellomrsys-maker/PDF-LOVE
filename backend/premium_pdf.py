"""
premium_pdf — page-level PDF operations (merge, split, rotate, watermark).

Two implementations, tried in order:

  1. dockbench_pdf — libqpdf linked straight into the interpreter. Measured
     ~6x faster than shelling out to the qpdf CLI for a 200-page split,
     because it does not fork+exec (and round-trip through the filesystem)
     once per page.
  2. pikepdf — the same qpdf engine behind a Python wrapper. Always present
     as a declared dependency, so the fallback is a slowdown, never a
     missing feature.

Nothing here requires network access.
"""

import io
import logging
import os
import tempfile
import zipfile
from typing import List, Tuple

import pikepdf

from errors import EngineError

logger = logging.getLogger("dockbench.pdf")

# The fused in-process engine (see native/pdfops.cpp).
try:
    import dockbench_pdf as _ext
    logger.info("Fused PDF engine loaded (dockbench_pdf)")
except ImportError:
    _ext = None


def pdf_backend() -> str:
    """Which implementation these functions will use. Surfaced through
    /capabilities so a deployment can be checked rather than assumed."""
    return "extension" if _ext is not None else "pikepdf"


def _open(data: bytes):
    """Open in-memory PDF bytes, turning a parse failure into a 422."""
    try:
        return pikepdf.open(io.BytesIO(data))
    except Exception as e:
        raise EngineError(422, f"Not a readable PDF: {e}")


def _npages(data: bytes) -> int:
    if _ext is not None:
        try:
            return _ext.npages(data)
        except ValueError as e:
            raise EngineError(422, f"Not a readable PDF: {e}")
    with _open(data) as pdf:
        return len(pdf.pages)


def run_merge_pdf(files: List[bytes]) -> Tuple[bytes, str]:
    """Merge PDFs held in memory. Returns (pdf_bytes, "application/pdf").

    The bytes-in/bytes-out variant, used by the batch endpoint and anywhere
    the uploads are already resident. `run_merge_pdf_files` is the
    path-based variant for inputs too large to hold in memory.
    """
    if not files:
        raise EngineError(422, "No PDFs provided for merge.")

    if _ext is not None:
        try:
            return _ext.merge(files), "application/pdf"
        except ValueError as e:
            raise EngineError(422, f"Merge failed: {e}")

    out = pikepdf.Pdf.new()
    try:
        for raw in files:
            with _open(raw) as src:
                out.pages.extend(src.pages)
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue(), "application/pdf"
    finally:
        out.close()


def run_merge_pdf_files(input_paths: List[str]) -> Tuple[str, str]:
    """Merge PDFs from disk. Returns (output_path, "application/pdf").

    Reads each input off disk rather than requiring every upload to be
    resident at once, so a merge of very large files stays bounded.
    """
    if not input_paths:
        raise EngineError(422, "No PDFs provided for merge.")

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="merged_")
    os.close(tmp_fd)

    try:
        out = pikepdf.Pdf.new()
        with out:
            for p in input_paths:
                with pikepdf.open(p) as src:
                    out.pages.extend(src.pages)
            out.save(tmp_path)
    except Exception as e:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise EngineError(422, f"Merge failed: {e}")

    return tmp_path, "application/pdf"


def _extract(data: bytes, first: int, last: int) -> bytes:
    """Pages first..last inclusive (1-based) as a standalone PDF."""
    if _ext is not None:
        try:
            return _ext.extract(data, first, last)
        except ValueError as e:
            raise EngineError(422, str(e))
    with _open(data) as src:
        dst = pikepdf.Pdf.new()
        with dst:
            for i in range(first - 1, last):
                dst.pages.append(src.pages[i])
            buf = io.BytesIO()
            dst.save(buf)
        return buf.getvalue()


def run_split_pdf(data: bytes) -> Tuple[bytes, str]:
    """Split a PDF into one file per page, returned as a .zip."""
    page_count = _npages(data)
    if page_count == 0:
        raise EngineError(422, "PDF has no pages.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(1, page_count + 1):
            zf.writestr(f"page_{i}.pdf", _extract(data, i, i))
    return buf.getvalue(), "application/zip"


def run_split_pdf_range(data: bytes, start_page: int, end_page: int) -> Tuple[bytes, str]:
    """Return pages start_page..end_page (inclusive) as a .zip."""
    if start_page < 1 or end_page < start_page:
        raise EngineError(422, "Invalid page range specified.")

    total = _npages(data)
    if end_page > total:
        raise EngineError(422, f"Requested end_page {end_page} exceeds total pages {total}.")

    payload = _extract(data, start_page, end_page)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"range_{start_page}_{end_page}.pdf", payload)
    return buf.getvalue(), "application/zip"


def run_rotate_pdf(data: bytes, angle: int = 0) -> Tuple[bytes, str]:
    """Rotate every page by `angle` degrees, relative to its current
    rotation. `angle` must be a multiple of 90."""
    if angle % 90 != 0:
        raise EngineError(422, "Angle must be a multiple of 90 degrees.")

    if _ext is not None:
        try:
            return _ext.rotate(data, angle), "application/pdf"
        except ValueError as e:
            raise EngineError(422, f"Not a readable PDF: {e}")

    with _open(data) as src:
        for page in src.pages:
            # /Rotate is optional and absent on most real-world pages, so
            # reading it as an attribute raises instead of defaulting to 0.
            current = int(page.obj.get("/Rotate", 0))
            page.obj["/Rotate"] = (current + angle) % 360
        out = io.BytesIO()
        src.save(out)
    return out.getvalue(), "application/pdf"


def run_watermark_pdf(data: bytes, watermark: bytes) -> Tuple[bytes, str]:
    """Stamp the first page of `watermark` over every page of `data`.

    Stays on pikepdf: add_overlay handles content-stream merging and
    resource-name collisions, which is the fiddly part of this operation.
    """
    with _open(data) as base, _open(watermark) as wm:
        if len(wm.pages) == 0:
            raise EngineError(422, "Watermark PDF has no pages.")
        wm_page = wm.pages[0]
        for page in base.pages:
            page.add_overlay(wm_page)
        out = io.BytesIO()
        base.save(out)
    return out.getvalue(), "application/pdf"

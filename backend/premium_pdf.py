import io
import os
import tempfile
import zipfile
from typing import List, Tuple
import subprocess, shutil

def _qpdf_available() -> bool:
    """Return True if the qpdf executable is found in PATH."""
    return shutil.which("qpdf") is not None

# Conditional import: prefer pikepdf, fallback to PyPDF2
try:
    import pikepdf
    _USE_PIKEPDF = True
except Exception:
    from PyPDF2 import PdfReader, PdfWriter
    _USE_PIKEPDF = False
from connectivity import is_online
from engines import EngineError

def _ensure_online():
    """Raise EngineError if offline for premium PDF features."""
    if not is_online():
        raise EngineError(503, "Online connectivity required for premium PDF features.")

def run_merge_pdf_files(input_paths: List[str]) -> Tuple[str, str]:
    """Merge PDFs located at the given file system paths using the qpdf CLI.
    Returns a tuple of (output_path, "application/pdf").
    This implementation streams PDFs from disk and avoids loading them into memory.
    """
    _ensure_online()
    if not input_paths:
        raise EngineError(422, "No PDFs provided for merge.")

    # Create a temporary output file
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="merged_")
    os.close(tmp_fd)

    # Build the qpdf command: qpdf --empty --pages file1.pdf file2.pdf ... -- output.pdf
    cmd = ["qpdf", "--empty", "--pages"] + input_paths + ["--", tmp_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise EngineError(500, f"qpdf merge failed: {result.stderr.strip()}")

    return tmp_path, "application/pdf"


def run_split_pdf(data: bytes) -> Tuple[bytes, str]:
    """Split a PDF into individual pages and zip them.
    Returns (zip_bytes, "application/zip").
    """
    _ensure_online()
    # Write PDF data to a temporary file to enable streaming processing
    in_fd, in_path = tempfile.mkstemp(suffix=".pdf", prefix="split_input_")
    os.close(in_fd)
    with open(in_path, "wb") as f:
        f.write(data)

    # Determine total number of pages
    if _qpdf_available():
        count_cmd = ["qpdf", "--show-npages", in_path]
        count_res = subprocess.run(count_cmd, capture_output=True, text=True)
        if count_res.returncode != 0:
            os.remove(in_path)
            raise EngineError(500, f"qpdf page count failed: {count_res.stderr.strip()}")
        try:
            page_count = int(count_res.stdout.strip())
        except ValueError:
            os.remove(in_path)
            raise EngineError(500, "Unable to parse page count from qpdf output")
    else:
        src_tmp = pikepdf.open(in_path)
        page_count = len(src_tmp.pages)
        src_tmp.close()

    # Extract each page to its own PDF file using qpdf or a pure‑Python fallback
    with tempfile.TemporaryDirectory(prefix="split_pages_") as tmp_dir:
        for i in range(1, page_count + 1):
            out_path = os.path.join(tmp_dir, f"page_{i}.pdf")
            if _qpdf_available():
                split_cmd = ["qpdf", in_path, "--pages", in_path, str(i), "--", out_path]
                split_res = subprocess.run(split_cmd, capture_output=True, text=True)
                if split_res.returncode != 0:
                    os.remove(in_path)
                    raise EngineError(500, f"qpdf split page {i} failed: {split_res.stderr.strip()}")
            else:
                src_page = pikepdf.open(in_path)
                dst = pikepdf.Pdf.new()
                dst.pages.append(src_page.pages[i - 1])
                dst.save(out_path)
                src_page.close()
                dst.close()
        # Zip all extracted page PDFs
        zip_path = os.path.join(tmp_dir, "pages.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for i in range(1, page_count + 1):
                page_file = os.path.join(tmp_dir, f"page_{i}.pdf")
                zipf.write(page_file, f"page_{i}.pdf")
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()
    # Cleanup temporary input file
    try:
        os.remove(in_path)
    except OSError:
        pass
    return zip_bytes, "application/zip"

def run_rotate_pdf(data: bytes, angle: int = 0) -> Tuple[bytes, str]:
    """Rotate all pages of a PDF by the given angle (in degrees).
    Angle must be a multiple of 90.
    """
    _ensure_online()
    if angle % 90 != 0:
        raise EngineError(422, "Angle must be a multiple of 90 degrees.")
    src = pikepdf.open(io.BytesIO(data))
    for page in src.pages:
        page.Rotate = (page.Rotate + angle) % 360
    out = io.BytesIO()
    src.save(out)
    src.close()
    return out.getvalue(), "application/pdf"

def run_watermark_pdf(data: bytes, watermark: bytes) -> Tuple[bytes, str]:
    """Apply a PDF watermark (as a PDF) onto each page of the input PDF.
    Returns (watermarked_pdf_bytes, "application/pdf").
    """
    _ensure_online()
    base = pikepdf.open(io.BytesIO(data))
    wm = pikepdf.open(io.BytesIO(watermark))
    if len(wm.pages) == 0:
        raise EngineError(422, "Watermark PDF has no pages.")
    wm_page = wm.pages[0]
    for page in base.pages:
        page.add_overlay(wm_page)
    out = io.BytesIO()
    base.save(out)
    base.close()
    wm.close()
    return out.getvalue(), "application/pdf"

def run_split_pdf_range(data: bytes, start_page: int, end_page: int) -> Tuple[bytes, str]:
    """Split a PDF and return only pages start_page‑end_page (inclusive) as a zip.
    Handles very large PDFs by streaming to temporary files and using qpdf if available.
    """
    _ensure_online()
    if start_page < 1 or end_page < start_page:
        raise EngineError(422, "Invalid page range specified.")

    # Write PDF data to a temporary file
    in_fd, in_path = tempfile.mkstemp(suffix=".pdf", prefix="split_range_input_")
    os.close(in_fd)
    with open(in_path, "wb") as f:
        f.write(data)

    # Determine total number of pages if needed for validation
    if _qpdf_available():
        count_cmd = ["qpdf", "--show-npages", in_path]
        count_res = subprocess.run(count_cmd, capture_output=True, text=True)
        if count_res.returncode != 0:
            os.remove(in_path)
            raise EngineError(500, f"qpdf page count failed: {count_res.stderr.strip()}")
        try:
            total_pages = int(count_res.stdout.strip())
        except ValueError:
            os.remove(in_path)
            raise EngineError(500, "Unable to parse page count from qpdf output")
    else:
        src_tmp = pikepdf.open(in_path)
        total_pages = len(src_tmp.pages)
        src_tmp.close()

    if end_page > total_pages:
        os.remove(in_path)
        raise EngineError(422, f"Requested end_page {end_page} exceeds total pages {total_pages}")

    # Extract the requested range
    with tempfile.TemporaryDirectory(prefix="split_range_pages_") as tmp_dir:
        out_path = os.path.join(tmp_dir, f"range_{start_page}_{end_page}.pdf")
        if _qpdf_available():
            # qpdf page spec can be "start-end"
            pages_spec = f"{start_page}-{end_page}"
            split_cmd = ["qpdf", in_path, "--pages", in_path, pages_spec, "--", out_path]
            split_res = subprocess.run(split_cmd, capture_output=True, text=True)
            if split_res.returncode != 0:
                os.remove(in_path)
                raise EngineError(500, f"qpdf split range failed: {split_res.stderr.strip()}")
        else:
            src = pikepdf.open(in_path)
            dst = pikepdf.Pdf.new()
            for i in range(start_page - 1, end_page):
                dst.pages.append(src.pages[i])
            dst.save(out_path)
            src.close()
            dst.close()

        # Zip the single PDF (still a zip for consistency)
        zip_path = os.path.join(tmp_dir, "range.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(out_path, os.path.basename(out_path))
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()
    # Cleanup
    try:
        os.remove(in_path)
    except OSError:
        pass
    return zip_bytes, "application/zip"

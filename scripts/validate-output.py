#!/usr/bin/env python3
"""
Check that a tool's output is actually correct, not merely present.

    python scripts/validate-output.py <checker> <file> [expected]

Called per-tool by scripts/functional-suite.js. Prints one line of JSON:
{"ok": bool, "detail": "..."}.

The distinction this file exists to enforce: "a download happened" is not a
passing test. Redaction that draws a black box over text still containing
the SSN is a security failure that looks like success. An EXIF stripper that
returns the original file looks identical to one that works. These checkers
open the output and look.
"""

import io
import json
import os
import re
import sys
import zipfile

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


def manifest():
    with open(os.path.join(FIXTURES, "manifest.json")) as f:
        return json.load(f)


def ok(detail=""):
    return {"ok": True, "detail": detail}


def bad(detail):
    return {"ok": False, "detail": detail}


# ------------------------------------------------------------- generic

def any_output(path, expected=None):
    size = os.path.getsize(path)
    return ok(f"{size} bytes") if size > 0 else bad("empty file")


def valid_pdf(path, expected=None):
    import pikepdf
    try:
        with pikepdf.open(path) as p:
            n = len(p.pages)
        return ok(f"valid PDF, {n} pages") if n else bad("PDF has no pages")
    except Exception as e:
        return bad(f"not a readable PDF: {e}")


def pdf_pages(path, expected=None):
    import pikepdf
    try:
        with pikepdf.open(path) as p:
            n = len(p.pages)
    except Exception as e:
        return bad(f"not a readable PDF: {e}")
    if expected is None:
        return ok(f"{n} pages")
    return ok(f"{n} pages") if n == int(expected) else bad(f"expected {expected} pages, got {n}")


def pdf_fewer_pages(path, expected=None):
    """N-up must actually reduce the page count."""
    import pikepdf
    with pikepdf.open(path) as p:
        n = len(p.pages)
    src = int(expected) if expected else 3
    return ok(f"{src} -> {n} pages") if n < src else bad(f"no reduction: still {n} pages")


def pdf_rotated(path, expected=None):
    import pikepdf
    want = int(expected or 90)
    with pikepdf.open(path) as p:
        rots = [int(pg.obj.get("/Rotate", 0)) for pg in p.pages]
    if not rots:
        return bad("no pages")
    if all(r % 360 == want % 360 for r in rots):
        return ok(f"all {len(rots)} pages at {want}deg")
    return bad(f"rotations are {rots}, expected every page at {want}")


def pdf_not_larger(path, expected=None):
    """Compression must never return something bigger than the input."""
    src = os.path.join(FIXTURES, "scanned.pdf")
    if not os.path.exists(src):
        return valid_pdf(path)
    before, after = os.path.getsize(src), os.path.getsize(path)
    v = valid_pdf(path)
    if not v["ok"]:
        return v
    pct = (1 - after / before) * 100
    if after <= before:
        return ok(f"{before} -> {after} bytes ({pct:.0f}% smaller)")
    return bad(f"output grew: {before} -> {after} bytes")


def pdf_encrypted(path, expected=None):
    """Must be genuinely encrypted and reject the wrong password."""
    import pikepdf
    try:
        pikepdf.open(path)
        return bad("opened with no password — not encrypted")
    except pikepdf.PasswordError:
        pass
    except Exception as e:
        return bad(f"unreadable: {e}")
    try:
        pikepdf.open(path, password="definitely-not-the-password")
        return bad("a wrong password was accepted")
    except pikepdf.PasswordError:
        return ok("encrypted; wrong password correctly rejected")
    except Exception as e:
        return bad(f"unexpected error with a wrong password: {e}")


def pdf_not_encrypted(path, expected=None):
    import pikepdf
    try:
        with pikepdf.open(path) as p:
            return ok(f"opens with no password, {len(p.pages)} pages")
    except pikepdf.PasswordError:
        return bad("still password-protected")
    except Exception as e:
        return bad(f"unreadable: {e}")


def no_form_fields(path, expected=None):
    """Flatten must remove the interactive fields, not just draw over them."""
    import pikepdf
    try:
        with pikepdf.open(path) as p:
            root = p.Root
            if "/AcroForm" not in root:
                return ok("AcroForm removed")
            fields = root.AcroForm.get("/Fields", [])
            n = len(fields)
            return ok("no fields remain") if n == 0 else bad(f"{n} form field(s) still interactive")
    except Exception as e:
        return bad(f"unreadable: {e}")


def ssn_removed(path, expected=None):
    """Redaction must remove the text, not cover it.

    Drawing a black rectangle over an SSN leaves the SSN in the content
    stream, where any text extractor finds it. That is the failure mode this
    checks for, and it is a real one — it has leaked real documents.
    """
    ssn = manifest()["secret_ssn"]
    try:
        import pdfminer.high_level
        text = pdfminer.high_level.extract_text(path)
    except ImportError:
        import pikepdf
        with pikepdf.open(path) as p:
            raw = b"".join(bytes(pg.Contents.read_bytes()) for pg in p.pages
                           if "/Contents" in pg)
        text = raw.decode("latin-1", "replace")
    except Exception as e:
        return bad(f"could not extract text: {e}")

    digits = ssn.replace("-", "")
    if ssn in text or digits in re.sub(r"[^0-9]", "", text):
        return bad(f"the SSN {ssn} is still present in the extracted text")
    return ok("SSN absent from the text layer")


def contains_ocr_phrase(path, expected=None):
    phrase = manifest()["ocr_phrase"]
    data = open(path, "rb").read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            import pdfminer.high_level
            text = pdfminer.high_level.extract_text(path)
        except Exception:
            text = data.decode("latin-1", "replace")

    norm = re.sub(r"\s+", " ", text).lower()
    want = phrase.lower()
    if want in norm:
        return ok("found the expected phrase")
    # OCR is imperfect; accept a strong majority of the words.
    words = [w for w in want.split() if len(w) > 3]
    hits = sum(1 for w in words if w in norm)
    if words and hits / len(words) >= 0.7:
        return ok(f"{hits}/{len(words)} expected words present")
    return bad(f"only {hits}/{len(words)} expected words found in {len(text)} chars")


# ------------------------------------------------------------- archives

def _zip(path):
    return zipfile.ZipFile(path)


def zip_not_empty(path, expected=None):
    try:
        names = _zip(path).namelist()
    except Exception as e:
        return bad(f"not a zip: {e}")
    return ok(f"{len(names)} entries") if names else bad("zip is empty")


def zip_of_pdfs(path, expected=None):
    try:
        z = _zip(path)
        names = z.namelist()
    except Exception as e:
        return bad(f"not a zip: {e}")
    pdfs = [n for n in names if n.lower().endswith(".pdf")]
    if not pdfs:
        return bad(f"no PDFs in the zip ({names[:5]})")
    import pikepdf
    for n in pdfs[:5]:
        try:
            pikepdf.open(io.BytesIO(z.read(n)))
        except Exception as e:
            return bad(f"{n} is not a valid PDF: {e}")
    if expected and len(pdfs) != int(expected):
        return bad(f"expected {expected} PDFs, got {len(pdfs)}")
    return ok(f"{len(pdfs)} valid PDFs")


def zip_of_images(path, expected=None):
    from PIL import Image
    try:
        z = _zip(path)
        names = z.namelist()
    except Exception as e:
        return bad(f"not a zip: {e}")
    imgs = [n for n in names if re.search(r"\.(jpe?g|png|webp|gif|bmp|tiff?)$", n, re.I)]
    if not imgs:
        return bad(f"no images in the zip ({names[:5]})")
    for n in imgs[:5]:
        try:
            Image.open(io.BytesIO(z.read(n))).verify()
        except Exception as e:
            return bad(f"{n} is not a valid image: {e}")
    if expected and len(imgs) < int(expected):
        return bad(f"expected at least {expected} images, got {len(imgs)}")
    return ok(f"{len(imgs)} valid images")


# --------------------------------------------------------------- media

def valid_image(path, expected=None):
    from PIL import Image
    try:
        im = Image.open(path)
        im.verify()
        im = Image.open(path)
        return ok(f"{im.format} {im.width}x{im.height}")
    except Exception as e:
        return bad(f"not a valid image: {e}")


def image_smaller(path, expected=None):
    src = os.path.join(FIXTURES, "large.jpg")
    v = valid_image(path)
    if not v["ok"]:
        return v
    before, after = os.path.getsize(src), os.path.getsize(path)
    if after < before:
        return ok(f"{before} -> {after} bytes ({(1 - after / before) * 100:.0f}% smaller)")
    return bad(f"not smaller: {before} -> {after} bytes")


def image_resized(path, expected=None):
    from PIL import Image
    v = valid_image(path)
    if not v["ok"]:
        return v
    src = Image.open(os.path.join(FIXTURES, "photo.jpg"))
    out = Image.open(path)
    if expected:
        # A requested width is the real assertion: "changed somehow" would
        # pass on a tool that resized to the wrong size.
        want = int(expected)
        if out.width != want:
            return bad(f"asked for width {want}, got {out.width}x{out.height}")
        return ok(f"{src.width}x{src.height} -> {out.width}x{out.height} (asked {want})")
    if (out.width, out.height) != (src.width, src.height):
        return ok(f"{src.width}x{src.height} -> {out.width}x{out.height}")
    return bad(f"dimensions unchanged at {out.width}x{out.height}")


def exif_stripped(path, expected=None):
    """The output must carry no GPS and no camera identity."""
    from PIL import Image
    v = valid_image(path)
    if not v["ok"]:
        return v
    try:
        import piexif
        try:
            ex = piexif.load(path)
        except Exception:
            return ok("no parseable EXIF block at all")
        gps = ex.get("GPS") or {}
        zeroth = ex.get("0th") or {}
        leftovers = []
        if gps:
            leftovers.append(f"GPS ({len(gps)} tags)")
        for tag, name in ((piexif.ImageIFD.Make, "Make"), (piexif.ImageIFD.Model, "Model")):
            if tag in zeroth:
                leftovers.append(name)
        if leftovers:
            return bad("still present: " + ", ".join(leftovers))
        return ok("GPS and camera tags removed")
    except ImportError:
        exif = Image.open(path).getexif()
        return ok("no EXIF") if not exif else bad(f"{len(exif)} EXIF tags remain")


def valid_gif(path, expected=None):
    from PIL import Image
    try:
        im = Image.open(path)
        if im.format != "GIF":
            return bad(f"expected GIF, got {im.format}")
        frames = getattr(im, "n_frames", 1)
        return ok(f"GIF {im.width}x{im.height}, {frames} frames")
    except Exception as e:
        return bad(f"not a valid GIF: {e}")


def valid_video(path, expected=None):
    """Container sniffing — no decoder is guaranteed present, but a WebM or
    MP4 header plus a plausible size is a real check against a zero-byte or
    HTML-error-page 'video'."""
    data = open(path, "rb").read(64)
    size = os.path.getsize(path)
    if size < 1024:
        return bad(f"only {size} bytes")
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return ok(f"WebM/Matroska, {size / 1024:.0f} KB")
    if data[4:8] == b"ftyp":
        return ok(f"MP4, {size / 1024:.0f} KB")
    return bad(f"unrecognised container (first bytes {data[:8]!r})")


def valid_audio(path, expected=None):
    data = open(path, "rb").read(16)
    size = os.path.getsize(path)
    if size < 512:
        return bad(f"only {size} bytes")
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return ok(f"WAV, {size / 1024:.0f} KB")
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return ok(f"MP3, {size / 1024:.0f} KB")
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return ok(f"WebM audio, {size / 1024:.0f} KB")
    if data[:4] == b"OggS":
        return ok(f"Ogg, {size / 1024:.0f} KB")
    return bad(f"unrecognised audio container ({data[:8]!r})")


# ------------------------------------------------------------ documents

def valid_docx(path, expected=None):
    try:
        z = zipfile.ZipFile(path)
        if "word/document.xml" not in z.namelist():
            return bad("zip has no word/document.xml — not a .docx")
        return ok("valid .docx")
    except Exception as e:
        return bad(f"not a .docx: {e}")


def csv_has_rows(path, expected=None):
    text = open(path, encoding="utf-8", errors="replace").read()
    rows = [r for r in text.splitlines() if r.strip()]
    want = int(expected) if expected else 2
    if len(rows) >= want:
        return ok(f"{len(rows)} rows")
    return bad(f"only {len(rows)} rows, expected at least {want}")


CHECKERS = {k: v for k, v in list(globals().items()) if callable(v) and not k.startswith("_")}


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: validate-output.py <checker> <file> [expected]")
    name, path = sys.argv[1], sys.argv[2]
    expected = sys.argv[3] if len(sys.argv) > 3 else None

    fn = CHECKERS.get(name)
    if fn is None:
        print(json.dumps(bad(f"unknown checker {name!r}")))
        return
    if not os.path.exists(path):
        print(json.dumps(bad("output file does not exist")))
        return
    try:
        print(json.dumps(fn(path, expected)))
    except Exception as e:
        print(json.dumps(bad(f"{type(e).__name__}: {e}")))


if __name__ == "__main__":
    main()

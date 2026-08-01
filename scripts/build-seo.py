#!/usr/bin/env python3
"""
Generate the SEO landing pages, sitemap.xml and robots.txt.

    python scripts/build-seo.py

Three families of page, all written into frontend/tools/:

  * format pairs   — "pdf-to-word", "markdown-to-pdf", ... one per real
                     conversion people search for
  * per-tool       — one per tool in the app
  * questions      — the plain-language problems people actually type

Every page deep-links into the live app (index.html?tool=...) so it answers
the query rather than being a stop on the way to answering it, and every
page carries its own title, description, body copy and FAQ.

On volume: this deliberately produces a few hundred pages, not thousands.
Google's scaled-content-abuse policy targets mass-generated near-duplicates,
and a manual action would deindex the whole domain — the opposite of the
goal. Each page here maps to a distinct search intent with its own content.
Adding more is fine; adding more *of the same* is not.
"""

import html
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")
OUT_DIR = os.path.join(FRONTEND, "tools")
# The origin every canonical, og:url, and sitemap entry points at. A
# canonical tag naming a host that does not resolve tells search engines the
# real copy of the page lives somewhere unreachable, which is worse for
# ranking than having no canonical at all — so this must match the host the
# site is actually served from. Override when deploying elsewhere:
#     SITE_ORIGIN=https://pdflove.example.workers.dev python scripts/build-seo.py
# scripts/check-canonical.py verifies the configured host really answers.
SITE = os.environ.get("SITE_ORIGIN", "https://pdflove.co.in").rstrip("/")
TODAY = date.today().isoformat()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tool_content import CONTENT as TOOL_CONTENT  # noqa: E402
from tool_content import PAIR_CONTENT, QUESTION_CONTENT  # noqa: E402

# Tools whose pages exist for people who browse to them, but which should not
# compete in search.
#
# The rule is not guessed search volume — it is whether this product's actual
# claim means anything for that tool. "Runs on your device, nothing is
# uploaded" matters enormously when you hand over a bank statement. It means
# nothing when you roll a die. For the tools below we have no advantage worth
# writing 200 words about, and a page 70% identical to its 85 siblings would
# never have ranked anyway — it would only have dragged on the domain.
#
# noindex,follow rather than nofollow: these pages should still pass link
# equity through to the ones that matter.
NOINDEX_TOOLS = {
    "Word & Character Counter", "Change Text Case", "Compare Two Texts",
    "Remove Duplicate Lines", "Placeholder Text Generator", "Unit Converter",
    "JSON Formatter & Checker", "Base64 Encode / Decode", "Hash Generator",
    "Date & Timestamp Converter", "URL Encode / Decode", "Age Calculator",
    "BMI Calculator", "Color Converter & Palette", "CSV ↔ JSON Converter",
    "Stopwatch & Countdown Timer", "Random Number, Dice & Coin",
    "Barcode Generator", "Pattern (Regex) Tester", "Loan / EMI Calculator",
    "Simple vs. Compound Interest", "Currency Converter",
}


# --------------------------------------------------------------------
# Source data: real conversions, with the phrasing people actually search.
# --------------------------------------------------------------------
FORMATS = {
    "pdf":      ("PDF", "Portable Document Format"),
    "word":     ("Word", "Microsoft Word document (.docx)"),
    "excel":    ("Excel", "Microsoft Excel spreadsheet (.xlsx)"),
    "powerpoint": ("PowerPoint", "Microsoft PowerPoint deck (.pptx)"),
    "jpg":      ("JPG", "JPEG image"),
    "png":      ("PNG", "PNG image"),
    "webp":     ("WebP", "WebP image"),
    "gif":      ("GIF", "GIF image"),
    "bmp":      ("BMP", "bitmap image"),
    "heic":     ("HEIC", "iPhone HEIC photo"),
    "markdown": ("Markdown", "Markdown text file (.md)"),
    "text":     ("Text", "plain text file (.txt)"),
    "html":     ("HTML", "web page"),
    "csv":      ("CSV", "comma-separated values file"),
    "json":     ("JSON", "JSON data file"),
    "svg":      ("SVG", "scalable vector image"),
    "epub":     ("EPUB", "EPUB e-book"),
    "video":    ("Video", "video file"),
    "mp3":      ("MP3", "MP3 audio file"),
    "wav":      ("WAV", "WAV audio file"),
}

# (from, to, tool name in the app, extra sentence about this specific pair)
PAIRS = [
    ("pdf", "word", "PDF to Word", "Keeps the layout, so headings and tables survive the trip."),
    ("word", "pdf", "Word to PDF", "Fonts and page breaks come out exactly as Word laid them out."),
    ("pdf", "jpg", "PDF to JPG", "Every page becomes its own image at the resolution you pick."),
    ("jpg", "pdf", "Images to PDF", "Drop in as many photos as you like; they become pages in order."),
    ("png", "pdf", "Images to PDF", "Transparency is flattened onto white, the way a printer would."),
    ("webp", "pdf", "Images to PDF", "WebP is decoded natively by your browser, so nothing is re-compressed twice."),
    ("gif", "pdf", "Images to PDF", "The first frame is used for each animated GIF."),
    ("bmp", "pdf", "Images to PDF", "Old bitmaps compress dramatically on the way in."),
    ("heic", "jpg", "Convert Image Format", "The format iPhones save in, turned into something everything can open."),
    ("heic", "pdf", "Images to PDF", "Straight from an iPhone photo to a shareable document."),
    ("pdf", "markdown", "PDF to Markdown", "Headings, lists and emphasis are inferred from the layout."),
    ("markdown", "pdf", "Markdown to PDF", "Renders headings, code blocks, tables and links properly."),
    ("pdf", "text", "PDF to Text", "Just the words, in reading order."),
    ("html", "pdf", "HTML / Text to PDF", "Paste a page or type directly; styling is preserved."),
    ("text", "pdf", "HTML / Text to PDF", "Plain text becomes a properly paginated document."),
    ("pdf", "powerpoint", "PDF to PowerPoint", "Each page becomes an editable slide."),
    ("powerpoint", "pdf", "PowerPoint to PDF", "Slides, speaker notes and all."),
    ("pdf", "excel", "PDF to Excel", "Detects table structure rather than dumping text into one column."),
    ("excel", "pdf", "Excel to PDF", "Print ranges and page breaks respected."),
    ("csv", "json", "CSV ↔ JSON Converter", "Round-trips both ways without losing types."),
    ("json", "csv", "CSV ↔ JSON Converter", "Nested objects are flattened into columns."),
    ("png", "jpg", "Convert Image Format", "Choose the quality; see the size before you save."),
    ("jpg", "png", "Convert Image Format", "For when you need lossless or transparency."),
    ("jpg", "webp", "Convert Image Format", "Usually 25-35% smaller at the same visual quality."),
    ("png", "webp", "Convert Image Format", "Keeps transparency, cuts the file size."),
    ("webp", "jpg", "Convert Image Format", "For tools that still do not read WebP."),
    ("webp", "png", "Convert Image Format", "Lossless, with transparency intact."),
    ("video", "gif", "Video to GIF", "No watermark, no length cap, no upload."),
    ("video", "mp3", "Extract Audio from Video", "Pulls the audio track out without re-encoding where possible."),
    ("video", "wav", "Extract Audio from Video", "Uncompressed audio for editing."),
    ("jpg", "text", "OCR — Make Scans Searchable", "Reads the text in a photo and gives it back as characters."),
    ("pdf", "csv", "Table to CSV", "Finds tables in the page and exports them as rows."),
]

# The questions people type, beyond the 7 guides that already exist.
QUESTIONS = [
    ("how-to-merge-pdf-files-for-free", "How do I merge PDF files for free?", "Merge PDF",
     "Combine any number of PDFs into one, in the order you choose, without uploading them anywhere."),
    ("how-to-reduce-pdf-file-size", "How do I reduce a PDF's file size?", "Make PDF Smaller",
     "Shrink a PDF to fit an email or upload limit, with a preview of the result before you save."),
    ("how-to-convert-pdf-to-word-without-losing-formatting", "How do I convert PDF to Word without losing formatting?", "PDF to Word",
     "Layout-aware conversion that keeps headings, tables and columns where they were."),
    ("how-to-remove-pages-from-a-pdf", "How do I remove pages from a PDF?", "Organize PDF",
     "Delete, reorder or keep only the pages you want, then save the result."),
    ("how-to-rotate-a-pdf-permanently", "How do I rotate a PDF permanently?", "Rotate PDF",
     "Rotation that is saved into the file, not just how your viewer displays it."),
    ("how-to-add-a-password-to-a-pdf", "How do I password-protect a PDF?", "Protect PDF",
     "Real AES-256 encryption, applied in your browser."),
    ("how-to-sign-a-pdf-electronically", "How do I sign a PDF electronically?", "Sign PDF",
     "Draw, type or upload a signature and place it anywhere on the page."),
    ("how-to-add-page-numbers-to-a-pdf", "How do I add page numbers to a PDF?", "Page Numbering & Document ID",
     "Bates numbering and plain page numbers, with control over position and format."),
    ("how-to-add-a-watermark-to-a-pdf", "How do I add a watermark to a PDF?", "Add Watermark",
     "Text or image watermarks, with opacity and rotation."),
    ("how-to-extract-images-from-a-pdf", "How do I extract images from a PDF?", "Extract Images",
     "Pulls every embedded image out at original quality, into a zip."),
    ("how-to-compress-an-image-without-losing-quality", "How do I compress an image without losing quality?", "Make Image Smaller",
     "Adjust quality and see the size change before you commit."),
    ("how-to-resize-an-image", "How do I resize an image?", "Resize Image",
     "By pixels or percentage, keeping the aspect ratio if you want."),
    ("how-to-remove-the-background-from-an-image", "How do I remove an image's background?", "Remove Background",
     "An AI model runs in your browser and cuts the subject out."),
    ("how-to-remove-exif-data-from-photos", "How do I remove EXIF data from photos?", "Remove Photo Metadata (EXIF)",
     "Strips GPS coordinates, camera details and timestamps before you share."),
    ("how-to-scan-a-document-with-your-phone", "How do I scan a document with my phone?", "Scan Document",
     "Point the camera at a page; the edges are found automatically and flattened like a real scan."),
    ("how-to-make-a-scanned-pdf-searchable", "How do I make a scanned PDF searchable?", "OCR — Make Scans Searchable",
     "Real OCR in your browser turns a picture of text into text you can select and search."),
    ("how-to-convert-a-photo-to-pdf", "How do I turn a photo into a PDF?", "Images to PDF",
     "One photo or fifty, in the order you arrange them."),
    ("how-to-split-a-pdf-into-separate-pages", "How do I split a PDF into separate pages?", "Split PDF",
     "One file per page, or a specific range."),
    ("how-to-fill-in-a-pdf-form", "How do I fill in a PDF form?", "PDF Forms",
     "Type into the fields and save a filled copy, or flatten it so it cannot be edited."),
    ("how-to-flatten-a-pdf", "How do I flatten a PDF?", "Flatten PDF",
     "Bakes form fields and annotations into the page so they cannot be changed."),
    ("how-to-convert-a-pdf-to-black-and-white", "How do I convert a PDF to black and white?", "Grayscale PDF",
     "Often shrinks the file substantially as a side effect."),
    ("how-to-compare-two-pdfs", "How do I compare two PDFs?", "Compare PDF",
     "Highlights what changed between two versions."),
    ("how-to-repair-a-corrupted-pdf", "How do I repair a corrupted PDF?", "Repair PDF",
     "Rebuilds a malformed file's structure so viewers will open it again."),
    ("how-to-generate-a-qr-code", "How do I generate a QR code?", "QR Code Generator",
     "Any text or URL, at any size, downloadable as PNG or SVG."),
    ("how-to-create-an-invoice", "How do I create an invoice?", "Invoice Generator",
     "Fill in the lines, get a clean PDF invoice. Nothing is stored."),
    ("how-to-make-a-passport-photo", "How do I make a passport photo?", "Passport & ID Photo Maker",
     "Correct dimensions for common countries, ready to print."),
    ("how-to-convert-a-video-to-gif", "How do I convert a video to a GIF?", "Video to GIF",
     "Pick the section and frame rate; no watermark is added."),
    ("how-to-trim-a-video", "How do I trim a video?", "Trim Video",
     "Cut to the part you want, keeping the audio."),
    ("how-to-record-your-screen", "How do I record my screen?", "Screen Recorder",
     "Records to a file on your machine. Nothing is streamed anywhere."),
    ("how-to-redact-text-in-a-pdf", "How do I properly redact text in a PDF?", "Search & Redact",
     "Removes the text, rather than drawing a black box over text that is still there."),
]


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def esc(s):
    return html.escape(s, quote=True)


def page(slug, title, description, h1, lede, body_html, faq, tool_name, related,
         noindex=False):
    """Render one landing page.

    The page mounts its one named tool in place via #tool-mount (see
    panelShell() in frontend/app.js) instead of only linking out to the
    modal — a visitor from search lands on a working tool, not a doorway
    page. #overlay/#panel still ship too: "related tools" links on this
    page open in the modal, exactly as they do from the homepage.
    """
    canonical = f"{SITE}/tools/{slug}.html"
    faq_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq
        ],
    }
    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "PDF Love", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Tools", "item": SITE + "/tools/"},
            {"@type": "ListItem", "position": 3, "name": h1, "item": canonical},
        ],
    }
    # Root-absolute, not page-relative: <base href="/"> below makes every
    # relative path in this page (including app.js's internal vendor/ and
    # sw.js lookups) resolve against the site root instead of /tools/, which
    # is what app.js — written for index.html at the root — assumes. That
    # means same-directory links must be written as absolute paths here.
    related_html = "".join(
        f'<li><a href="/tools/{esc(r_slug)}.html">{esc(r_title)}</a></li>'
        for r_slug, r_title in related
    )
    faq_html = "".join(
        f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faq
    )
    # Fallback for JS-disabled visitors and for anything that opens this
    # page's tool from elsewhere (search, ?tool= deep links). The primary
    # path is #tool-mount below, filled in by panelShell() in app.js.
    deep_link = f"../index.html?tool={esc(tool_name)}"

    # noindex,follow keeps the page usable and still passing link equity,
    # while keeping it out of the index. Paired with exclusion from
    # sitemap.xml in build_sitemap — a sitemap listing a noindexed URL
    # tells crawlers two contradictory things.
    robots = ("noindex, follow" if noindex else
              "index, follow, max-image-preview:large, max-snippet:-1")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="{robots}">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}/icons/feature-graphic-1024x500.png">
<meta name="twitter:card" content="summary_large_image">
<base href="/">
<link href="vendor/fonts/fonts.css" rel="stylesheet">
<link href="company/company.css" rel="stylesheet">
<link href="app.css" rel="stylesheet">
<script type="application/ld+json">{json.dumps(faq_ld)}</script>
<script type="application/ld+json">{json.dumps(breadcrumb_ld)}</script>
</head>
<body>
<header>
  <div class="wrap header-row">
    <a class="brand" href="index.html"><span class="dot"></span>PDF Love</a>
    <nav class="site-nav" id="site-nav" aria-label="Tools">
      <a class="nav-link" href="tools/merge-pdf.html">Merge PDF</a>
      <a class="nav-link" href="tools/split-pdf.html">Split PDF</a>
      <a class="nav-link" href="tools/make-pdf-smaller.html">Compress PDF</a>
      <div class="nav-dropdown">
        <button type="button" class="nav-link nav-trigger" id="nav-trigger-convert" aria-expanded="false" aria-controls="nav-panel-convert">Convert<span class="nav-caret">▾</span></button>
        <div class="nav-panel" id="nav-panel-convert" hidden></div>
      </div>
      <div class="nav-dropdown">
        <button type="button" class="nav-link nav-trigger" id="nav-trigger-all" aria-expanded="false" aria-controls="nav-panel-all">All tools<span class="nav-caret">▾</span></button>
        <div class="nav-panel nav-panel-mega" id="nav-panel-all" hidden></div>
      </div>
    </nav>
  </div>
</header>
<div class="overlay" id="overlay"><div class="panel" id="panel"></div></div>
<main><div class="wrap">
  <p class="breadcrumb"><a href="../index.html">Home</a> / <a href="/tools/index.html">Tools</a> / {esc(h1)}</p>
  <h1>{esc(h1)}</h1>
  <p class="lede">{esc(lede)}</p>

  <div id="tool-mount" data-tool="{esc(tool_name)}"></div>
  <noscript><p><a class="cta" href="{deep_link}">Open {esc(tool_name)}</a></p></noscript>

  <div class="ad-slot" id="ad-leaderboard-slot"></div>

  <div class="note">
    <strong>Your file never leaves this device.</strong> Pick a file and watch
    the Network tab — nothing fires while it is being processed. No upload,
    no account, no daily limit.
  </div>

{body_html}

  <h2>Common questions</h2>
{faq_html}

  <h2>Related tools</h2>
  <ul>{related_html}</ul>

  <div class="ad-slot ad-slot-sticky" id="ad-sticky-slot"></div>

  <p style="margin-top:26px;"><a class="cta secondary" href="../index.html">See all 104 tools</a></p>
</div></main>
<div class="platform-strip"><div class="wrap">
  <span class="platform-label">Available on</span>
  <a href="../download.html#plat-web">Web</a>
  <a href="../download.html#plat-desktop">Windows</a>
  <a href="../download.html#plat-desktop">macOS</a>
  <a href="../download.html#plat-desktop">Linux</a>
  <a href="../download.html#plat-android">Android</a>
</div></div>

<footer class="dark-footer">
  <div class="wrap footer-grid">
    <div class="footer-col">
      <h4>Product</h4>
      <a href="../index.html">All 104 tools</a>
      <a href="../tools/merge-pdf.html">Merge PDF</a>
      <a href="../tools/split-pdf.html">Split PDF</a>
      <a href="../tools/make-pdf-smaller.html">Compress PDF</a>
      <a href="../download.html">Download</a>
    </div>
    <div class="footer-col">
      <h4>Resources</h4>
      <a href="../guides/index.html">Guides</a>
      <a href="/tools/index.html">All guides</a>
      <a href="../company/security.html">Security</a>
    </div>
    <div class="footer-col">
      <h4>Company</h4>
      <a href="../company/about.html">About</a>
      <a href="../company/pricing.html">Pricing</a>
      <a href="../company/for-business.html">For business</a>
      <a href="../company/contact.html">Contact</a>
    </div>
    <div class="footer-col">
      <h4>Legal</h4>
      <a href="../company/legal.html">Legal, in plain English</a>
      <a href="../company/privacy.html">Privacy</a>
      <a href="../company/terms.html">Terms</a>
      <a href="../company/cookies.html">Cookies &amp; ads</a>
      <a href="../company/grievance.html">Grievance</a>
      <a href="../company/refund.html">Refunds</a>
    </div>
    <div class="footer-col">
      <h4>Get PDF Love</h4>
      <a href="../download.html#plat-web">Web app</a>
      <a href="../download.html#plat-desktop">Desktop app</a>
      <a href="../download.html#plat-android">Android app</a>
    </div>
  </div>
  <div class="wrap footer-bottom">
    <span class="brand-mini"><span class="dot"></span>PDF Love</span>
    <span class="footer-fine">PDF, image and video tools that run on your own device.</span>
  </div>
</footer>
<script defer src="../vendor/pdf-lib.min.js" onerror="this.remove();var s=document.createElement('script');s.defer=true;s.integrity='sha384-weMABwrltA6jWR8DDe9Jp5blk+tZQh7ugpCsF3JwSA53WZM9/14PjS5LAJNHNjAI';s.crossOrigin='anonymous';s.src='https://cdnjs.cloudflare.com/ajax/libs/pdf-lib/1.17.1/pdf-lib.min.js';document.head.appendChild(s)"></script>
<script defer src="../vendor/pdf.min.js" onerror="this.remove();var s=document.createElement('script');s.defer=true;s.integrity='sha384-/1qUCSGwTur9vjf/z9lmu/eCUYbpOTgSjmpbMQZ1/CtX2v/WcAIKqRv+U1DUCG6e';s.crossOrigin='anonymous';s.src='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';document.head.appendChild(s)"></script>
<script defer src="../vendor/jszip.min.js" onerror="this.remove();var s=document.createElement('script');s.defer=true;s.integrity='sha384-+mbV2IY1Zk/X1p/nWllGySJSUN8uMs+gUAN10Or95UBH0fpj6GfKgPmgC5EXieXG';s.crossOrigin='anonymous';s.src='https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';document.head.appendChild(s)"></script>
<script defer src="../vendor/mammoth.browser.min.js" onerror="this.remove();var s=document.createElement('script');s.defer=true;s.integrity='sha384-/cXAMbzovUIKbBERjPmR3SnPTh8siWr5lsvFYj1Uq4XP0yaJUZJmsh0YXyGv5P0y';s.crossOrigin='anonymous';s.src='https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.8.0/mammoth.browser.min.js';document.head.appendChild(s)"></script>
<script defer src="../vendor/jspdf.umd.min.js" onerror="this.remove();var s=document.createElement('script');s.defer=true;s.integrity='sha384-JcnsjUPPylna1s1fvi1u12X5qjY5OL56iySh75FdtrwhO/SWXgMjoVqcKyIIWOLk';s.crossOrigin='anonymous';s.src='https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';document.head.appendChild(s)"></script>
<script defer src="../vendor/html2canvas.min.js" onerror="this.remove();var s=document.createElement('script');s.defer=true;s.integrity='sha384-ZZ1pncU3bQe8y31yfZdMFdSpttDoPmOZg2wguVK9almUodir1PghgT0eY7Mrty8H';s.crossOrigin='anonymous';s.src='https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';document.head.appendChild(s)"></script>
<script defer src="../app.js"></script>
<script defer src="../ads.js"></script>
</body>
</html>
"""


def build_pairs(index):
    pages = []
    missing = [f"{a}-to-{b}" for a, b, _, _ in PAIRS
               if f"{a}-to-{b}" not in PAIR_CONTENT]
    if missing:
        raise SystemExit(
            f"\n{len(missing)} conversion page(s) have no entry in "
            f"PAIR_CONTENT in scripts/tool_content.py:\n  " +
            "\n  ".join(missing) +
            "\n\nEvery conversion page needs format-specific copy — what "
            "survives the conversion and what does not. A shared template "
            "across 32 pages is what search engines read as scaled content.\n")
    for src, dst, tool, extra in PAIRS:
        s_name, s_desc = FORMATS[src]
        d_name, d_desc = FORMATS[dst]
        slug = f"{src}-to-{dst}"
        title = f"{s_name} to {d_name} — free, no upload | PDF Love"
        h1 = f"Convert {s_name} to {d_name}"
        desc = f"Convert {s_name} to {d_name} free in your browser. No upload, no account, no watermark. {extra}"
        if len(desc) > 160:
            desc = f"Convert {s_name} to {d_name} free in your browser — no upload, no account, no watermark. {extra}"[:158].rsplit(" ", 1)[0] + "."
        entry = PAIR_CONTENT[slug]
        lede = (f"Turn a {s_desc} into a {d_desc} without sending it anywhere. "
                f"The conversion runs on your own device.")
        body = f"""
  <h2>How to convert {esc(s_name)} to {esc(d_name)}</h2>
  <ol>
    <li>Open the {esc(tool)} tool.</li>
    <li>Choose your {esc(s_name)} file, or drag it onto the page.</li>
    <li>Adjust the options if you want to — defaults are sensible.</li>
    <li>Download the {esc(d_name)} result. It saves straight to your downloads folder.</li>
  </ol>

  <h2>What survives the conversion</h2>
  <p>{entry["notes"]}</p>
"""
        faq = entry["faq"]
        related = [(f"{a}-to-{b}", f"{FORMATS[a][0]} to {FORMATS[b][0]}")
                   for a, b, _, _ in PAIRS
                   if (a, b) != (src, dst) and (a == src or b == dst)][:6]
        pages.append((slug, page(slug, title, desc, h1, lede, body, faq, tool, related)))
        index.append((slug, h1, desc, "Convert"))
    return pages


def build_tools(index, tool_names):
    pages = []
    missing = []
    for name in tool_names:
        slug = slugify(name)
        # Some tool names are long ("Describe a Photo / Alt-Text (On Your
        # Device)"). Trim the parenthetical for the title so it still fits
        # what search engines render, while the h1 keeps the full name.
        short = re.sub(r"\s*\([^)]*\)", "", name).strip()
        title = f"{short} — free, on-device | PDF Love"
        if len(title) > 68:
            title = f"{short[:52].rstrip()} — free | PDF Love"
        desc = (f"{name}, free in your browser. Runs on your own device — no upload, "
                f"no account, no daily limit. Works offline.")
        h1 = name
        noindex = name in NOINDEX_TOOLS

        entry = TOOL_CONTENT.get(name)
        if entry is None:
            if not noindex:
                missing.append(name)
            # Noindexed pages keep the short generic body on purpose: they
            # are not competing in search, so unique prose there would be
            # writing nobody reads.
            lede = f"{name}, running entirely on your own device."
            body = f"""
  <h2>Using {esc(name)}</h2>
  <ol>
    <li>Open the tool.</li>
    <li>Choose your file, or drag it onto the page.</li>
    <li>Set the options you need.</li>
    <li>Download the result.</li>
  </ol>
"""
            faq = [
                (f"Is {name} free?", "Yes — no account, no daily limit, no card."),
                ("Are my files uploaded?",
                 "No. Everything happens in your browser, on your own device."),
            ]
        else:
            lede = entry["intro"]
            steps = "\n".join(f"    <li>{s}</li>" for s in entry["steps"])
            body = f"""
  <h2>How to use {esc(name)}</h2>
  <ol>
{steps}
  </ol>

  <h2>What to know</h2>
  <p>{entry["notes"]}</p>
"""
            faq = entry["faq"]

        related = [(slugify(n), n) for n in tool_names if n != name][:6]
        pages.append((slug, page(slug, title, desc, h1, lede, body, faq, name,
                                 related, noindex=noindex)))
        if not noindex:
            index.append((slug, h1, desc, "Tools"))

    if missing:
        raise SystemExit(
            f"\n{len(missing)} indexed tool(s) have no entry in "
            f"scripts/tool_content.py:\n  " + "\n  ".join(missing) +
            "\n\nEvery indexed page needs its own content — a generic page is "
            "what got us into this. Add an entry, or add the tool to "
            "NOINDEX_TOOLS if it genuinely should not compete in search.\n")
    return pages


def build_questions(index):
    pages = []
    missing = [s for s, _, _, _ in QUESTIONS if s not in QUESTION_CONTENT]
    if missing:
        raise SystemExit(
            f"\n{len(missing)} question page(s) have no entry in "
            f"QUESTION_CONTENT in scripts/tool_content.py:\n  " +
            "\n  ".join(missing) +
            "\n\nA question page that does not answer its question is filler. "
            "Write why the problem happens and what to do when the obvious "
            "fix fails, or drop the question.\n")
    for slug, question, tool, answer in QUESTIONS:
        entry = QUESTION_CONTENT[slug]
        title = f"{question} | PDF Love"
        desc = f"{answer} Free, in your browser, with nothing uploaded."
        steps = "\n".join(f"    <li>{s}</li>" for s in entry["steps"])
        body = f"""
  <h2>The short answer</h2>
  <p>{esc(answer)}</p>
  <h2>What is actually going on</h2>
  <p>{entry["why"]}</p>
  <h2>Step by step</h2>
  <ol>
{steps}
  </ol>
"""
        faq = entry["faq"]
        related = [(s, q) for s, q, _, _ in QUESTIONS if s != slug][:6]
        pages.append((slug, page(slug, title, desc, question, answer, body, faq, tool, related)))
        index.append((slug, question, desc, "Questions"))
    return pages


def extract_tool_names():
    """Read the real tool list out of the app, so these pages can never
    drift from what actually exists. Tool registry arrays live in
    frontend/app.js (extracted out of index.html's inline <script>)."""
    src = open(os.path.join(FRONTEND, "app.js")).read()
    # Anchored to the {icon:'...', name:'...' registry-entry shape, not just
    # any `name:'...'` — a comment describing Emscripten's ExitStatus object
    # (`{name:'ExitStatus', status:N}`) otherwise matches too and produces a
    # bogus tool page for a thing that isn't a tool.
    names = re.findall(r"\{icon:'[^']*',\s*name:'([^']+)'", src)
    # Server-assisted tools are hidden without a backend; a landing page for
    # one would send visitors to a tool they cannot see.
    skip = {"OCR (server)", "Word/Office to PDF (full fidelity)",
            "PowerPoint to PDF (full fidelity)", "Excel to PDF (full fidelity)",
            "PDF to Word (layout-aware)", "Remove Background (server)", "Chat with PDF"}
    return [n for n in dict.fromkeys(names) if n not in skip]


def build_index(index):
    groups = {}
    for slug, title, desc, group in index:
        groups.setdefault(group, []).append((slug, title, desc))
    sections = ""
    for group in ("Convert", "Questions", "Tools"):
        items = sorted(groups.get(group, []))
        if not items:
            continue
        links = "".join(
            f'<li><a href="{esc(s)}.html">{esc(t)}</a><p>{esc(d[:110])}</p></li>'
            for s, t, d in items)
        sections += f'<div class="card"><h2>{group} ({len(items)})</h2><ul style="list-style:none;padding:0;">{links}</ul></div>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>All tools and guides | PDF Love</title>
<meta name="description" content="Every PDF Love tool and conversion, with a guide for each. Free, on-device, no upload.">
<link rel="canonical" href="{SITE}/tools/">
<link href="../vendor/fonts/fonts.css" rel="stylesheet">
<link href="../company/company.css" rel="stylesheet">
<link href="../app.css" rel="stylesheet">
</head>
<body>
<header><div class="wrap header-row">
  <a class="brand" href="../index.html"><span class="dot"></span>PDF Love</a>
  <nav class="site-nav" aria-label="Tools">
    <a class="nav-link" href="merge-pdf.html">Merge PDF</a>
    <a class="nav-link" href="split-pdf.html">Split PDF</a>
    <a class="nav-link" href="make-pdf-smaller.html">Compress PDF</a>
  </nav>
</div></header>
<main><div class="wrap">
  <h1>Every tool, and how to use it</h1>
  <p class="lede">{len(index)} pages covering every conversion and tool in
  PDF Love. All of them run on your own device.</p>
  {sections}
</div></main>
<footer class="site-footer"><div class="wrap">
  <nav>
    <a href="../index.html">Tools</a>
    <a href="../download.html">Download</a>
    <a href="../guides/index.html">Guides</a>
    <a href="../company/about.html">About</a>
    <a href="../company/privacy.html">Privacy</a>
  </nav>
</div></footer>
</body>
</html>
"""


def build_sitemap(slugs):
    urls = [
        (SITE + "/", "1.0", "weekly"),
        (SITE + "/download.html", "0.9", "weekly"),
        (SITE + "/tools/", "0.8", "weekly"),
        (SITE + "/guides/index.html", "0.7", "monthly"),
    ]
    for f in sorted(os.listdir(os.path.join(FRONTEND, "guides"))):
        if f.endswith(".html") and f != "index.html":
            urls.append((f"{SITE}/guides/{f}", "0.7", "monthly"))
    for f in sorted(os.listdir(os.path.join(FRONTEND, "company"))):
        if f.endswith(".html"):
            urls.append((f"{SITE}/company/{f}", "0.4", "yearly"))
    for s in sorted(slugs):
        urls.append((f"{SITE}/tools/{s}.html", "0.6", "monthly"))

    body = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod>"
        f"<changefreq>{cf}</changefreq><priority>{p}</priority></url>"
        for u, p, cf in urls)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'{body}\n</urlset>\n'), len(urls)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in os.listdir(OUT_DIR):
        if f.endswith(".html"):
            os.remove(os.path.join(OUT_DIR, f))

    tool_names = extract_tool_names()
    print(f"found {len(tool_names)} on-device tools in the app")

    index = []
    pages = build_pairs(index) + build_tools(index, tool_names) + build_questions(index)

    seen = {}
    for slug, content in pages:
        if slug in seen:
            continue          # a tool serving two pairs shares one page
        # Derived from what the page actually says rather than recomputed
        # from NOINDEX_TOOLS, so the sitemap cannot drift from the robots
        # tag. A slug can be produced by more than one generator — the first
        # wins — and only that surviving page's own tag should decide this.
        seen[slug] = "noindex" not in content.split("</head>")[0]
        with open(os.path.join(OUT_DIR, slug + ".html"), "w") as f:
            f.write(content)

    with open(os.path.join(OUT_DIR, "index.html"), "w") as f:
        f.write(build_index(index))

    indexable = [s for s, ok in seen.items() if ok]
    print(f"  {len(seen) - len(indexable)} page(s) noindexed and kept out of the sitemap")
    sitemap, n_urls = build_sitemap(indexable)
    with open(os.path.join(FRONTEND, "sitemap.xml"), "w") as f:
        f.write(sitemap)

    with open(os.path.join(FRONTEND, "robots.txt"), "w") as f:
        f.write(f"""User-agent: *
Allow: /

# Generated pages that exist only to be crawled would be a bad signal; every
# page in /tools/ answers a real query and embeds the working tool.
Sitemap: {SITE}/sitemap.xml
""")

    print(f"wrote {len(seen)} pages + index into frontend/tools/")
    print(f"wrote sitemap.xml ({n_urls} URLs) and robots.txt")


if __name__ == "__main__":
    main()

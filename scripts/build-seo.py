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
SITE = "https://dockbench.app"
TODAY = date.today().isoformat()


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


def page(slug, title, description, h1, lede, body_html, faq, tool_name, related):
    """Render one landing page."""
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
            {"@type": "ListItem", "position": 1, "name": "Dockbench", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Tools", "item": SITE + "/tools/"},
            {"@type": "ListItem", "position": 3, "name": h1, "item": canonical},
        ],
    }
    related_html = "".join(
        f'<li><a href="{esc(r_slug)}.html">{esc(r_title)}</a></li>'
        for r_slug, r_title in related
    )
    faq_html = "".join(
        f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faq
    )
    deep_link = f"../index.html?tool={esc(tool_name)}"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}/icons/feature-graphic-1024x500.png">
<meta name="twitter:card" content="summary_large_image">
<link href="../vendor/fonts/fonts.css" rel="stylesheet">
<link href="../company/company.css" rel="stylesheet">
<script type="application/ld+json">{json.dumps(faq_ld)}</script>
<script type="application/ld+json">{json.dumps(breadcrumb_ld)}</script>
</head>
<body>
<header><div class="wrap"><a class="brand" href="../index.html"><span class="dot"></span>Dockbench</a></div></header>
<main><div class="wrap">
  <h1>{esc(h1)}</h1>
  <p class="lede">{esc(lede)}</p>

  <p><a class="cta" href="{deep_link}">Open {esc(tool_name)}</a></p>

  <div class="note">
    <strong>Your file never leaves this device.</strong> It is read, processed
    and saved back by your own browser — no upload, no account, no daily limit.
    Check it yourself: open developer tools, watch the Network tab, and use
    the tool. Nothing fires.
  </div>

{body_html}

  <h2>Common questions</h2>
{faq_html}

  <h2>Related tools</h2>
  <ul>{related_html}</ul>

  <p style="margin-top:26px;"><a class="cta" href="{deep_link}">Open {esc(tool_name)}</a>
     <a class="cta secondary" href="../index.html">See all 104 tools</a></p>
</div></main>
<footer class="site-footer"><div class="wrap">
  <nav>
    <a href="../index.html">Tools</a>
    <a href="../download.html">Download</a>
    <a href="index.html">All guides</a>
    <a href="../company/about.html">About</a>
    <a href="../company/pricing.html">Pricing</a>
    <a href="../company/privacy.html">Privacy</a>
    <a href="../company/terms.html">Terms</a>
  </nav>
  <p class="fine">Dockbench — PDF, image and video tools that run on your own device.</p>
</div></footer>
</body>
</html>
"""


def build_pairs(index):
    pages = []
    for src, dst, tool, extra in PAIRS:
        s_name, s_desc = FORMATS[src]
        d_name, d_desc = FORMATS[dst]
        slug = f"{src}-to-{dst}"
        title = f"{s_name} to {d_name} — free, no upload | Dockbench"
        h1 = f"Convert {s_name} to {d_name}"
        desc = f"Convert {s_name} to {d_name} free in your browser. No upload, no account, no watermark. {extra}"
        if len(desc) > 160:
            desc = f"Convert {s_name} to {d_name} free in your browser — no upload, no account, no watermark. {extra}"[:158].rsplit(" ", 1)[0] + "."
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

  <h2>Why this one is different</h2>
  <p>{esc(extra)} Most online converters upload your file to their server,
  process it there, and hand you a download link — which means your document
  sits on someone else's machine under a retention policy you have to take on
  faith. This one does the work in the browser you are already running.</p>
  <p>The practical differences: there is no daily limit, because each
  conversion costs us nothing. There is no upload wait, because there is no
  upload. And it keeps working with the network off.</p>
"""
        faq = [
            (f"Is this {s_name} to {d_name} converter really free?",
             "Yes, with no daily limit and no account. Your device does the work, so there is no per-use cost to pass on."),
            (f"Is my {s_name} file uploaded to a server?",
             "No. It is read by your browser, converted in memory, and saved back to your device. You can confirm this in the Network tab of your browser's developer tools."),
            (f"Will there be a watermark on the {d_name} file?",
             "No watermark is added."),
            ("What is the largest file I can convert?",
             "In a browser, around 2 GB — browsers cap a single buffer at roughly that. The desktop app streams from disk and handles far larger files."),
        ]
        related = [(f"{a}-to-{b}", f"{FORMATS[a][0]} to {FORMATS[b][0]}")
                   for a, b, _, _ in PAIRS
                   if (a, b) != (src, dst) and (a == src or b == dst)][:6]
        pages.append((slug, page(slug, title, desc, h1, lede, body, faq, tool, related)))
        index.append((slug, h1, desc, "Convert"))
    return pages


def build_tools(index, tool_names):
    pages = []
    for name in tool_names:
        slug = slugify(name)
        # Some tool names are long ("Describe a Photo / Alt-Text (On Your
        # Device)"). Trim the parenthetical for the title so it still fits
        # what search engines render, while the h1 keeps the full name.
        short = re.sub(r"\s*\([^)]*\)", "", name).strip()
        title = f"{short} — free, on-device | Dockbench"
        if len(title) > 68:
            title = f"{short[:52].rstrip()} — free | Dockbench"
        desc = (f"{name}, free in your browser. Runs on your own device — no upload, "
                f"no account, no daily limit. Works offline.")
        h1 = name
        lede = f"{name}, running entirely on your own device."
        body = f"""
  <h2>Using {esc(name)}</h2>
  <ol>
    <li>Open the tool.</li>
    <li>Choose your file, or drag it onto the page.</li>
    <li>Set the options you need.</li>
    <li>Download the result.</li>
  </ol>
  <h2>What happens to your file</h2>
  <p>Nothing leaves this device. The file is read with the browser's File API,
  processed in page memory, and handed back through the browser's own download
  mechanism. There is no request to send, because there is nothing to send.</p>
"""
        faq = [
            (f"Is {name} free?", "Yes — no account, no daily limit, no card."),
            ("Does it work offline?",
             "Yes. After the first visit the app is cached, so it keeps working with no connection."),
            ("Are my files uploaded?",
             "No. Everything happens in your browser, on your own device."),
        ]
        related = [(slugify(n), n) for n in tool_names if n != name][:6]
        pages.append((slug, page(slug, title, desc, h1, lede, body, faq, name, related)))
        index.append((slug, h1, desc, "Tools"))
    return pages


def build_questions(index):
    pages = []
    for slug, question, tool, answer in QUESTIONS:
        title = f"{question} | Dockbench"
        desc = f"{answer} Free, in your browser, with nothing uploaded."
        body = f"""
  <h2>The short answer</h2>
  <p>{esc(answer)}</p>
  <h2>Step by step</h2>
  <ol>
    <li>Open {esc(tool)}.</li>
    <li>Add your file — click, or drag it onto the page.</li>
    <li>Adjust anything you need to.</li>
    <li>Download the result.</li>
  </ol>
  <h2>Why not just use an online converter?</h2>
  <p>You can, but almost all of them upload your file first. For a bank
  statement, a passport scan or a contract, that means handing a copy to a
  company you know nothing about. This does the same job without the upload —
  which also means no queue, no size-limited free tier and no daily cap.</p>
"""
        faq = [
            ("Does this cost anything?", "No. There is no account, no limit and no card."),
            ("Is my file uploaded?", "No — it is processed by your own browser and never transmitted."),
            ("Does it work on a phone?", "Yes, and there is an Android app that works fully offline."),
        ]
        related = [(s, q) for s, q, _, _ in QUESTIONS if s != slug][:6]
        pages.append((slug, page(slug, title, desc, question, answer, body, faq, tool, related)))
        index.append((slug, question, desc, "Questions"))
    return pages


def extract_tool_names():
    """Read the real tool list out of the app, so these pages can never
    drift from what actually exists."""
    src = open(os.path.join(FRONTEND, "index.html")).read()
    names = re.findall(r"name:'([^']+)'", src)
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
<title>All tools and guides | Dockbench</title>
<meta name="description" content="Every Dockbench tool and conversion, with a guide for each. Free, on-device, no upload.">
<link rel="canonical" href="{SITE}/tools/">
<link href="../vendor/fonts/fonts.css" rel="stylesheet">
<link href="../company/company.css" rel="stylesheet">
</head>
<body>
<header><div class="wrap"><a class="brand" href="../index.html"><span class="dot"></span>Dockbench</a></div></header>
<main><div class="wrap">
  <h1>Every tool, and how to use it</h1>
  <p class="lede">{len(index)} pages covering every conversion and tool in
  Dockbench. All of them run on your own device.</p>
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
        seen[slug] = True
        with open(os.path.join(OUT_DIR, slug + ".html"), "w") as f:
            f.write(content)

    with open(os.path.join(OUT_DIR, "index.html"), "w") as f:
        f.write(build_index(index))

    sitemap, n_urls = build_sitemap(seen.keys())
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

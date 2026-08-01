"""
Per-tool page content for the generated /tools/*.html pages.

Why this file exists: every per-tool page used to share one template whose
only variable was the tool's name. Measured with 5-gram shingles, 39% of any
page was word-for-word identical to every other, and unrelated pairs — Age
Calculator against BMI Calculator — reached 83% similarity. That is the
shape Google's scaled-content-abuse policy targets, and "low value content"
is the single most common reason an AdSense application is rejected.

Every tool needs a real entry. scripts/build-seo.py raises if one is
missing, so a new tool cannot quietly ship a generic page.

Fields, all optional except intro/steps/notes/faq:
    intro  — 2-3 sentences: the problem, who hits it, what is specific here
    steps  — the real steps for THIS tool, not "open it, pick a file"
    notes  — a paragraph of genuine detail: limits, formats, how it works
    faq    — 3 (question, answer) pairs that only make sense for this tool
"""

CONTENT = {

# ---------------------------------------------------------------- PDF core

"Merge PDF": {
    "intro": "Combining PDFs is the job people most often reach for a paid "
             "tool to do, and it is also the one most often broken by page "
             "order — a scanned appendix ends up in front of the contract it "
             "belongs to. This merges in exactly the order you arrange the "
             "files, and lets you reorder before committing.",
    "steps": [
        "Add two or more PDFs, by clicking or dragging them in together.",
        "Drag the rows to set the order — the list is the final page order.",
        "Remove anything you added by mistake with the remove button on its row.",
        "Click Merge &amp; download. The combined file saves straight to your downloads.",
    ],
    "notes": "Bookmarks and page labels from each source are carried into the "
             "result where they exist. Merging does not re-encode anything: "
             "pages are copied object-by-object, so text stays selectable, "
             "images keep their original quality, and the output is usually "
             "close to the sum of the inputs rather than larger. Very large "
             "merges are limited by memory rather than file size — the page "
             "count is what matters, because the writer holds a page-tree "
             "entry for every page until it finishes.",
    "faq": [
        ("Does the order of the files matter?",
         "Yes — the list order is the page order in the result. Drag the rows "
         "to rearrange before you merge."),
        ("Will merging make the file bigger than the originals added together?",
         "Rarely. Pages are copied rather than re-encoded, and shared "
         "resources such as repeated fonts are written once."),
        ("How many PDFs can I combine at once?",
         "There is no imposed limit. In a browser the practical ceiling is "
         "memory: tens of thousands of pages will strain a phone long before "
         "a desktop."),
    ],
},

"Split PDF": {
    "intro": "Splitting is two different jobs that tools tend to conflate: "
             "pulling one section out of a long document, and breaking a "
             "document into its individual pages. Both are here, as separate "
             "modes, because picking the wrong one wastes a lot of time on a "
             "300-page file.",
    "steps": [
        "Choose the PDF. The page count appears once it has been read.",
        "Pick a mode: extract a page range, or one file per page.",
        "For a range, set the first and last page you want to keep.",
        "Click Split &amp; download — a single PDF for a range, or a .zip of "
        "numbered files for one-per-page.",
    ],
    "notes": "Page numbers are the ones printed in your viewer, counting from "
             "one. The one-file-per-page mode zero-pads its filenames to the "
             "width of the total, so page 7 of 200 becomes page-007.pdf and "
             "the files sort correctly in any file manager. Extracted pages "
             "keep their original size, rotation and embedded fonts.",
    "faq": [
        ("Can I take out several separate ranges at once?",
         "Not in one pass. Run the range mode once per section, or split into "
         "single pages and keep the ones you want."),
        ("Why are my files named page-001 rather than page-1?",
         "So they sort in the right order. Without padding, page-10 sorts "
         "before page-2 in most file managers."),
        ("Does splitting lose quality?",
         "No. Pages are copied whole, not re-rendered, so the extracted file "
         "is identical to those pages of the original."),
    ],
},

"Images to PDF": {
    "intro": "Turning a folder of photos into one document is the usual way "
             "people send receipts to an accountant or homework to a teacher. "
             "The awkward part is page size: photos come in whatever shape "
             "the camera produced, and a PDF wants consistent pages.",
    "steps": [
        "Add your images — JPG, PNG, WebP, GIF, BMP and HEIC all work.",
        "Reorder the rows so the pages come out in the sequence you want.",
        "Choose a page size: match each image exactly, or fit everything to "
        "A4 or US Letter.",
        "Click Convert &amp; download to get a single PDF, one image per page.",
    ],
    "notes": "Match-each-image produces pages the exact proportions of your "
             "photos, with no white borders — best for screenshots and "
             "receipts. A4 or Letter centres each image on a standard page "
             "and is what you want if anyone will print it. Formats the "
             "browser cannot hand directly to the PDF writer, such as WebP "
             "and HEIC, are decoded through a canvas first; JPG and PNG are "
             "embedded as-is, with no quality loss.",
    "faq": [
        ("Which image formats can I use?",
         "Anything your browser can decode: JPG, PNG, WebP, GIF, BMP, and "
         "HEIC on devices that support it. You can mix formats freely."),
        ("Why do my pages have white borders?",
         "You chose A4 or Letter, which fits the image onto a fixed page. "
         "Pick \"match each image\" for borderless pages."),
        ("Are animated GIFs supported?",
         "The first frame is used. A PDF page cannot animate."),
    ],
},

"PDF to JPG": {
    "intro": "Exporting pages as images is how you get a PDF into something "
             "that will not open one — a chat app, a slide, an image field on "
             "a form. The variable that matters is resolution, and most tools "
             "hide it.",
    "steps": [
        "Choose the PDF.",
        "Set the resolution. 150 DPI is fine on screen; 300 DPI is print "
        "quality and roughly four times the file size.",
        "Click Convert &amp; download.",
        "One page gives you a JPG; several pages give you a .zip of numbered "
        "images.",
    ],
    "notes": "Each page is rendered the way your PDF viewer would draw it, "
             "so vector text comes out crisp at whatever resolution you pick "
             "rather than being upscaled from a bitmap. Rendering is capped "
             "at 8192 pixels on the longest edge, which is a guard against "
             "decompression-bomb documents rather than a quality limit — you "
             "will only meet it at very high DPI on very large pages.",
    "faq": [
        ("What resolution should I choose?",
         "150 DPI for anything read on screen, 300 DPI if it will be printed. "
         "Above 300 the file grows quickly with little visible gain."),
        ("Can I export just one page?",
         "Run Split PDF first to pull out the page you want, then convert it."),
        ("Why is my text slightly soft?",
         "It was rendered at too low a DPI for the size you are viewing it "
         "at. Re-export at 300."),
    ],
},

"Rotate PDF": {
    "intro": "A PDF that opens sideways is almost always a scanner or phone "
             "that recorded the wrong orientation. Viewers let you turn the "
             "page on screen, but that setting is not saved — the next person "
             "to open it sees it sideways again. This writes the rotation "
             "into the file.",
    "steps": [
        "Choose the PDF.",
        "Pick 90° clockwise, 180°, or 90° anticlockwise.",
        "Click Rotate &amp; download.",
    ],
    "notes": "Rotation is stored as a page attribute, not by re-drawing the "
             "page, so nothing is re-encoded and the file size barely moves. "
             "Every page is turned by the same amount; if only some pages are "
             "sideways, use Organize PDF, which rotates pages individually.",
    "faq": [
        ("Why did my viewer's rotate button not stick?",
         "Most viewers rotate the display only and never write to the file. "
         "This changes the document itself, so it opens correctly everywhere."),
        ("Can I rotate only page 3?",
         "Not here — this turns every page. Organize PDF handles per-page "
         "rotation."),
        ("Does rotating reduce quality?",
         "No. It sets a flag on the page; the content is untouched."),
    ],
},

"Organize PDF": {
    "intro": "Most edits to a finished PDF are structural rather than "
             "textual: a page in the wrong place, a duplicate scan, a blank "
             "sheet the feeder pulled through. This shows every page as a "
             "thumbnail so you can fix all of that in one pass.",
    "steps": [
        "Choose the PDF. Every page is rendered as a thumbnail.",
        "Drag thumbnails to reorder, or use the per-page controls to rotate "
        "or delete.",
        "Check the running page count — it updates as you remove pages.",
        "Click Save &amp; download when the order looks right.",
    ],
    "notes": "Rotation here is per page, which is the difference between this "
             "and Rotate PDF: a scanned bundle where only the landscape pages "
             "came out sideways is fixed here. Deleted pages are removed from "
             "the output entirely rather than hidden, so the result really is "
             "smaller. Nothing is re-encoded — surviving pages are copied "
             "with their text, fonts and images intact.",
    "faq": [
        ("Can I get a deleted page back?",
         "Not after downloading — reload the original and start again. "
         "Nothing is stored, so there is no undo history to fall back on."),
        ("Is there a limit on page count?",
         "Thumbnails are rendered lazily, so long documents work, but a few "
         "hundred pages will feel slow on a phone."),
        ("Does reordering change the bookmarks?",
         "Bookmarks that point at moved pages follow them where the source "
         "document defines them by page object rather than page number."),
    ],
},

"Crop PDF": {
    "intro": "Cropping is what you need when a scan has a black border, a "
             "page has enormous margins that waste paper, or a slide deck "
             "printed with a footer nobody wants. It changes the visible "
             "area, not the content.",
    "steps": [
        "Choose the PDF. The first page is shown as a preview.",
        "Drag the crop handles to set the area you want to keep.",
        "Apply the same crop to every page, or only to the page you are on.",
        "Click Crop &amp; download.",
    ],
    "notes": "Cropping sets the page's CropBox, the rectangle a viewer draws. "
             "The content outside it is still in the file and can be revealed "
             "by re-cropping — this is a presentation change, not a "
             "redaction. If your intent is to remove sensitive material at "
             "the edge of a page, use Search &amp; Redact, which destroys the "
             "content rather than hiding it.",
    "faq": [
        ("Does cropping delete what is outside the box?",
         "No. It changes the visible area only. Use Search &amp; Redact if the "
         "material must actually be gone."),
        ("Will cropping shrink the file?",
         "Barely — the hidden content is still stored. Run Make PDF Smaller "
         "afterwards if size is the goal."),
        ("Can pages have different crops?",
         "Yes, if you apply the crop to the current page rather than all "
         "pages, then move to the next page and repeat."),
    ],
},

"Make PDF Smaller": {
    "intro": "Almost every request to shrink a PDF is caused by a limit "
             "someone else set — a 10 MB email cap, a 2 MB upload field on a "
             "government portal. Nearly all of that weight is images, so that "
             "is what this targets, with the result shown before you commit.",
    "steps": [
        "Choose the PDF.",
        "Pick a compression level. Stronger settings re-encode images at "
        "lower quality.",
        "Click Shrink &amp; download.",
        "Compare the before and after sizes shown in the log — if it is not "
        "small enough, try a stronger level.",
    ],
    "notes": "Text and vector graphics are never re-encoded, so they stay "
             "sharp at any setting; the savings come from embedded images. A "
             "text-only PDF may barely shrink at all, because there was "
             "nothing heavy in it to begin with — that is expected, not a "
             "failure. Scanned documents, which are images of pages, "
             "typically compress the most, often by 80% or more.",
    "faq": [
        ("Why did my file hardly shrink?",
         "It is probably mostly text. Compression works on images, and a "
         "text PDF has little to remove."),
        ("Will the text get blurry?",
         "No. Text and vectors are copied untouched; only images are "
         "re-encoded."),
        ("What if it is still too big for my upload limit?",
         "Try a stronger level, or Split by File Size to break it into parts "
         "under the cap."),
    ],
},

"Repair PDF": {
    "intro": "\"The file is damaged and could not be repaired\" usually means "
             "the cross-reference table — the index a reader uses to find "
             "objects — is wrong, while the actual pages are intact. That is "
             "recoverable, and it is what this does.",
    "steps": [
        "Choose the PDF your viewer refuses to open.",
        "Click Repair. The engine scans the file for real objects and rebuilds "
        "the index around them.",
        "If pages are found, download the rebuilt file.",
        "If the damage is genuinely unrecoverable, you are told so plainly.",
    ],
    "notes": "Repair runs qpdf compiled to WebAssembly, the same engine "
             "command-line users reach for. It reconstructs the "
             "cross-reference table by scanning for object headers, which "
             "recovers files truncated at the end, broken by a failed "
             "transfer, or written by buggy software. What it cannot do is "
             "invent data that was never written — a file cut off halfway "
             "through is missing those pages, and the tool says so rather "
             "than handing back something that silently lost content.",
    "faq": [
        ("It says the file is damaged past recovery. Is that final?",
         "For this file, yes — the content is not in it. Look for the "
         "original, or an email attachment or backup copy."),
        ("Will repairing change the pages?",
         "No. Recovered objects are written back as they were; only the index "
         "is rebuilt."),
        ("My PDF opens but shows errors. Is this worth running?",
         "Yes — rebuilding the index often clears warnings and makes the file "
         "behave in stricter readers."),
    ],
},

"OCR — Make Scans Searchable": {
    "intro": "A scanned page looks like text but is a photograph of text, "
             "which is why Ctrl+F finds nothing in it. OCR reads the shapes "
             "and produces real characters — and this runs the recognition on "
             "your own device, which matters because scans are usually the "
             "most sensitive documents people own.",
    "steps": [
        "Choose a scanned PDF or a photo of a page.",
        "Pick the output: selectable text, or a searchable PDF that looks "
        "identical but has a hidden text layer.",
        "Click Run OCR. The first run downloads the recognition engine, then "
        "works offline.",
        "Download the result.",
    ],
    "notes": "The searchable-PDF output keeps your original page image and "
             "draws the recognised words invisibly on top, positioned where "
             "they appear. The page looks exactly as it did, but text can be "
             "selected, copied and searched. Accuracy depends on the scan: "
             "300 DPI, straight, and evenly lit gives near-perfect results, "
             "while a phone photo at an angle in poor light will produce "
             "mistakes. Recognition happens entirely in your browser — no "
             "page image is uploaded.",
    "faq": [
        ("Why is the first run slow?",
         "The recognition engine and language model download once, around 15 "
         "MB. After that it is cached and works with no connection."),
        ("The text has mistakes. Can I improve it?",
         "Rescan at 300 DPI, keep the page flat and square to the camera, and "
         "get even lighting. OCR accuracy is mostly input quality."),
        ("Does the searchable PDF look different?",
         "No. The text layer is invisible and sits over your original image."),
    ],
},

"Scan Document": {
    "intro": "A phone photo of a page is not a scan: it is taken at an angle, "
             "lit unevenly, and surrounded by whatever your desk looks like. "
             "This finds the page edges, corrects the perspective, and "
             "flattens the lighting — the job a dedicated scanner app does, "
             "without installing one.",
    "steps": [
        "Point your camera at the page, or choose a photo you already took.",
        "Check the detected corners and drag any that landed wrong.",
        "Pick an output: colour, greyscale, or high-contrast black and white.",
        "Add more pages if you have them, then download the finished PDF.",
    ],
    "notes": "Corner detection looks for the strongest quadrilateral in the "
             "frame, so a page on a contrasting surface is found reliably "
             "while a white page on a white desk may need manual adjustment. "
             "The perspective correction maps your four corners onto a true "
             "rectangle, which is what removes the trapezoid look. "
             "High-contrast mode is the right choice for printed text: it "
             "drops the paper to pure white and typically cuts the file size "
             "by an order of magnitude compared with a colour photo.",
    "faq": [
        ("The corners were detected in the wrong place.",
         "Drag them onto the page corners yourself. Detection is a starting "
         "point, not the final answer."),
        ("Should I use colour or black and white?",
         "Black and white for printed text — smaller and sharper. Colour only "
         "if the page has photographs or coloured markings that matter."),
        ("Can I scan several pages into one PDF?",
         "Yes. Capture each page in turn; they are collected in order and "
         "saved as a single document."),
    ],
},

"Compare PDF": {
    "intro": "Finding what changed between two versions of a contract is "
             "slow and error-prone by eye, and the differences that matter "
             "are usually the small ones — a number, a date, a negation. "
             "This lines the two documents up and marks what moved.",
    "steps": [
        "Choose the original document.",
        "Choose the revised one.",
        "Click Compare. Differences are highlighted page by page.",
        "Read through the marked regions to see what was added or removed.",
    ],
    "notes": "Comparison works on the extracted text of each page, so it is "
             "reliable on documents with a real text layer and unreliable on "
             "scans, which have none — run those through OCR first. Because "
             "both files stay on your device, this is usable on material you "
             "could not upload to a comparison service, which is most of the "
             "material anyone actually needs to compare.",
    "faq": [
        ("Nothing was highlighted, but I know the documents differ.",
         "One of them is probably a scan with no text layer. Run OCR on it "
         "first, then compare."),
        ("Does it detect moved paragraphs?",
         "A moved block shows as a removal in one place and an addition in "
         "another, rather than as a single move."),
        ("Can I compare a PDF against a Word file?",
         "Convert the Word file to PDF first, then compare the two PDFs."),
    ],
},

"Remove Duplicate/Blank Pages": {
    "intro": "Documents that came from a sheet-feed scanner collect junk: "
             "the blank reverse of every single-sided page, and the "
             "occasional sheet that fed twice. Removing them by hand across "
             "two hundred pages is exactly the kind of task people give up "
             "on.",
    "steps": [
        "Choose the PDF.",
        "Let it analyse — each page is rendered and fingerprinted.",
        "Review what it flagged as blank or as a duplicate of an earlier page.",
        "Untick anything you want to keep, then download the cleaned file.",
    ],
    "notes": "\"Blank\" means visually blank rather than literally empty: a "
             "page with nothing but scanner speckle is still caught, because "
             "the test is how much ink is on the page rather than whether any "
             "objects exist. Duplicates are found by comparing rendered "
             "images, so a page scanned twice is detected even though the two "
             "scans are not byte-identical. Nothing is removed until you "
             "confirm — the flags are a proposal.",
    "faq": [
        ("It flagged a page that is not blank.",
         "Very light content can fall under the ink threshold. Untick it "
         "before downloading; nothing is removed without your confirmation."),
        ("Will it catch two scans of the same page?",
         "Yes. Detection compares the rendered appearance, not the file "
         "bytes, so near-identical rescans are found."),
        ("Does this change the remaining pages?",
         "No. Kept pages are copied unchanged."),
    ],
},

"Extract Images": {
    "intro": "Pulling the photographs out of a PDF is normally done by "
             "screenshotting them, which throws away resolution and quality. "
             "The images are stored inside the file at full size, and this "
             "takes them out as they were stored.",
    "steps": [
        "Choose the PDF.",
        "Click Extract. Every embedded image is found and listed.",
        "Download the .zip of everything it recovered.",
    ],
    "notes": "Images are read out of the page resource dictionaries rather "
             "than captured from a rendered page, which is the difference "
             "between getting the original file and getting a screenshot. "
             "JPEGs are written back as the original JPEG bytes, so nothing "
             "is re-encoded and no quality is lost. Other formats are "
             "converted to PNG, which is lossless. A page that looks like it "
             "contains a photo may contain several tiled fragments — that is "
             "how some tools write large images, and you will see them "
             "separately.",
    "faq": [
        ("I got more images than the page appeared to have.",
         "Large images are sometimes stored as tiles. The pieces are all "
         "there and can be reassembled."),
        ("Are the images the same quality as in the PDF?",
         "Yes for JPEGs, which come out byte-identical. Others are converted "
         "to PNG, which is lossless."),
        ("It found nothing in a document full of pictures.",
         "The pages are probably vector drawings rather than embedded "
         "photographs. Use PDF to JPG to render them instead."),
    ],
},

"Edit Metadata": {
    "intro": "A PDF carries a title, author, keywords and the name of the "
             "software that made it — and that metadata often says something "
             "you did not intend, like the previous client's name in a "
             "template you reused, or your full name on an anonymous "
             "submission.",
    "steps": [
        "Choose the PDF. The current metadata is shown.",
        "Edit the title, author, subject or keywords.",
        "Clear any field entirely to remove it.",
        "Click Save &amp; download.",
    ],
    "notes": "The document title is what most viewers show in the window bar "
             "and what many sites use as the default filename, so it is worth "
             "setting deliberately rather than leaving as \"Microsoft Word - "
             "draft3.docx\". If your aim is to remove everything rather than "
             "correct it, Sanitize PDF strips metadata along with embedded "
             "scripts and attachments in one pass.",
    "faq": [
        ("Where does a viewer show the title?",
         "In the window or tab, and often as the suggested filename when "
         "someone saves it. The visible first page is unrelated."),
        ("Does this remove hidden data too?",
         "It edits the standard document fields. Use Sanitize PDF to strip "
         "scripts, attachments and embedded metadata as well."),
        ("Can I clear a field completely?",
         "Yes — empty it and save. The entry is written out as blank."),
    ],
},

"Page Numbering & Document ID": {
    "intro": "Two different needs share one tool: page numbers for a "
             "document that will be printed or cited, and a fixed reference "
             "stamped on every page — a case number, a GST number, a Bates "
             "number for discovery.",
    "steps": [
        "Choose the PDF.",
        "Pick auto-counting numbers, or a fixed text that repeats on every "
        "page.",
        "Set the position, the starting number, and any prefix.",
        "Click Apply &amp; download.",
    ],
    "notes": "Bates numbering — a continuous sequence across a bundle, often "
             "with a prefix like ABC-000123 — is the standard in legal "
             "discovery, and the starting number matters because bundles "
             "continue from one another. Numbers are drawn into the page as "
             "real text, so they survive printing, copying and further "
             "conversion, and can be searched for later.",
    "faq": [
        ("Can I start at a number other than 1?",
         "Yes. Set the starting number — necessary when this bundle "
         "continues from a previous one."),
        ("Can I skip the cover page?",
         "Set the start so the first numbered page is the one you want, or "
         "split the cover off, number the rest, and merge them back."),
        ("Will the numbers survive printing?",
         "Yes. They are written into the page content, not added as an "
         "annotation layer."),
    ],
},

"Add Header & Footer": {
    "intro": "Headers and footers are what turn a stack of pages into a "
             "document someone can navigate: a title in the margin, a date, "
             "a confidentiality line that has to appear on every sheet.",
    "steps": [
        "Choose the PDF.",
        "Type the header text, the footer text, or both.",
        "Choose alignment and how far in from the edge it should sit.",
        "Click Apply &amp; download.",
    ],
    "notes": "The text is drawn inside the page margin, so it does not "
             "reflow or displace existing content — if your document already "
             "has very tight margins, increase the inset so the new text does "
             "not sit on top of what is there. It is added as real text "
             "rather than an image, so it prints crisply and can be found by "
             "a search.",
    "faq": [
        ("The footer overlaps my existing text.",
         "Increase the distance from the edge. The margin on that document is "
         "tighter than the default assumes."),
        ("Can the header differ on odd and even pages?",
         "Not in one pass. Split the document, apply each variant, and merge "
         "the pages back in order."),
        ("Can I include a page number here?",
         "Use Page Numbering &amp; Document ID for anything that counts; this "
         "tool repeats fixed text."),
    ],
},

"Put Multiple Pages on One Sheet": {
    "intro": "Printing a 40-page deck one slide per sheet wastes most of the "
             "paper and all of the ink. Putting two or four pages on each "
             "sheet is what handouts and reading copies are for, and doing it "
             "in the file rather than the print dialog means it looks the "
             "same wherever it is printed.",
    "steps": [
        "Choose the PDF.",
        "Pick 2 pages per sheet, or 4.",
        "Click Combine &amp; download.",
    ],
    "notes": "Pages are scaled to fit and arranged in reading order, so a "
             "2-up sheet reads left to right and a 4-up reads across then "
             "down. Because this rewrites the document rather than relying on "
             "printer settings, the layout is identical on every machine — "
             "useful when you are sending the file to someone else to print. "
             "Text stays vector, so it remains sharp despite being smaller.",
    "faq": [
        ("Will the text be too small to read?",
         "2-up on A4 is comfortable for most documents. 4-up suits slides "
         "with large type rather than dense prose."),
        ("Can I do this in the print dialog instead?",
         "Yes, but only on your own machine. Doing it in the file means "
         "anyone who prints it gets the same layout."),
        ("Does the original page order change?",
         "No. Pages are placed in reading order across each sheet."),
    ],
},

"Insert / Replace Page": {
    "intro": "Late corrections to a finished document are usually one page: "
             "a signature sheet that came back scanned, a corrected figure, a "
             "blank divider that needs to go in before printing. Rebuilding "
             "the whole file for that is overkill.",
    "steps": [
        "Choose the PDF you are amending.",
        "Pick a position, and whether you are inserting or replacing.",
        "Supply the new page — either a blank, or a page from another PDF.",
        "Click Apply &amp; download.",
    ],
    "notes": "Inserting shifts every following page along by one; replacing "
             "keeps the page count the same. Neither touches the pages around "
             "the change, so bookmarks and links elsewhere in the document "
             "survive. If you need to swap several pages, it is usually "
             "quicker to use Organize PDF, which shows the whole document at "
             "once.",
    "faq": [
        ("Does inserting renumber the rest?",
         "Physically, yes — pages after the insertion move along by one. "
         "Printed page numbers already on the pages do not change."),
        ("Can I insert several pages at once?",
         "One per pass here. For larger restructuring use Organize PDF."),
        ("Can I insert a page from a different document?",
         "Yes. Choose the source PDF and the page you want from it."),
    ],
},

"Split by Bookmark": {
    "intro": "A long report with a bookmark per chapter already contains the "
             "structure you want to split on. Finding the page each chapter "
             "starts at and splitting by hand repeats work the document has "
             "already done.",
    "steps": [
        "Choose the PDF.",
        "The bookmark outline is read and listed with its page numbers.",
        "Choose which outline level to split at.",
        "Download a .zip with one file per section, named after its bookmark.",
    ],
    "notes": "Splitting at the top level gives you chapters; going a level "
             "deeper gives sections within them, which is usually more files "
             "than anyone wants. Output files are named from the bookmark "
             "text with characters that filesystems dislike removed, so they "
             "arrive meaningfully named rather than as part-1, part-2. A "
             "document with no bookmarks cannot be split this way — use Split "
             "by File Size or a page range instead.",
    "faq": [
        ("It says there are no bookmarks.",
         "The document has no outline. Split PDF by page range, or Split by "
         "File Size, will do the job instead."),
        ("Which level should I split at?",
         "Top level for chapters. Deeper levels multiply the file count "
         "quickly."),
        ("What are the output files called?",
         "After their bookmark text, cleaned of characters that filesystems "
         "reject."),
    ],
},

"Split by File Size": {
    "intro": "Some limits are absolute: an email gateway that rejects "
             "anything over 10 MB, a portal that refuses more than 5. What "
             "you need is not a smaller document but several documents, each "
             "under the ceiling, with nothing lost.",
    "steps": [
        "Choose the PDF.",
        "Enter the maximum size each part may be.",
        "Click Split. Pages are accumulated until adding one more would cross "
        "the limit.",
        "Download the .zip of parts.",
    ],
    "notes": "Parts are built by measuring the real written size as pages are "
             "added, not by estimating from the page count, so a document "
             "with a few very heavy pages splits correctly rather than "
             "producing one oversized part. A single page larger than your "
             "limit cannot be split further — run Make PDF Smaller on the "
             "document first, then split the result.",
    "faq": [
        ("One part came out over my limit.",
         "A single page exceeded it on its own. Compress the document first, "
         "then split."),
        ("Are pages ever cut in half?",
         "No. Splitting happens between pages; every part contains whole "
         "pages."),
        ("Should I compress or split?",
         "Compress first — it often removes the problem. Split when the "
         "document is genuinely too large even compressed."),
    ],
},

"Bookmarks / TOC": {
    "intro": "A PDF's bookmark outline is the table of contents your viewer "
             "shows in the sidebar. It is worth inspecting before you rely on "
             "it, because plenty of documents that look structured have no "
             "outline at all.",
    "steps": [
        "Choose the PDF.",
        "The outline is read and shown as a tree with page numbers.",
        "Expand levels to see how deep the structure goes.",
    ],
    "notes": "This reads the outline rather than the visible contents page, "
             "which is why a document can have a printed table of contents "
             "and still show nothing here — they are unrelated. If there is "
             "an outline, Split by Bookmark can use it to break the document "
             "into sections automatically, which is usually the reason people "
             "check.",
    "faq": [
        ("It shows nothing, but the document has a contents page.",
         "A printed contents page is just text. The bookmark outline is "
         "separate data, and this document has none."),
        ("Can I edit the bookmarks here?",
         "This view is read-only. It tells you what structure exists."),
        ("What is this useful for?",
         "Checking whether Split by Bookmark will work, and seeing how a long "
         "document is organised before reading it."),
    ],
},

"Search & Redact": {
    "intro": "Drawing a black rectangle over a social security number does "
             "not remove it — the text is still in the file, and selecting "
             "over the box reveals it. Documents have been leaked exactly "
             "this way. This removes the content rather than covering it.",
    "steps": [
        "Choose the PDF.",
        "Pick what to find: social security numbers, emails, phone numbers, "
        "or your own search text.",
        "Review the matches it found on each page.",
        "Click Redact &amp; download.",
    ],
    "notes": "Redaction here is destructive by design. Each page is rendered "
             "with the sensitive regions painted out, and the page is rebuilt "
             "from that image — so the finished document has no text layer "
             "containing the redacted material, because it has no text layer "
             "at all. That is the trade: the result is not searchable, and it "
             "is genuinely safe to hand over. An automated test on every "
             "release confirms the removed value cannot be extracted from the "
             "output.",
    "faq": [
        ("Why is the redacted file no longer searchable?",
         "Because the pages were rebuilt as images. That is what guarantees "
         "the hidden text is gone rather than merely covered."),
        ("Is this safer than a black box in a PDF editor?",
         "Substantially. A drawn box leaves the text underneath it, where "
         "anyone can select or extract it."),
        ("Can I redact something the patterns miss?",
         "Yes — enter your own search text and it is treated the same way."),
    ],
},

"Flatten PDF": {
    "intro": "A filled form is still a form: the fields remain editable, and "
             "whoever receives it can change your answers. Flattening turns "
             "the filled values into permanent page content, which is what "
             "you want before sending a signed or completed document.",
    "steps": [
        "Choose the filled PDF.",
        "Click Flatten.",
        "Download the result — the values are now part of the page.",
    ],
    "notes": "Flattening draws each field's current value onto the page and "
             "removes the interactive field itself, so the document looks "
             "identical and can no longer be edited through the form layer. "
             "Do this after filling, never before — once flattened the fields "
             "are gone and cannot be filled again, so keep the blank original "
             "if you will need it.",
    "faq": [
        ("Can I unflatten it later?",
         "No. Keep the unfilled original if you need to produce more copies."),
        ("Does it change how the document looks?",
         "No. The values are drawn where the fields displayed them."),
        ("Does this stop someone editing the file altogether?",
         "It stops form editing. Anyone with a full PDF editor can still "
         "alter page content — add a password with Protect PDF if that "
         "matters."),
    ],
},

"Sanitize PDF": {
    "intro": "PDFs can carry more than pages: embedded JavaScript, attached "
             "files, launch actions, and metadata recording who made the "
             "document and with what. Before a document leaves your "
             "organisation, or arrives from outside it, that is worth "
             "removing.",
    "steps": [
        "Choose the PDF.",
        "Click Sanitize.",
        "Download the cleaned document.",
    ],
    "notes": "Embedded scripts and launch actions are the mechanism behind "
             "most PDF-borne malware, and almost no legitimate document needs "
             "them. Attachments — whole files hidden inside the PDF — are a "
             "common accidental disclosure. Metadata carrying an author name "
             "or the originating software is stripped in the same pass. The "
             "visible pages are untouched: the document looks exactly as it "
             "did.",
    "faq": [
        ("Will the pages look different?",
         "No. Only non-visible content is removed."),
        ("Should I run this on documents I receive?",
         "It is a reasonable habit for anything from an unknown sender, since "
         "it removes the active content malicious PDFs rely on."),
        ("Does it remove form fields?",
         "No. Use Flatten PDF for that."),
    ],
},

"Grayscale PDF": {
    "intro": "Converting to greyscale is usually about cost or consistency: "
             "a print shop charging per colour page, or a document that has "
             "to look the same coming out of any printer. It often shrinks "
             "the file substantially as a side effect.",
    "steps": [
        "Choose the PDF.",
        "Click Convert &amp; download.",
    ],
    "notes": "Every page is rendered and rewritten with colour information "
             "discarded, which is why the saving can be large on "
             "image-heavy documents. Because pages are re-rendered, the "
             "output is images rather than text — if you need the text to "
             "stay selectable, this is the wrong tool, and you should set "
             "greyscale in your printer driver instead. For documents heading "
             "to a print shop, that trade is usually worth making.",
    "faq": [
        ("Will the text still be selectable?",
         "No. Pages are re-rendered, so the result is images. Use your "
         "printer's greyscale setting if you need to keep the text layer."),
        ("How much smaller will it get?",
         "Colour photographs shrink a great deal; documents that were already "
         "mostly black text barely change."),
        ("Can I convert only some pages?",
         "Split the document, convert the pages you want, and merge them "
         "back."),
    ],
},

# ------------------------------------------------------------- conversion

"PDF to Word": {
    "intro": "People ask for Word because they want to edit, and a PDF is a "
             "description of how a page looks rather than a document with "
             "structure. Any conversion is therefore a reconstruction, and "
             "how good it is depends almost entirely on how the PDF was made.",
    "steps": [
        "Choose the PDF.",
        "Click Convert. Text is extracted in reading order and written into a "
        ".docx.",
        "Download and open it in Word, Google Docs, LibreOffice or Pages.",
    ],
    "notes": "A PDF exported from Word converts back well, because the text "
             "is present and in order. A scan converts to nothing, because "
             "there is no text to find — run OCR first. Complex multi-column "
             "layouts and tables are where reconstruction is hardest: the "
             "words come across, but the arrangement may not, and heavy "
             "formatting is usually faster to redo than to repair.",
    "faq": [
        ("The Word file came out empty.",
         "The PDF is a scan — an image of text with no text layer. Run OCR on "
         "it first, then convert."),
        ("Why did my table lose its layout?",
         "A PDF has no concept of a table; it draws lines and places text. "
         "Reconstruction is a best effort."),
        ("Which app should I open it in?",
         "Any of Word, Google Docs, LibreOffice or Pages will open the "
         ".docx."),
    ],
},

"PDF to Markdown": {
    "intro": "Markdown is what you want when the destination is a wiki, a "
             "static site, a README or a note-taking app — plain text with "
             "structure, and no formatting baggage from the original.",
    "steps": [
        "Choose the PDF.",
        "Click Convert. Headings, lists and emphasis are inferred from the "
        "layout.",
        "Download the .md file.",
    ],
    "notes": "Structure is inferred from visual cues, chiefly font size and "
             "weight: larger, bolder lines become headings, and lines "
             "beginning with bullets or numbers become lists. A document with "
             "consistent typographic hierarchy converts cleanly; one that "
             "styles headings by hand, at body size, gives the converter "
             "nothing to detect. Expect to fix a few heading levels by hand — "
             "that is normal and quick, and far less work than retyping.",
    "faq": [
        ("Why are some headings just paragraphs?",
         "They were not visually distinct in the PDF. Detection relies on "
         "size and weight."),
        ("Do images come across?",
         "No — Markdown references images rather than embedding them. Use "
         "Extract Images to pull them out separately."),
        ("Are tables preserved?",
         "Simple ones often are. Complex merged-cell tables usually need "
         "manual repair."),
    ],
},

"Markdown to PDF": {
    "intro": "Turning Markdown into something you can send means rendering "
             "it properly — headings, code blocks, tables and links laid out "
             "on paginated pages rather than a raw text dump.",
    "steps": [
        "Paste your Markdown, or choose a .md file.",
        "Watch the live preview as it renders.",
        "Click Download PDF.",
    ],
    "notes": "Standard Markdown is supported: headings, bold and italic, "
             "ordered and unordered lists, links, blockquotes, fenced code "
             "blocks and tables. Code blocks are set in a monospace face and "
             "kept together where they fit. Content is paginated properly "
             "rather than produced as one enormous page, so the result prints "
             "sensibly and reads correctly in any PDF viewer.",
    "faq": [
        ("Is syntax highlighting applied to code?",
         "Code is set in monospace and preserved exactly, without colouring."),
        ("Do tables work?",
         "Yes — standard pipe tables are rendered as real tables."),
        ("Can I control the page size?",
         "Output is A4 by default, which prints correctly on both A4 and "
         "Letter."),
    ],
},

"PDF to Text": {
    "intro": "Sometimes you want the words and nothing else — to paste "
             "somewhere, to search, to feed into another program. Plain text "
             "strips every trace of layout, which is exactly the point.",
    "steps": [
        "Choose the PDF.",
        "Click Extract.",
        "Download the .txt, or copy the text straight from the panel.",
    ],
    "notes": "Text comes out in reading order as the document defines it, "
             "which is reliable for ordinary single-column documents and less "
             "so for newspaper-style multi-column layouts, where the reading "
             "order recorded in the file may not match what your eye does. "
             "A scanned PDF yields nothing, because there is no text in it to "
             "extract — that is what OCR is for.",
    "faq": [
        ("I got an empty file.",
         "The PDF is a scan. Run OCR — Make Scans Searchable on it first."),
        ("The columns came out interleaved.",
         "Multi-column layouts store reading order in a way that does not "
         "always match the visual arrangement."),
        ("Is any formatting kept?",
         "None. This is plain text by design — use PDF to Word or PDF to "
         "Markdown if you want structure."),
    ],
},

"Word to PDF": {
    "intro": "Sending a Word file means trusting the recipient to have the "
             "same fonts, the same version and the same page setup. A PDF "
             "removes all three variables, which is why almost every formal "
             "submission asks for one.",
    "steps": [
        "Choose the .docx file.",
        "Click Convert.",
        "Download the PDF.",
    ],
    "notes": "The document is parsed and re-laid-out in your browser, "
             "carrying across headings, paragraph styling, lists, tables and "
             "images. Very heavily designed documents — complex text boxes, "
             "unusual float positioning, embedded objects from other Office "
             "applications — are where a browser-based conversion diverges "
             "most from Word's own rendering. Check anything critical before "
             "sending. If you need exact fidelity, the optional self-hosted "
             "backend renders through LibreOffice instead.",
    "faq": [
        ("Will it look exactly like it does in Word?",
         "Very close for ordinary documents. Complex layouts can shift — "
         "check before sending anything important."),
        ("Does it handle .doc as well as .docx?",
         "The modern .docx format is supported. Save older .doc files as "
         ".docx first."),
        ("Are fonts embedded?",
         "Standard fonts are embedded so the file renders the same "
         "everywhere."),
    ],
},

"HTML / Text to PDF": {
    "intro": "This is the quickest route from something you have as text or "
             "markup to a paginated document — an email you need to file, a "
             "receipt page, a block of notes that has to become an "
             "attachment.",
    "steps": [
        "Paste your HTML or plain text into the box.",
        "Check the preview.",
        "Click Download PDF.",
    ],
    "notes": "HTML is rendered with its inline styling applied, so headings, "
             "lists, tables and basic layout carry across. External "
             "stylesheets and remote images are not fetched — nothing on this "
             "page reaches the network — so paste self-contained markup for "
             "predictable results. Plain text is paginated with sensible "
             "margins rather than dumped onto a single page.",
    "faq": [
        ("My external CSS was ignored.",
         "Only inline styling is applied. Nothing is fetched from the "
         "network, by design."),
        ("Can I paste a whole web page?",
         "Yes, but images and stylesheets it links to will not load. Inline "
         "what matters."),
        ("Does plain text get sensible margins?",
         "Yes — it is paginated properly rather than run onto one long page."),
    ],
},

"Read PDF Aloud": {
    "intro": "Having a document read to you is useful for proofreading, for "
             "long reports you would rather listen to, and for anyone who "
             "finds reading on screen tiring. Your browser already has a "
             "speech engine; this points it at your PDF.",
    "steps": [
        "Choose the PDF.",
        "Pick a voice and reading speed.",
        "Press play, and pause or skip as you go.",
    ],
    "notes": "Speech uses the voices installed on your device, so what is "
             "available depends on your operating system rather than on this "
             "site — and nothing is sent anywhere to be synthesised. A "
             "scanned PDF has no text to read; run OCR on it first. "
             "Proofreading by ear is genuinely effective: a sentence that "
             "reads fine often sounds wrong.",
    "faq": [
        ("Why are there few voices?",
         "The list comes from your operating system. Installing more system "
         "voices adds them here."),
        ("Nothing is read from my document.",
         "It is probably a scan with no text layer. Run OCR first."),
        ("Can I download the audio?",
         "No — speech is generated live by the browser rather than rendered "
         "to a file."),
    ],
},

"Table to CSV": {
    "intro": "A table trapped in a PDF is data you cannot sort, sum or "
             "chart. Retyping it is the usual answer and the worst one. This "
             "detects the table structure and gives you rows and columns.",
    "steps": [
        "Choose the PDF and the page holding the table.",
        "Click Extract. Detected rows and columns are shown for checking.",
        "Download the .csv and open it in any spreadsheet.",
    ],
    "notes": "Detection uses the geometry of the page — where text sits "
             "relative to ruling lines and consistent column positions — so "
             "well-formed tables with clear alignment come out accurately. "
             "Merged cells, multi-line entries and tables without ruling "
             "lines are the hard cases, and are worth checking against the "
             "original before you rely on the numbers. A scanned table has no "
             "text to read; OCR it first.",
    "faq": [
        ("The columns came out misaligned.",
         "The table probably lacks consistent column positions or ruling "
         "lines. Check the preview and adjust the source if you can."),
        ("Can I extract tables from several pages at once?",
         "One page per pass. Run it for each page and combine the CSVs."),
        ("It found nothing on a page with a table.",
         "The page is likely a scan. Run OCR first, then extract."),
    ],
},

"PDF to PowerPoint": {
    "intro": "Turning a PDF deck back into editable slides is what you need "
             "when the original .pptx has been lost and the presentation has "
             "to be updated. Each page becomes a slide you can edit.",
    "steps": [
        "Choose the PDF.",
        "Click Convert.",
        "Download the .pptx and open it in PowerPoint, Keynote or Google "
        "Slides.",
    ],
    "notes": "This is one of the ten server-assisted tools: it needs a "
             "rendering engine too large to ship into a browser, so it "
             "appears only when a backend is configured and is clearly "
             "labelled server-assisted in the interface. Unlike the on-device "
             "tools, the file you submit is transmitted to that backend — "
             "which may be one you run yourself. Text becomes editable text "
             "boxes where it can be recovered; complex layouts arrive as "
             "positioned images.",
    "faq": [
        ("Why does this one need a server?",
         "It depends on an engine far too large to download into a browser. "
         "It is labelled server-assisted for that reason."),
        ("Is my file uploaded for this tool?",
         "Yes — unlike the on-device tools, this one transmits the file to "
         "the configured backend. That backend can be your own."),
        ("Will the slides be fully editable?",
         "Recovered text is editable. Graphics and complex arrangements come "
         "across as images."),
    ],
},

"PDF to Excel": {
    "intro": "Financial statements, invoices and reports arrive as PDFs and "
             "need to become spreadsheets. The difference between this and "
             "copy-paste is that it looks for table structure rather than "
             "dropping every line into column A.",
    "steps": [
        "Choose the PDF.",
        "Click Convert.",
        "Download the .xlsx and open it in Excel, Numbers or Google Sheets.",
    ],
    "notes": "Another of the ten server-assisted tools, for the same reason: "
             "reliable table detection across a whole document needs more "
             "than a browser can carry. It appears only with a backend "
             "configured, is labelled server-assisted, and does transmit your "
             "file. For a single table on a single page, Table to CSV runs "
             "entirely on your device and needs no backend at all — usually "
             "the better choice when that is all you need.",
    "faq": [
        ("Is there an on-device alternative?",
         "Yes — Table to CSV handles one table at a time entirely in your "
         "browser, with no upload."),
        ("Does each page become a sheet?",
         "Detected tables are written as sheets, so a multi-table document "
         "arrives as a workbook."),
        ("Is my file uploaded?",
         "Yes, for this tool. It is server-assisted and labelled as such."),
    ],
},

"PowerPoint to PDF": {
    "intro": "Sharing slides as a PDF stops the recipient seeing a different "
             "layout because they lack your fonts, and stops them editing the "
             "deck by accident. This one runs on your own device.",
    "steps": [
        "Choose the .pptx file.",
        "Click Convert.",
        "Download the PDF, one page per slide.",
    ],
    "notes": "Slides are parsed and rendered in your browser, one page per "
             "slide at the deck's own aspect ratio, so a 16:9 presentation "
             "does not arrive letterboxed on A4. Text, images and basic "
             "shapes carry across. Animations and transitions do not exist in "
             "a PDF and are dropped; slides render in their final state. "
             "Speaker notes are not included.",
    "faq": [
        ("What happens to animations?",
         "They are dropped — a PDF page is static. Slides appear in their "
         "final state."),
        ("Are speaker notes included?",
         "No. Only the slides themselves are rendered."),
        ("Is the aspect ratio preserved?",
         "Yes. A 16:9 deck produces 16:9 pages."),
    ],
},

"Excel to PDF": {
    "intro": "Spreadsheets are awkward to share because what the recipient "
             "sees depends on their window size, their zoom and their column "
             "widths. A PDF fixes the layout at the moment you sent it.",
    "steps": [
        "Choose the .xlsx file.",
        "Click Convert.",
        "Download the PDF.",
    ],
    "notes": "Cell values, formatting and column widths are rendered as the "
             "sheet defines them, with formulas shown as their computed "
             "results rather than the formula text. Very wide sheets are the "
             "perennial problem in any spreadsheet-to-PDF conversion: a "
             "40-column table has to go somewhere, and narrowing columns or "
             "setting a landscape print area in the source before converting "
             "gives a much better result than any converter can manage on "
             "your behalf.",
    "faq": [
        ("My wide sheet was cut off.",
         "Narrow the columns or set a landscape print area in the spreadsheet "
         "before converting."),
        ("Do formulas or results appear?",
         "Results — the same values the sheet displays."),
        ("Are all sheets in the workbook converted?",
         "Yes, in order, each starting on a new page."),
    ],
},

"PDF to PDF/A": {
    "intro": "PDF/A is the ISO archival format, and some institutions — "
             "courts, journals, government records offices — will not accept "
             "anything else. The requirement is that the file be readable "
             "decades from now without external dependencies.",
    "steps": [
        "Choose the PDF.",
        "Click Convert.",
        "Download the PDF/A-compliant file.",
    ],
    "notes": "Compliance mainly means self-containment: every font embedded "
             "rather than referenced, no encryption, no external links "
             "required to render the page, colour spaces defined explicitly. "
             "This is one of the ten server-assisted tools, because the "
             "validation and font-embedding machinery is too large for a "
             "browser — so it appears only with a backend configured and does "
             "transmit your file.",
    "faq": [
        ("Why does an archive need a special format?",
         "PDF/A forbids anything that might not resolve in future — "
         "unembedded fonts, external references, encryption."),
        ("Will it look different?",
         "No. The visible document is unchanged; what changes is what the "
         "file depends on."),
        ("Is my file uploaded?",
         "Yes. This is a server-assisted tool and is labelled as such."),
    ],
},

# ---------------------------------------------------------- edit and sign

"PDF Editor": {
    "intro": "Adding text to a finished PDF — a missing date, a reference "
             "number, a correction — normally means opening a paid editor. "
             "For placing text on a page, that is more tool than the job "
             "needs.",
    "steps": [
        "Choose the PDF and go to the page you want.",
        "Click where the text should go and type it.",
        "Adjust the size and position until it sits right.",
        "Click Save &amp; download.",
    ],
    "notes": "Text is drawn onto the page as real text, so it stays sharp at "
             "any zoom and can be selected and searched in the finished "
             "document. This adds to a page rather than reflowing it: "
             "existing content does not move to make room, which is what you "
             "want for filling gaps and wrong if you are trying to rewrite a "
             "paragraph. For that, convert to Word, edit, and convert back.",
    "faq": [
        ("Can I edit the text that is already there?",
         "No — this adds new text. To change existing wording, convert to "
         "Word, edit, and convert back."),
        ("Will the added text be selectable?",
         "Yes. It is written as real text, not an image."),
        ("Can I choose the font?",
         "A standard set is available, embedded so the file renders "
         "identically elsewhere."),
    ],
},

"Highlight Important Text": {
    "intro": "Marking up a document you are reviewing — the clause that "
             "matters, the figure that looks wrong — is what a highlighter "
             "pen does on paper. This does it on the page and saves it into "
             "the file.",
    "steps": [
        "Choose the PDF.",
        "Drag across the areas you want to mark.",
        "Pick a colour if the default does not suit.",
        "Click Save &amp; download.",
    ],
    "notes": "Highlights are drawn as translucent colour over the page, so "
             "the text beneath stays readable and, importantly, still "
             "selectable — this marks up a document, it does not obscure it. "
             "If your intent is to hide rather than emphasise, that is Search "
             "&amp; Redact, which destroys the content underneath instead.",
    "faq": [
        ("Can the person I send it to remove the highlights?",
         "They are part of the page content, so not easily. Keep an unmarked "
         "original if you need one."),
        ("Does highlighting hide anything?",
         "No — it is translucent, and the text stays readable. Use Search "
         "&amp; Redact to remove content."),
        ("Can I use different colours?",
         "Yes, chosen per highlight."),
    ],
},

"Add Watermark": {
    "intro": "A diagonal DRAFT or CONFIDENTIAL across every page is how you "
             "stop an interim version being mistaken for a final one, and how "
             "you mark ownership of something you are circulating.",
    "steps": [
        "Choose the PDF.",
        "Type the watermark text.",
        "Set the opacity, angle and size.",
        "Click Apply &amp; download.",
    ],
    "notes": "The mark is drawn into each page's content, not added as an "
             "annotation, so it survives printing, flattening and conversion "
             "and cannot be switched off in a viewer. Opacity is the setting "
             "that matters: high enough to be unmistakable, low enough to "
             "read through — around 20 to 30 per cent usually strikes it. "
             "Keep an unmarked original, because removing this cleanly "
             "afterwards is not possible.",
    "faq": [
        ("Can it be removed later?",
         "Not cleanly — it is part of the page. Keep the original."),
        ("What opacity should I use?",
         "20-30% is usually the balance between visible and readable."),
        ("Will it print?",
         "Yes. It is page content, not a viewer annotation."),
    ],
},

"Redact / Remove Watermark": {
    "intro": "Sometimes the thing you need gone is in the same place on every "
             "page — a watermark, a header from the system that generated the "
             "document, a stamp along one edge. This blanks a chosen area "
             "across the whole file.",
    "steps": [
        "Choose the PDF.",
        "Drag a box around the area to remove, on any page.",
        "Apply it to every page.",
        "Click Save &amp; download.",
    ],
    "notes": "The selected region is painted out and the page rebuilt from "
             "the result, so whatever was in that rectangle is gone rather "
             "than covered. That is also the limitation: this removes an "
             "area, not an object, so a watermark sitting diagonally across "
             "the text cannot be lifted off without taking the text with it. "
             "For finding and removing specific values wherever they occur, "
             "use Search &amp; Redact.",
    "faq": [
        ("Can it remove a diagonal watermark across the text?",
         "No. It clears a rectangular area, and that area would include the "
         "text underneath."),
        ("Is the content really gone?",
         "Yes. The region is destroyed, not covered."),
        ("What if what I want removed moves around?",
         "Use Search &amp; Redact, which finds values wherever they appear."),
    ],
},

"Sign PDF": {
    "intro": "Most documents that ask for a signature just need a visible "
             "one — a lease, a form, a letter of consent. Printing, signing "
             "and rescanning is the ritual people go through to avoid "
             "uploading a contract to a website. Here, nothing is uploaded.",
    "steps": [
        "Choose the PDF.",
        "Draw your signature with a mouse or finger, type it, or upload an "
        "image of it.",
        "Drag it onto the right spot and size it.",
        "Click Save &amp; download.",
    ],
    "notes": "This produces a visible signature, which is what the vast "
             "majority of documents ask for. It is not a cryptographic "
             "digital signature — that is a different thing, requiring a "
             "certificate from a trust provider, and is only needed where a "
             "recipient specifically demands it. The signature image is "
             "composited into the page, so it survives printing and cannot be "
             "dragged off in a viewer. Your contract never leaves the device, "
             "which is the entire reason to do it this way.",
    "faq": [
        ("Is this legally binding?",
         "In most jurisdictions an electronic signature is binding for "
         "ordinary agreements, but this is not legal advice — check what your "
         "document and country require."),
        ("Is it a digital certificate signature?",
         "No. It is a visible signature. Certificate-based signing needs a "
         "trust provider."),
        ("Can I reuse the same signature?",
         "Draw it once and save the image, then upload that image next time."),
    ],
},

"PDF Forms": {
    "intro": "A form with real fields should be fillable on screen. Often it "
             "will not open properly in a browser's built-in viewer, and the "
             "official advice becomes \"print it, write on it, scan it back\".",
    "steps": [
        "Choose the form PDF. Existing fields are detected and listed.",
        "Fill in the values.",
        "Save a filled copy that can still be edited, or flatten it so it "
        "cannot.",
    ],
    "notes": "Flattening is the step people forget. A filled but unflattened "
             "form still has live fields, and anyone receiving it can change "
             "your answers — which for anything signed or submitted is not "
             "what you want. Flatten before sending, and keep the unfilled "
             "original if you will need more copies. Forms without real "
             "fields are just pictures of forms; use PDF Editor to place text "
             "on those.",
    "faq": [
        ("No fields were found.",
         "The document has no interactive form — it only looks like one. Use "
         "PDF Editor to type onto it."),
        ("Should I flatten before sending?",
         "Yes, for anything final. Otherwise the recipient can edit your "
         "answers."),
        ("Can I fill it in more than once?",
         "Keep the blank original and fill a fresh copy each time."),
    ],
},

"Digital Stamp": {
    "intro": "APPROVED, PAID, RECEIVED — the rubber-stamp marks that route "
             "paper through an office still have a job in a digital workflow, "
             "and a clear stamp communicates status faster than a note in an "
             "email.",
    "steps": [
        "Choose the PDF.",
        "Pick a preset stamp or type your own text.",
        "Place it where it should sit and set the size.",
        "Click Apply &amp; download.",
    ],
    "notes": "Stamps are drawn into the page, so they print and survive "
             "conversion. Unlike a watermark, a stamp goes in one place at a "
             "chosen size rather than across every page — the two tools "
             "exist separately because the intent is different: a watermark "
             "marks the whole document's status, a stamp marks a point in a "
             "process. Adding the date alongside the stamp text is worth the "
             "extra second when the document will be filed.",
    "faq": [
        ("Can I stamp every page at once?",
         "Add Watermark is the tool for a mark on every page. This places one "
         "deliberately."),
        ("Can I use my own wording?",
         "Yes — the presets are shortcuts, not a fixed list."),
        ("Will it print?",
         "Yes. It becomes part of the page content."),
    ],
},

# ----------------------------------------------------------------- security

"Protect PDF": {
    "intro": "Password-protecting a document is the one job where uploading "
             "it to a website is most obviously self-defeating: you are "
             "sending the very file you are trying to secure to a stranger, "
             "unprotected, so they can protect it. This encrypts it on your "
             "own machine.",
    "steps": [
        "Choose the PDF.",
        "Set a password. Longer matters far more than more punctuation.",
        "Click Protect &amp; download.",
        "Test the result by opening it — you should be asked for the password.",
    ],
    "notes": "This is real AES-256 encryption, performed by qpdf compiled to "
             "WebAssembly and running in your browser — the same engine "
             "command-line users rely on, not a viewer flag that merely asks "
             "readers to behave. The file cannot be opened without the "
             "password by anyone, including us. That cuts both ways: there is "
             "no recovery, no reset and no back door, so a forgotten password "
             "means a lost document. Send the password by a different channel "
             "from the file.",
    "faq": [
        ("What if I forget the password?",
         "The document is unrecoverable. That is what real encryption means — "
         "there is no reset."),
        ("Is this the same as a viewer's 'restrict editing' setting?",
         "No. Those are requests readers can ignore. This is AES-256 "
         "encryption of the file's contents."),
        ("How should I send the password?",
         "Separately from the file — a message or a call, not the same email "
         "as the attachment."),
    ],
},

"Unlock PDF": {
    "intro": "Removing a password you know is a routine need: a bank "
             "statement that arrives encrypted with your date of birth, and "
             "which you now want to store or print without typing that in "
             "every time.",
    "steps": [
        "Choose the encrypted PDF.",
        "Enter the password you already know.",
        "Click Unlock &amp; download.",
    ],
    "notes": "This decrypts a document you can already open — it removes a "
             "password you hold, which is not the same as breaking one you do "
             "not. There is no cracking here and no attempt at it. Decryption "
             "runs on your device via the same qpdf engine used to encrypt, "
             "so a statement full of account numbers is never transmitted "
             "anywhere in order to be unlocked.",
    "faq": [
        ("Can it open a PDF whose password I do not have?",
         "No. It removes protection using the password you supply; it does "
         "not attempt to break encryption."),
        ("The password is rejected but I am sure it is right.",
         "Some documents have separate open and permissions passwords. The "
         "one needed here is the one that opens the file."),
        ("Is the file uploaded to be decrypted?",
         "No. Decryption happens in your browser."),
    ],
},

# -------------------------------------------------------------------- image

"Make Image Smaller": {
    "intro": "Photo file sizes have grown faster than the limits that "
             "constrain them: a modern phone shot is routinely 6 MB, and the "
             "form you are uploading it to wants under 1 MB. Quality is the "
             "dial, and you should be able to see what it costs.",
    "steps": [
        "Choose the image.",
        "Move the quality slider and watch the estimated size change.",
        "Compare the preview against the original.",
        "Download when the size is under your limit and it still looks right.",
    ],
    "notes": "Compression discards detail the eye is least likely to miss, so "
             "the honest way to choose is by looking rather than by trusting "
             "a percentage. Photographs tolerate aggressive settings well; "
             "screenshots, line art and anything with text or sharp edges "
             "show artefacts far sooner — for those, resizing the dimensions "
             "or converting to PNG is usually the better answer. Around 80 "
             "per cent quality is where most photographs stop looking any "
             "different.",
    "faq": [
        ("What quality setting should I pick?",
         "Around 80% is invisible on most photographs. Judge by the preview, "
         "not the number."),
        ("My screenshot looks blotchy.",
         "Sharp edges and text compress badly. Use PNG, or reduce the "
         "dimensions instead."),
        ("Is the original changed?",
         "No. You download a new file; the original on your device is "
         "untouched."),
    ],
},

"Resize Image": {
    "intro": "Resizing is about dimensions rather than file size, and it is "
             "what you need when something has an explicit pixel requirement "
             "— a profile picture, a product photo, an upload that rejects "
             "anything over 2000 pixels wide.",
    "steps": [
        "Choose the image. Its current dimensions are shown.",
        "Enter a width or a height.",
        "Keep the aspect ratio locked unless you deliberately want to "
        "distort it.",
        "Download the resized image.",
    ],
    "notes": "Reducing size is safe; enlarging is not. There is no additional "
             "detail in a small image to recover, so scaling up produces a "
             "soft, blocky result no matter what tool does it — start from "
             "the largest original you have. With the ratio locked, entering "
             "either dimension computes the other, which is almost always "
             "what you want: unlocking it stretches faces and logos in ways "
             "everyone notices.",
    "faq": [
        ("Can I make a small image bigger?",
         "You can, but it will look soft. The detail is not there to "
         "recover — always start from the largest original available."),
        ("Should I keep the aspect ratio?",
         "Almost always. Unlocking it distorts the image."),
        ("Does this reduce the file size too?",
         "Yes, as a side effect. Use Make Image Smaller if size is the actual "
         "goal."),
    ],
},

"Remove Background": {
    "intro": "Cutting a subject out of its background is the most requested "
             "photo edit there is, and until recently it meant either careful "
             "manual work or uploading the photo to a service. A real AI "
             "model now does it on your own device.",
    "steps": [
        "Choose the photo.",
        "Wait for the model on first use — it downloads once, then works "
        "offline.",
        "Check the cut-out edges in the preview.",
        "Download a PNG with a transparent background.",
    ],
    "notes": "The model is around 44 MB and downloads once, after which the "
             "tool works with no connection at all. It is strongest on "
             "clearly separated subjects — a person, a product against a "
             "contrasting background — and weakest on fine detail like "
             "flyaway hair or foliage, and on subjects the same colour as "
             "what is behind them. Output is PNG because transparency needs "
             "an alpha channel, which JPEG does not have.",
    "faq": [
        ("Why is the first use slow?",
         "The AI model downloads once, around 44 MB. After that it runs "
         "offline and instantly."),
        ("The edges around hair are rough.",
         "Fine strands are the hard case for any automatic cut-out. A plain, "
         "contrasting background helps a great deal."),
        ("Why is the result a PNG?",
         "Transparency requires an alpha channel. JPEG has none, so it cannot "
         "hold a cut-out."),
    ],
},

"Remove Photo Metadata (EXIF)": {
    "intro": "Photographs carry more than the picture. A phone image usually "
             "records exactly where it was taken, on what device, and at what "
             "moment — which is how a casually shared photo reveals a home "
             "address. This shows you what is there before removing it.",
    "steps": [
        "Choose the photo.",
        "Read what it actually contains — GPS coordinates, camera, date, "
        "sometimes an owner name.",
        "Click Strip.",
        "Download the cleaned image.",
    ],
    "notes": "Seeing the data first is the point: most people do not believe "
             "their photos carry coordinates until they see their own. "
             "Stripping rewrites the image without any metadata block, so the "
             "picture is pixel-for-pixel unchanged while the record of where "
             "and when it was taken is gone. Worth doing before posting "
             "anything taken at home, at a school, or anywhere you would not "
             "publish the address of.",
    "faq": [
        ("Do social networks not strip this already?",
         "Most do on upload — but not all, not on every path, and not when "
         "you send the file directly to someone."),
        ("Does stripping change how the photo looks?",
         "No. The image data is untouched; only the metadata block is "
         "removed."),
        ("Which fields are removed?",
         "All of them, including GPS, camera model, timestamps and any "
         "embedded owner or copyright fields."),
    ],
},

"Convert Image Format": {
    "intro": "Format choice is a trade between size, quality and "
             "transparency, and the right answer changes with the picture. "
             "Converting between JPG, PNG and WebP is a matter of knowing "
             "which trade you want.",
    "steps": [
        "Choose the image.",
        "Pick the output format.",
        "Set the quality if you chose a lossy format.",
        "Download the converted file.",
    ],
    "notes": "JPEG suits photographs and cannot hold transparency. PNG is "
             "lossless, keeps transparency, and is right for screenshots, "
             "logos and line art — but is large for photographs. WebP does "
             "both and is typically 25-35 per cent smaller than JPEG at "
             "matching quality, with support everywhere that matters now. "
             "Converting a JPEG to PNG will not restore detail already lost: "
             "it locks in the current quality at a larger size.",
    "faq": [
        ("Which format should I choose?",
         "WebP for the web, JPEG for maximum compatibility with photographs, "
         "PNG for anything with transparency or sharp edges."),
        ("Does converting JPEG to PNG improve quality?",
         "No. The detail is already gone; PNG only preserves what is left, at "
         "a larger size."),
        ("What happens to transparency going to JPEG?",
         "It is flattened onto white, because JPEG has no alpha channel."),
    ],
},

"Rotate / Flip Image": {
    "intro": "A photo that appears sideways usually has a correct orientation "
             "flag that some app ignored. Rotating and re-saving fixes it "
             "everywhere, rather than only where the flag is respected.",
    "steps": [
        "Choose the image.",
        "Rotate in 90° steps, or mirror horizontally or vertically.",
        "Check the live preview.",
        "Download the corrected image.",
    ],
    "notes": "Rotation is applied to the pixels and written out, so the "
             "result is correct in every viewer regardless of how it handles "
             "orientation metadata — which is the difference between this and "
             "rotating in a photo app that only updates the flag. Mirroring "
             "is genuinely useful for scanned negatives, photographs of "
             "handwriting taken through glass, and selfies that came out "
             "reversed.",
    "faq": [
        ("Why does my photo look sideways only in some apps?",
         "Those apps ignore the orientation flag. Rotating and re-saving "
         "fixes it everywhere."),
        ("Is quality lost when rotating?",
         "A 90° rotation is lossless in effect — no resampling is needed."),
        ("What is flipping for?",
         "Mirrored scans, photographs taken through glass, and reversed "
         "selfies."),
    ],
},

"Favicon Generator": {
    "intro": "A favicon is not one image. Browsers, phones and bookmark bars "
             "each want different sizes, and the tab icon that looks fine at "
             "64 pixels is often unreadable at 16.",
    "steps": [
        "Choose a square logo or image, ideally 512×512 or larger.",
        "Every required size is generated, including a multi-resolution .ico.",
        "Copy the HTML tags provided.",
        "Download the .zip and drop the files into your site root.",
    ],
    "notes": "The set covers the classic 16 and 32 pixel favicons, the "
             "180-pixel Apple touch icon, and the Android icons a web app "
             "manifest expects, plus a legacy .ico containing several sizes "
             "in one file. Detailed logos rarely survive the smallest sizes — "
             "a simple mark or a single letter reads far better in a tab than "
             "a shrunken wordmark, which is worth knowing before you generate "
             "anything.",
    "faq": [
        ("What source image should I start from?",
         "Square, 512×512 or larger. Simple marks work far better than "
         "detailed logos at small sizes."),
        ("Do I still need an .ico file?",
         "It is included for older browsers. Modern ones use the PNGs."),
        ("Where do the files go?",
         "Your site root, with the supplied HTML tags in the page head."),
    ],
},

"Passport & ID Photo Maker": {
    "intro": "Passport photo requirements are exact and unforgiving, and "
             "they differ by country: 35×45mm for the UK, 2×2 inches for the "
             "US, with rules about head height and background. Getting it "
             "wrong means the application comes back.",
    "steps": [
        "Choose a head-and-shoulders photo against a plain background.",
        "Pick the country and document type.",
        "Position the crop guides over the face as shown.",
        "Download a correctly sized photo, or a print sheet of several.",
    ],
    "notes": "Presets carry each country's official dimensions and the head "
             "sizing rules that go with them, which is the part people "
             "usually get wrong — the head has to occupy a specified "
             "proportion of the frame, not merely be centred. The print-sheet "
             "output tiles several copies onto a 4×6 for a photo kiosk, which "
             "is the cheapest way to get physical prints. Start from an "
             "evenly lit photo against a plain light background, facing the "
             "camera with a neutral expression.",
    "faq": [
        ("Will this be accepted officially?",
         "The dimensions and head sizing follow published specifications, but "
         "acceptance also depends on the photo itself — lighting, background, "
         "expression and no glare on glasses."),
        ("Can I print several at once?",
         "Yes. The print sheet tiles copies onto a 4×6 for a photo kiosk."),
        ("What background do I need?",
         "Plain and light, evenly lit, with no shadow behind the head."),
    ],
},

"Batch Resize / Shrink Many Photos": {
    "intro": "Processing photos one at a time is where free tools impose "
             "their limits — two a day, then a subscription. Since the work "
             "happens on your machine, there is no per-file cost to meter, so "
             "there is no meter.",
    "steps": [
        "Add as many images as you like, in one go.",
        "Set the dimensions or quality to apply to all of them.",
        "Run the batch and watch it progress.",
        "Download a .zip of the results.",
    ],
    "notes": "Images are processed one after another rather than all at once, "
             "which keeps memory flat and means a hundred photos work as "
             "reliably as five — it simply takes longer. The same settings "
             "apply to every file in the batch, so group photos that need "
             "different treatment into separate runs. Filenames are "
             "preserved so the output maps back onto the input.",
    "faq": [
        ("How many photos can I process at once?",
         "There is no imposed limit. They are handled one at a time, so large "
         "batches take longer rather than failing."),
        ("Can different photos get different settings?",
         "Not in one run — the batch shares settings. Split them into "
         "separate runs."),
        ("Are the filenames kept?",
         "Yes, so you can match outputs to inputs."),
    ],
},

"ID Card Designer": {
    "intro": "Making a staff or member card usually means either design "
             "software nobody has or a supplier with a minimum order. For a "
             "handful of cards at standard size, neither is proportionate.",
    "steps": [
        "Add the photo, name, title and ID number.",
        "Choose a layout and colours.",
        "Check the preview at actual card size.",
        "Download a print-ready file.",
    ],
    "notes": "Cards are produced at the standard CR80 size — 85.6 × 54 mm, "
             "the same as a bank card — so they fit every commercial holder "
             "and lanyard. Output is at print resolution rather than screen "
             "resolution, which matters because a card that looks fine on a "
             "monitor prints visibly soft if it was generated at 72 DPI. "
             "Photos are cropped to the portrait area automatically.",
    "faq": [
        ("What size are the cards?",
         "CR80, 85.6 × 54 mm — the standard bank-card size, so it fits "
         "ordinary holders."),
        ("Can I print these at home?",
         "Yes on card stock, though a print shop gives a better result on "
         "proper PVC blanks."),
        ("Can I make many at once?",
         "Batch ID Card Maker takes a list of names and produces one card per "
         "person."),
    ],
},

"Business Card Designer": {
    "intro": "Business cards are still the fastest way to hand over contact "
             "details, and the version with a QR code solves the part that "
             "always failed — the other person retyping your email wrongly.",
    "steps": [
        "Enter your name, title, company and contact details.",
        "Choose a layout.",
        "Add a QR code holding your contact details or a link.",
        "Download a print-ready file.",
    ],
    "notes": "Cards are produced at the standard 85 × 55 mm with room for a "
             "printer's bleed, so a commercial printer can trim them without "
             "cutting into the design. The QR code can carry a vCard, which "
             "phones offer to save directly into contacts — considerably "
             "better than a URL, because it works without a connection and "
             "without the recipient trusting a link.",
    "faq": [
        ("What should the QR code point to?",
         "A vCard is best — phones offer to save it straight into contacts, "
         "with no network needed."),
        ("Is it ready for a commercial printer?",
         "Yes. It is generated at print resolution with room for bleed."),
        ("What size are the cards?",
         "85 × 55 mm, the standard in most of the world."),
    ],
},

"Batch ID Card Maker": {
    "intro": "Making cards for a whole cohort — a conference, a school year, "
             "a shift roster — one at a time is the definition of work a "
             "computer should do. Paste the list, get the cards.",
    "steps": [
        "Paste your list of names, one per line, with any extra fields.",
        "Choose the card design once.",
        "Generate — one card per person.",
        "Download the .zip, or a single PDF laid out for printing.",
    ],
    "notes": "The design is chosen once and applied to every row, so a "
             "hundred cards are as much work as one. The combined PDF lays "
             "cards out several to a sheet with cutting margins, which is "
             "what you want for printing in bulk; the .zip of individual "
             "files suits card printers that feed blanks one at a time. "
             "Check one card carefully before generating the whole run — a "
             "misplaced field is much cheaper to fix before printing.",
    "faq": [
        ("What format should the list be in?",
         "One person per line. Extra fields separated consistently are "
         "mapped onto the card."),
        ("Can each card have its own photo?",
         "The batch flow is for text fields. Use ID Card Designer for "
         "individual cards with photos."),
        ("How should I print a large run?",
         "Use the combined PDF, which tiles cards with cutting margins."),
    ],
},

"Certificate / Award Maker": {
    "intro": "Certificates are needed in bursts — at the end of a course, "
             "after an event, at the close of a season — and always sooner "
             "than expected. A decent one takes minutes rather than a design "
             "brief.",
    "steps": [
        "Choose a template.",
        "Enter the recipient, the award, the date and the signatory.",
        "Adjust the border and colours.",
        "Download a print-ready PDF.",
    ],
    "notes": "Output is landscape A4 at print resolution, which is what "
             "certificate frames and folders are made for. Signature lines "
             "are left as lines to sign by hand — a printed signature on an "
             "award tends to look worse than an ink one, and signing is part "
             "of the ceremony. For a whole class, generate one, check it "
             "carefully, then repeat with each name.",
    "faq": [
        ("What paper should I print on?",
         "Heavier stock, 160gsm or above, makes a substantial difference to "
         "how a certificate feels."),
        ("Can I add a signature image?",
         "You can, though a hand-signed line usually looks better on an "
         "award."),
        ("What size is it?",
         "Landscape A4, which fits standard certificate frames."),
    ],
},

"Invoice Generator": {
    "intro": "Invoicing software is priced for businesses that invoice "
             "constantly. Freelancers and small suppliers often need a few a "
             "month, and the essential requirements are the same: line items "
             "that add up, tax shown correctly, and a number that makes the "
             "invoice traceable.",
    "steps": [
        "Enter your details and the client's.",
        "Add line items with quantities and rates — totals compute as you "
        "type.",
        "Set the tax rate, invoice number and payment terms.",
        "Download the finished PDF.",
    ],
    "notes": "Totals, tax and the grand total are calculated as you type, "
             "which removes the most common and most embarrassing error on a "
             "hand-made invoice. Nothing is stored — no account, no saved "
             "client list — so keep your own copy of every invoice you issue, "
             "and keep the numbering sequential, because a gap in an invoice "
             "sequence is the first thing an auditor asks about. What "
             "counts as a compliant invoice varies by country; check what "
             "yours requires.",
    "faq": [
        ("Are my invoices saved for next time?",
         "No — nothing is stored anywhere. Download and keep each one "
         "yourself."),
        ("Does it handle tax correctly?",
         "It applies the rate you set and shows it as a separate line. What "
         "your jurisdiction requires on the invoice is for you to confirm."),
        ("How should I number them?",
         "Sequentially, with no gaps. Missing numbers in a sequence attract "
         "questions."),
    ],
},

# -------------------------------------------------------------------- video

"Images to Slideshow Video": {
    "intro": "Photos become far more shareable as a video: social platforms "
             "favour it, it plays automatically, and a sequence with "
             "crossfades tells a story that a grid of thumbnails does not.",
    "steps": [
        "Add your photos in the order you want them shown.",
        "Set how long each image holds and how long the crossfade runs.",
        "Click Create and watch it render.",
        "Download the video.",
    ],
    "notes": "Frames are composited and encoded by your browser, so a long "
             "slideshow takes real time to render — roughly the length of the "
             "finished video. Around three to four seconds per image suits "
             "most viewing; faster feels rushed for photographs with detail "
             "in them. Mixing portrait and landscape images means one or the "
             "other gets letterboxed, so a consistent orientation looks "
             "considerably better.",
    "faq": [
        ("Why does rendering take so long?",
         "Each frame is composited and encoded on your device. Expect roughly "
         "the duration of the output video."),
        ("How long should each photo hold?",
         "Three to four seconds is comfortable. Shorter feels rushed."),
        ("Can I add music?",
         "Not here. Add an audio track in a video editor afterwards."),
    ],
},

"Video to GIF": {
    "intro": "GIFs remain the format that plays anywhere — in a chat, in a "
             "document, in an issue tracker — with no player and no controls. "
             "Most online converters watermark the result or cap the length; "
             "this does neither.",
    "steps": [
        "Choose the video.",
        "Set the start and end of the section you want.",
        "Choose a frame rate and size.",
        "Click Create and download the GIF.",
    ],
    "notes": "GIF is an old format with a hard limit of 256 colours per "
             "frame, which is why gradients and video footage can look "
             "banded — screen recordings and animation, with flat colour, "
             "convert beautifully. File size grows with dimensions, frame "
             "rate and duration together, so a 10-second clip at full "
             "resolution and 30fps becomes enormous. Halving the width and "
             "using 10-15fps usually keeps it recognisable at a fraction of "
             "the size.",
    "faq": [
        ("Why is my GIF so large?",
         "Size scales with dimensions, frame rate and length. Reduce the "
         "width and try 10-15fps."),
        ("Why does the colour look banded?",
         "GIF allows only 256 colours per frame. Screen recordings fare much "
         "better than filmed footage."),
        ("Is there a watermark or a length cap?",
         "Neither."),
    ],
},

"Trim Video": {
    "intro": "Cutting a clip down to the part that matters is the most "
             "common video edit there is, and installing an editor to remove "
             "thirty seconds from the start is disproportionate.",
    "steps": [
        "Choose the video.",
        "Drag the start and end handles to the section you want.",
        "Preview the selection.",
        "Click Trim and download the result.",
    ],
    "notes": "The selected section is re-encoded by your browser with the "
             "audio track kept in sync. Encoding happens in real time, so "
             "trimming a five-minute section takes around five minutes — a "
             "consequence of doing this on your own machine rather than "
             "handing the file to a server farm. The container format is "
             "chosen from what your browser can actually encode, which is why "
             "the output extension may differ from the input.",
    "faq": [
        ("Why does the output format differ from my input?",
         "The browser encodes into a container it supports. The content is "
         "the section you chose."),
        ("Is the audio kept?",
         "Yes, and kept in sync with the trimmed video."),
        ("Why does it take as long as the clip?",
         "It is encoded in real time on your device rather than on a server."),
    ],
},

"Screen Recorder": {
    "intro": "Recording a tab or a window is how you show a bug, demonstrate "
             "a workflow, or answer a question that would take four "
             "paragraphs to write. It needs no install, and the recording "
             "never leaves your machine.",
    "steps": [
        "Click record and choose a tab, a window, or the whole screen.",
        "Choose whether to include audio.",
        "Record what you need, then stop.",
        "Download the video file.",
    ],
    "notes": "The browser's own screen-capture permission handles this, so "
             "you choose exactly what is shared and a clear indicator shows "
             "while recording. The file is written locally and never "
             "transmitted — worth knowing when the recording is of internal "
             "software. Sharing a single tab rather than the whole screen "
             "avoids the classic accident of capturing notifications and "
             "whatever else is open.",
    "faq": [
        ("Can I record system audio as well as my microphone?",
         "Depends on the browser and platform. Chrome on desktop can capture "
         "tab audio when you share a tab."),
        ("Is the recording uploaded?",
         "No. It is written to your device and stays there."),
        ("Should I share a tab or the whole screen?",
         "A tab, unless you need more — it avoids capturing notifications."),
    ],
},

"Extract Audio from Video": {
    "intro": "Pulling the sound out of a video is what you need for a "
             "recorded talk you want to listen to, an interview to "
             "transcribe, or a soundtrack to reuse.",
    "steps": [
        "Choose the video.",
        "Click Extract.",
        "Download the audio file.",
    ],
    "notes": "Output is uncompressed WAV, which is deliberately the "
             "highest-quality option: it is the right input for transcription "
             "and for editing, because compressing already-compressed audio "
             "loses more each time. WAV is large — roughly 10 MB a minute — "
             "so convert to MP3 afterwards if you only want to listen to it. "
             "A video with no audio track produces nothing, and says so.",
    "faq": [
        ("Why WAV and not MP3?",
         "WAV is uncompressed, which is what transcription and editing want. "
         "Convert afterwards if you just want to listen."),
        ("Why is the file so big?",
         "Uncompressed audio is around 10 MB per minute."),
        ("Can I extract just part of it?",
         "Trim the video first, then extract from the trimmed clip."),
    ],
},

# ----------------------------------------------------------------- utility

"Ask PDF Love": {
    "intro": "Knowing what a tool is called is its own barrier. People do "
             "not think \"I need to compress a PDF\" — they think \"this is "
             "too big to email\". Describe the problem in your own words and "
             "this works out which tools solve it, in what order.",
    "steps": [
        "Type what you are trying to do, in ordinary language.",
        "Read the plan it proposes.",
        "Add your file once — it is carried between steps automatically.",
        "Work through the steps to the finished result.",
    ],
    "notes": "Multi-step requests are where this earns its place: \"make this "
             "small enough to email and black out the account number\" is two "
             "tools in a specific order, and the file passes from one to the "
             "next without you downloading and re-uploading between them. "
             "The matching runs on your device against the tool list — there "
             "is no language model call and nothing is sent anywhere.",
    "faq": [
        ("Does this send my question to an AI service?",
         "No. Matching happens in your browser against the tool list. Nothing "
         "is transmitted."),
        ("Can it chain several tools?",
         "Yes — that is the point. Your file carries through the steps "
         "without re-uploading."),
        ("What if it picks the wrong tool?",
         "Rephrase, or open the tool you wanted directly from the menu."),
    ],
},

"QR Code Generator": {
    "intro": "QR codes have become the default way to hand something over in "
             "the physical world — a menu, a wifi password, a payment link. "
             "Making one should not involve an account or a tracking redirect.",
    "steps": [
        "Type or paste the link or text.",
        "Set the size and error-correction level.",
        "Download as PNG for screens, or SVG for print.",
    ],
    "notes": "The code encodes your content directly, with no shortener and "
             "no redirect through anyone's server — so it keeps working "
             "forever and reports nothing about who scanned it. Higher error "
             "correction makes the code readable when partly obscured or "
             "printed on something that creases, at the cost of density: "
             "worth raising if a logo will sit over the middle. Use SVG for "
             "anything printed large, since it stays sharp at any size.",
    "faq": [
        ("Does the code expire or track scans?",
         "No. Your content is encoded directly, with no redirect service in "
         "between, so it works indefinitely and reports nothing."),
        ("PNG or SVG?",
         "PNG for screens and documents. SVG for print, because it stays "
         "sharp at any size."),
        ("What error correction should I use?",
         "Higher if the code will be small, creased, or partly covered by a "
         "logo."),
    ],
},

"QR Code Reader": {
    "intro": "Reading a QR code from a picture — a screenshot, a photo of a "
             "poster, a code embedded in a PDF — is awkward when the code is "
             "not in front of your camera. This decodes it from the image.",
    "steps": [
        "Choose the image containing the code.",
        "The code is found and decoded.",
        "Read the decoded content before you act on it.",
    ],
    "notes": "Seeing the destination before opening it is the security point: "
             "a QR code is opaque by design, and malicious codes rely on "
             "people scanning and tapping without ever reading the URL. "
             "Decoding happens in your browser, so the image is not sent "
             "anywhere. Codes that are blurred, at a steep angle, or "
             "partially obscured may not decode — crop to the code and try "
             "again.",
    "faq": [
        ("Why read a code instead of scanning it with my phone?",
         "Because you see the destination before opening it. Phone scanners "
         "often open the link immediately."),
        ("It could not find a code.",
         "Crop the image tightly around the code and retry. Blur and steep "
         "angles defeat decoding."),
        ("Is the image uploaded?",
         "No. Decoding happens in your browser."),
    ],
},

"Password Generator": {
    "intro": "The passwords people invent are guessable, and the ones "
             "generated by a website are only as trustworthy as that website. "
             "This uses your browser's cryptographic random number generator, "
             "and the result never leaves the page.",
    "steps": [
        "Choose a length — longer matters more than anything else.",
        "Pick which character types to include.",
        "Generate, and copy it straight into your password manager.",
    ],
    "notes": "Randomness comes from the browser's cryptographic generator, "
             "not from an ordinary random function, which is the difference "
             "between unpredictable and merely arbitrary. Length beats "
             "complexity: a long passphrase of ordinary words resists attack "
             "far better than a short string of symbols, and is far easier to "
             "type. Generated passwords are never transmitted, never logged "
             "and never stored — close the tab and it is gone, so put it in "
             "your password manager first.",
    "faq": [
        ("How long should a password be?",
         "16 characters or more for anything that matters. Length contributes "
         "more than punctuation does."),
        ("Is the password sent anywhere?",
         "No. It is generated in your browser and never leaves it."),
        ("Is this really random?",
         "It uses the browser's cryptographic random source, which is "
         "designed for exactly this."),
    ],
},

# ---------------------------------------------------------------- on-device AI

"AI Summarize (On Your Device)": {
    "intro": "Summarising with AI normally means pasting your document into "
             "someone else's service, which is precisely what you cannot do "
             "with a contract, a medical letter or an internal report. This "
             "runs a real model inside your browser.",
    "steps": [
        "Paste the text, or load a document.",
        "Wait for the model on first use — it downloads once.",
        "Choose how long the summary should be.",
        "Read or copy the result.",
    ],
    "notes": "The model downloads once and then runs entirely offline, so "
             "after the first use there is no connection involved and no text "
             "leaves the device. Being small enough to run in a browser, it "
             "is less capable than a large hosted model: it is good at "
             "condensing straightforward prose and weaker on highly technical "
             "or heavily structured documents. First use is slow while the "
             "model loads; afterwards it is quick.",
    "faq": [
        ("Is my text sent to a service?",
         "No. The model runs in your browser. After the initial download "
         "there is no network involved at all."),
        ("How does it compare to a large hosted model?",
         "Less capable — it has to fit in a browser. The trade is that your "
         "document stays with you."),
        ("Why is the first run slow?",
         "The model downloads and loads once, then is cached."),
    ],
},

"Translate Text (On Your Device)": {
    "intro": "Translation services read what you translate. For a personal "
             "letter, a legal document or anything commercially sensitive "
             "that is a genuine problem, and it is why people avoid "
             "translating exactly the documents they most need translated.",
    "steps": [
        "Paste the text.",
        "Choose the source and target language.",
        "Wait for the language model on first use.",
        "Read or copy the translation.",
    ],
    "notes": "Around ten languages are supported, each as a model that "
             "downloads once and then works offline. Quality is good for "
             "ordinary prose and weaker on idiom, wordplay and specialised "
             "terminology — as with any machine translation, have anything "
             "consequential checked by a person. The advantage here is not "
             "that it beats a hosted service on quality; it is that your text "
             "is never seen by anyone.",
    "faq": [
        ("Is my text uploaded to translate it?",
         "No. The model runs on your device and works offline once "
         "downloaded."),
        ("How good is it?",
         "Solid on ordinary prose, weaker on idiom and technical vocabulary. "
         "Have anything important reviewed by a person."),
        ("Which languages are available?",
         "Around ten major languages, each downloading its model on first "
         "use."),
    ],
},

"Voice to Text (On Your Device)": {
    "intro": "Dictation is faster than typing for most people, and speech "
             "recognition normally means streaming your voice to a server. "
             "For notes, interviews or anything confidential, doing it "
             "locally changes what you are willing to dictate.",
    "steps": [
        "Allow microphone access when asked.",
        "Wait for the model on first use.",
        "Speak — text appears as you go.",
        "Copy the transcript, or download it.",
    ],
    "notes": "Audio is processed by a model running in your browser and is "
             "never streamed anywhere. Accuracy rewards a decent microphone "
             "and a quiet room far more than careful enunciation; background "
             "noise and overlapping speakers are what defeat it. Punctuation "
             "generally needs adding afterwards, which is normal for "
             "dictation and quicker than typing the words themselves.",
    "faq": [
        ("Is my voice sent to a server?",
         "No. Recognition happens in your browser, and the audio never leaves "
         "your device."),
        ("How can I improve accuracy?",
         "A quiet room and a decent microphone help far more than speaking "
         "slowly."),
        ("Does it add punctuation?",
         "Only partly. Expect to add some afterwards."),
    ],
},

"Describe a Photo / Alt-Text (On Your Device)": {
    "intro": "Alt text is what a screen reader announces in place of an "
             "image, and it is skipped constantly because writing it for "
             "fifty pictures is tedious. A vision model can produce a solid "
             "first draft for each one.",
    "steps": [
        "Choose the image.",
        "Wait for the vision model on first use.",
        "Read the generated description.",
        "Edit it for your context, then copy it into your alt attribute.",
    ],
    "notes": "The model describes what is visibly in the picture, which is "
             "the right starting point but not the finished job: good alt "
             "text depends on why the image is there. The same photograph on "
             "a news article and in a product listing needs different text. "
             "Treat the output as a draft to sharpen, name people and places "
             "the model cannot know, and drop detail that does not serve the "
             "reader. Everything runs on your device, so the photos are not "
             "uploaded.",
    "faq": [
        ("Can I use the description unedited?",
         "Usually not. It describes what is visible; good alt text also "
         "reflects why the image is on the page."),
        ("How long should alt text be?",
         "A sentence is usually right. Purely decorative images should have "
         "an empty alt attribute instead."),
        ("Are my photos uploaded?",
         "No. The vision model runs in your browser."),
    ],
},

}

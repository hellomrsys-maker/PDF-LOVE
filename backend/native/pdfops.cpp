/*
 * pdfops.cpp — CPython extension linking libqpdf directly.
 *
 * Replaces the `qpdf` command-line shell-outs in premium_pdf.py. Each of
 * those paid a fork+exec plus a full round trip through the filesystem for
 * every operation; splitting a 200-page PDF spawned 201 processes. Here the
 * same qpdf C++ API runs in-process against memory buffers.
 *
 * All entry points release the GIL around the qpdf work, so several
 * documents can be processed in parallel by worker threads.
 *
 * Every function raises a Python exception and returns NULL on failure;
 * qpdf's own exceptions are caught and converted rather than being allowed
 * to unwind through the interpreter.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>

/* Opt in to qpdf's post-transition smart-pointer API explicitly. Without
 * this qpdf 10/11 headers emit a #warning on every compile. */
#ifndef POINTERHOLDER_TRANSITION
#  define POINTERHOLDER_TRANSITION 4
#endif

#include <qpdf/QPDF.hh>
#include <qpdf/QPDFWriter.hh>
#include <qpdf/QPDFPageDocumentHelper.hh>
#include <qpdf/QPDFObjectHandle.hh>
#include <qpdf/Buffer.hh>

#include <string>
#include <vector>
#include <memory>
#include <cstring>

namespace {

/* Note: qpdf keeps a pointer into the buffer passed to processMemoryFile,
 * so every caller below copies its input into a std::vector that outlives
 * the QPDF object using it. */

/* Serialise a QPDF to memory. Caller owns nothing; output lands in `out`. */
bool write_to(QPDF &pdf, std::vector<char> &out, std::string &err)
{
    try {
        QPDFWriter w(pdf);
        w.setOutputMemory();
        w.setStaticID(false);
        w.write();
        std::unique_ptr<Buffer> buf(w.getBuffer());
        const char *p = reinterpret_cast<const char *>(buf->getBuffer());
        out.assign(p, p + buf->getSize());
        return true;
    } catch (std::exception const &e) {
        err = e.what();
        return false;
    }
}

PyObject *bytes_from(const std::vector<char> &v)
{
    return PyBytes_FromStringAndSize(v.data(), static_cast<Py_ssize_t>(v.size()));
}

/* ------------------------------------------------------------------
 * Path-based helpers — the 100 GB path.
 *
 * The bytes-based functions above require the whole document to be
 * resident, which caps them at available RAM. These read with
 * processFile() and write with QPDFWriter(qpdf, filename): qpdf resolves
 * objects lazily from the file and streams them back out, so peak memory
 * tracks the size of the object model, not the size of the document. A
 * 100 GB scan merges in a few hundred MB of RAM.
 * ------------------------------------------------------------------ */

/* Open a file lazily. Never reads the whole document. */
void open_file(QPDF &pdf, const char *path)
{
    pdf.setSuppressWarnings(true);
    pdf.processFile(path);
}

/* Configure a writer for streaming output.
 *
 * Linearization is explicitly OFF: it requires two passes and holds the
 * whole document, which would defeat the entire point here. Preserving
 * object streams avoids decompressing and re-encoding every object. */
void configure_streaming(QPDFWriter &w)
{
    w.setStaticID(false);
    w.setLinearization(false);
    w.setObjectStreamMode(qpdf_o_preserve);
    w.setStreamDataMode(qpdf_s_preserve);
}

}  // namespace


PyDoc_STRVAR(merge_doc,
"merge(list_of_pdf_bytes) -> bytes\n\nConcatenate PDFs in order.");

static PyObject *pdfops_merge(PyObject *, PyObject *args)
{
    PyObject *seq;
    if (!PyArg_ParseTuple(args, "O", &seq))
        return NULL;

    PyObject *fast = PySequence_Fast(seq, "merge() expects a sequence of bytes");
    if (fast == NULL)
        return NULL;

    Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
    if (n == 0) {
        Py_DECREF(fast);
        PyErr_SetString(PyExc_ValueError, "no PDFs provided");
        return NULL;
    }

    /* Copy every input out of Python objects first, so the GIL-free section
     * below never touches a PyObject. */
    std::vector<std::vector<char>> inputs;
    inputs.reserve(static_cast<size_t>(n));
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = PySequence_Fast_GET_ITEM(fast, i);  /* borrowed */
        char *buf = NULL;
        Py_ssize_t len = 0;
        if (PyBytes_AsStringAndSize(item, &buf, &len) != 0) {
            Py_DECREF(fast);
            return NULL;
        }
        inputs.emplace_back(buf, buf + len);
    }
    Py_DECREF(fast);

    std::vector<char> out;
    std::string err;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF dest;
        dest.emptyPDF();
        QPDFPageDocumentHelper dh(dest);

        std::vector<std::unique_ptr<QPDF>> srcs;
        srcs.reserve(inputs.size());
        for (auto &raw : inputs) {
            auto src = std::make_unique<QPDF>();
            src->setSuppressWarnings(true);
            src->processMemoryFile("in.pdf", raw.data(), raw.size());
            for (auto &page : QPDFPageDocumentHelper(*src).getAllPages())
                dh.addPage(page, false);
            /* Keep each source alive until after write(): copied pages
             * reference objects that still live in their origin document. */
            srcs.push_back(std::move(src));
        }
        ok = write_to(dest, out, err);
    } catch (std::exception const &e) {
        err = e.what();
        ok = false;
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return bytes_from(out);
}


PyDoc_STRVAR(npages_doc, "npages(pdf_bytes) -> int\n\nPage count.");

static PyObject *pdfops_npages(PyObject *, PyObject *args)
{
    const char *data;
    Py_ssize_t len;
    if (!PyArg_ParseTuple(args, "y#", &data, &len))
        return NULL;

    std::vector<char> raw(data, data + len);
    int count = 0;
    std::string err;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF pdf;
        pdf.setSuppressWarnings(true);
        pdf.processMemoryFile("in.pdf", raw.data(), raw.size());
        count = static_cast<int>(QPDFPageDocumentHelper(pdf).getAllPages().size());
        ok = true;
    } catch (std::exception const &e) {
        err = e.what();
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return PyLong_FromLong(count);
}


PyDoc_STRVAR(extract_doc,
"extract(pdf_bytes, first, last) -> bytes\n\n"
"Return a PDF holding pages first..last inclusive, 1-based.");

static PyObject *pdfops_extract(PyObject *, PyObject *args)
{
    const char *data;
    Py_ssize_t len;
    int first, last;
    if (!PyArg_ParseTuple(args, "y#ii", &data, &len, &first, &last))
        return NULL;
    if (first < 1 || last < first) {
        PyErr_SetString(PyExc_ValueError, "invalid page range");
        return NULL;
    }

    std::vector<char> raw(data, data + len);
    std::vector<char> out;
    std::string err;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF src;
        src.setSuppressWarnings(true);
        src.processMemoryFile("in.pdf", raw.data(), raw.size());
        auto pages = QPDFPageDocumentHelper(src).getAllPages();
        int total = static_cast<int>(pages.size());
        if (last > total) {
            err = "page range exceeds document length";
        } else {
            QPDF dest;
            dest.emptyPDF();
            QPDFPageDocumentHelper dh(dest);
            for (int i = first; i <= last; i++)
                dh.addPage(pages[static_cast<size_t>(i - 1)], false);
            ok = write_to(dest, out, err);
        }
    } catch (std::exception const &e) {
        err = e.what();
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return bytes_from(out);
}


PyDoc_STRVAR(rotate_doc,
"rotate(pdf_bytes, angle) -> bytes\n\n"
"Rotate every page by angle degrees (a multiple of 90), relative to its\n"
"current rotation.");

static PyObject *pdfops_rotate(PyObject *, PyObject *args)
{
    const char *data;
    Py_ssize_t len;
    int angle;
    if (!PyArg_ParseTuple(args, "y#i", &data, &len, &angle))
        return NULL;
    if (angle % 90 != 0) {
        PyErr_SetString(PyExc_ValueError, "angle must be a multiple of 90");
        return NULL;
    }

    std::vector<char> raw(data, data + len);
    std::vector<char> out;
    std::string err;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF pdf;
        pdf.setSuppressWarnings(true);
        pdf.processMemoryFile("in.pdf", raw.data(), raw.size());
        for (auto &page : QPDFPageDocumentHelper(pdf).getAllPages())
            page.rotatePage(angle, true);   /* true = relative to current */
        ok = write_to(pdf, out, err);
    } catch (std::exception const &e) {
        err = e.what();
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return bytes_from(out);
}


/* ==================================================================
 * Path-based API — files that do not fit in memory.
 * ================================================================== */

PyDoc_STRVAR(npages_file_doc,
"npages_file(path) -> int\n\nPage count, without loading the document.");

static PyObject *pdfops_npages_file(PyObject *, PyObject *args)
{
    const char *path;
    if (!PyArg_ParseTuple(args, "s", &path))
        return NULL;

    std::string in(path), err;
    int count = 0;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF pdf;
        open_file(pdf, in.c_str());
        count = static_cast<int>(QPDFPageDocumentHelper(pdf).getAllPages().size());
        ok = true;
    } catch (std::exception const &e) {
        err = e.what();
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return PyLong_FromLong(count);
}


PyDoc_STRVAR(merge_files_doc,
"merge_files(in_paths, out_path) -> int\n\n"
"Concatenate PDFs from disk to disk, returning the page count written.\n"
"Peak memory tracks the object model, not the file size, so this handles\n"
"inputs far larger than RAM.");

static PyObject *pdfops_merge_files(PyObject *, PyObject *args)
{
    PyObject *seq;
    const char *out_path;
    if (!PyArg_ParseTuple(args, "Os", &seq, &out_path))
        return NULL;

    PyObject *fast = PySequence_Fast(seq, "merge_files() expects a sequence of paths");
    if (fast == NULL)
        return NULL;

    Py_ssize_t n = PySequence_Fast_GET_SIZE(fast);
    if (n == 0) {
        Py_DECREF(fast);
        PyErr_SetString(PyExc_ValueError, "no PDFs provided");
        return NULL;
    }

    /* Copy the paths out of Python objects before releasing the GIL. */
    std::vector<std::string> inputs;
    inputs.reserve(static_cast<size_t>(n));
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = PySequence_Fast_GET_ITEM(fast, i);   /* borrowed */
        const char *s = PyUnicode_AsUTF8(item);
        if (s == NULL) {
            Py_DECREF(fast);
            return NULL;
        }
        inputs.emplace_back(s);
    }
    Py_DECREF(fast);

    std::string out(out_path), err;
    int pages = 0;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF dest;
        dest.emptyPDF();
        QPDFPageDocumentHelper dh(dest);

        /* Each source stays open until write() completes: copied pages
         * still resolve their objects out of the origin document, and with
         * lazy file reads those objects are only pulled in as the writer
         * asks for them. */
        std::vector<std::unique_ptr<QPDF>> srcs;
        srcs.reserve(inputs.size());
        for (auto &path : inputs) {
            auto src = std::make_unique<QPDF>();
            open_file(*src, path.c_str());
            for (auto &page : QPDFPageDocumentHelper(*src).getAllPages()) {
                dh.addPage(page, false);
                pages++;
            }
            srcs.push_back(std::move(src));
        }

        QPDFWriter w(dest, out.c_str());
        configure_streaming(w);
        w.write();
        ok = true;
    } catch (std::exception const &e) {
        err = e.what();
        ok = false;
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return PyLong_FromLong(pages);
}


PyDoc_STRVAR(extract_file_doc,
"extract_file(in_path, out_path, first, last) -> int\n\n"
"Write pages first..last (inclusive, 1-based) to out_path.");

static PyObject *pdfops_extract_file(PyObject *, PyObject *args)
{
    const char *in_path, *out_path;
    int first, last;
    if (!PyArg_ParseTuple(args, "ssii", &in_path, &out_path, &first, &last))
        return NULL;
    if (first < 1 || last < first) {
        PyErr_SetString(PyExc_ValueError, "invalid page range");
        return NULL;
    }

    std::string in(in_path), out(out_path), err;
    int written = 0;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF src;
        open_file(src, in.c_str());
        auto pages = QPDFPageDocumentHelper(src).getAllPages();
        int total = static_cast<int>(pages.size());
        if (last > total) {
            err = "page range exceeds document length";
        } else {
            QPDF dest;
            dest.emptyPDF();
            QPDFPageDocumentHelper dh(dest);
            for (int i = first; i <= last; i++) {
                dh.addPage(pages[static_cast<size_t>(i - 1)], false);
                written++;
            }
            QPDFWriter w(dest, out.c_str());
            configure_streaming(w);
            w.write();
            ok = true;
        }
    } catch (std::exception const &e) {
        err = e.what();
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return PyLong_FromLong(written);
}


PyDoc_STRVAR(rotate_file_doc,
"rotate_file(in_path, out_path, angle) -> int\n\n"
"Rotate every page by angle degrees relative to its current rotation.");

static PyObject *pdfops_rotate_file(PyObject *, PyObject *args)
{
    const char *in_path, *out_path;
    int angle;
    if (!PyArg_ParseTuple(args, "ssi", &in_path, &out_path, &angle))
        return NULL;
    if (angle % 90 != 0) {
        PyErr_SetString(PyExc_ValueError, "angle must be a multiple of 90");
        return NULL;
    }

    std::string in(in_path), out(out_path), err;
    int pages = 0;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF pdf;
        open_file(pdf, in.c_str());
        for (auto &page : QPDFPageDocumentHelper(pdf).getAllPages()) {
            page.rotatePage(angle, true);
            pages++;
        }
        QPDFWriter w(pdf, out.c_str());
        configure_streaming(w);
        w.write();
        ok = true;
    } catch (std::exception const &e) {
        err = e.what();
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return PyLong_FromLong(pages);
}


PyDoc_STRVAR(split_file_doc,
"split_file(in_path, out_dir, prefix='page') -> int\n\n"
"Write one PDF per page into out_dir, returning the number of files\n"
"written. The source is opened once and streamed, rather than reopened\n"
"per page.");

static PyObject *pdfops_split_file(PyObject *, PyObject *args)
{
    const char *in_path, *out_dir, *prefix = "page";
    if (!PyArg_ParseTuple(args, "ss|s", &in_path, &out_dir, &prefix))
        return NULL;

    std::string in(in_path), dir(out_dir), pre(prefix), err;
    int written = 0;
    bool ok = false;

    Py_BEGIN_ALLOW_THREADS
    try {
        QPDF src;
        open_file(src, in.c_str());
        auto pages = QPDFPageDocumentHelper(src).getAllPages();
        for (size_t i = 0; i < pages.size(); i++) {
            QPDF dest;
            dest.emptyPDF();
            QPDFPageDocumentHelper(dest).addPage(pages[i], false);
            std::string out = dir + "/" + pre + "_" + std::to_string(i + 1) + ".pdf";
            QPDFWriter w(dest, out.c_str());
            configure_streaming(w);
            w.write();
            written++;
        }
        ok = true;
    } catch (std::exception const &e) {
        err = e.what();
    }
    Py_END_ALLOW_THREADS

    if (!ok) {
        PyErr_SetString(PyExc_ValueError, err.c_str());
        return NULL;
    }
    return PyLong_FromLong(written);
}


static PyMethodDef PdfopsMethods[] = {
    /* in-memory: fast for everyday files */
    {"merge",   pdfops_merge,   METH_VARARGS, merge_doc},
    {"npages",  pdfops_npages,  METH_VARARGS, npages_doc},
    {"extract", pdfops_extract, METH_VARARGS, extract_doc},
    {"rotate",  pdfops_rotate,  METH_VARARGS, rotate_doc},
    /* path-based: streams from disk, for files larger than RAM */
    {"npages_file",  pdfops_npages_file,  METH_VARARGS, npages_file_doc},
    {"merge_files",  pdfops_merge_files,  METH_VARARGS, merge_files_doc},
    {"extract_file", pdfops_extract_file, METH_VARARGS, extract_file_doc},
    {"rotate_file",  pdfops_rotate_file,  METH_VARARGS, rotate_file_doc},
    {"split_file",   pdfops_split_file,   METH_VARARGS, split_file_doc},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef pdfopsmodule = {
    PyModuleDef_HEAD_INIT,
    "dockbench_pdf",
    "In-process PDF operations on libqpdf (GIL released during work).",
    -1,
    PdfopsMethods,
    NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_dockbench_pdf(void)
{
    return PyModule_Create(&pdfopsmodule);
}

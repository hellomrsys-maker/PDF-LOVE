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


static PyMethodDef PdfopsMethods[] = {
    {"merge",   pdfops_merge,   METH_VARARGS, merge_doc},
    {"npages",  pdfops_npages,  METH_VARARGS, npages_doc},
    {"extract", pdfops_extract, METH_VARARGS, extract_doc},
    {"rotate",  pdfops_rotate,  METH_VARARGS, rotate_doc},
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

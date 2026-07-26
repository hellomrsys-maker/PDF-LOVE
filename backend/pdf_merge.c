#include <Python.h>
#include <qpdf/QPDF.hh>
#include <qpdf/QPDFWriter.hh>
#include <qpdf/QUtil.hh>
#include <vector>
#include <string>

// Helper to convert Python list of strings to std::vector<std::string>
static std::vector<std::string> pylist_to_vector(PyObject* pylist) {
    std::vector<std::string> result;
    if (!PyList_Check(pylist)) {
        return result;
    }
    Py_ssize_t len = PyList_Size(pylist);
    for (Py_ssize_t i = 0; i < len; ++i) {
        PyObject* item = PyList_GetItem(pylist, i); // borrowed reference
        if (PyUnicode_Check(item)) {
            PyObject* bytes = PyUnicode_AsEncodedString(item, "utf-8", "strict");
            if (bytes) {
                const char* path = PyBytes_AS_STRING(bytes);
                result.emplace_back(path);
                Py_DECREF(bytes);
            }
        }
    }
    return result;
}

static PyObject* merge_pdfs(PyObject* self, PyObject* args) {
    PyObject* pylist;
    if (!PyArg_ParseTuple(args, "O", &pylist)) {
        return NULL;
    }
    std::vector<std::string> input_paths = pylist_to_vector(pylist);
    if (input_paths.empty()) {
        PyErr_SetString(PyExc_ValueError, "No input PDF paths provided");
        return NULL;
    }
    // Create a temporary output file
    std::string out_path = QUtil::generate_filename("merged_", ".pdf");
    QPDFWriter writer(out_path.c_str());
    writer.setNewlineBeforeEndstream(true);

    for (const auto& path : input_paths) {
        try {
            QPDF src(path.c_str(), "");
            const std::vector<QPDFPageObjectHelper> pages = src.getAllPages();
            for (const auto& page : pages) {
                writer.addPage(page);
            }
        } catch (const std::exception& e) {
            PyErr_SetString(PyExc_RuntimeError, e.what());
            return NULL;
        }
    }
    writer.write();
    // Return output path to Python
    return PyUnicode_FromString(out_path.c_str());
}

static PyMethodDef PdfMergeMethods[] = {
    {"merge_pdfs", (PyCFunction)merge_pdfs, METH_VARARGS, "Merge PDFs given a list of file paths and return output path"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef pdfmergemodule = {
    PyModuleDef_HEAD_INIT,
    "pdf_merge",
    "Zero-bridge PDF merge implemented in C using libqpdf",
    -1,
    PdfMergeMethods
};

PyMODINIT_FUNC PyInit_pdf_merge(void) {
    return PyModule_Create(&pdfmergemodule);
}

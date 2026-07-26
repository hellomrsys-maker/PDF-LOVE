/*
 * imgprocmodule.c — CPython extension wrapper around the scan-cleanup
 * kernel in imgproc.c.
 *
 * This replaces the previous ctypes binding. The difference that matters is
 * not syntax, it is these two things:
 *
 *   1. One call instead of four. ctypes crossed the FFI boundary once per
 *      kernel function (gray_and_hist -> build_lut -> apply_lut), converting
 *      arguments each time. Here the whole pipeline runs behind a single
 *      call.
 *   2. The GIL is released around the pixel work. Under ctypes the
 *      interpreter lock was held for the entire operation, so two pages of a
 *      scanned PDF could never binarize at the same time no matter how many
 *      cores the box had. With Py_BEGIN_ALLOW_THREADS, N worker threads
 *      genuinely run on N cores.
 *
 * imgproc.c itself deliberately does not include Python.h — it stays pure,
 * portable C that compiles and tests standalone under -Wall -Wextra -Werror.
 * This file is the only part that knows about the interpreter.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

/* Implemented in imgproc.c */
void gray_and_hist(const uint8_t *src, uint8_t *dst, size_t npixels,
                   int channels, uint64_t *hist);
void hist_only(const uint8_t *gray, size_t npixels, uint64_t *hist);
int  build_lut(const uint64_t *hist, size_t npixels, int p_low, int p_high,
               uint8_t *lut);
void apply_lut(uint8_t *gray, size_t npixels, const uint8_t *lut);

PyDoc_STRVAR(enhance_doc,
"enhance(pixels, width, height, channels, p_low=5, p_high=995) -> bytes\n"
"\n"
"Run the full scan-cleanup pipeline (grayscale -> percentile contrast\n"
"stretch -> inverted-scan correction -> Otsu binarization) and return the\n"
"cleaned single-band image as bytes of length width*height.\n"
"\n"
"channels must be 1 (already grayscale), 3 (RGB) or 4 (RGBA).");

static PyObject *
imgproc_enhance(PyObject *self, PyObject *args)
{
    Py_buffer src;
    int width, height, channels;
    int p_low = 5, p_high = 995;

    (void)self;

    if (!PyArg_ParseTuple(args, "y*iii|ii", &src, &width, &height,
                          &channels, &p_low, &p_high))
        return NULL;

    if (width <= 0 || height <= 0) {
        PyBuffer_Release(&src);
        return PyErr_Format(PyExc_ValueError,
                            "width and height must be positive (got %d x %d)",
                            width, height);
    }
    if (channels != 1 && channels != 3 && channels != 4) {
        PyBuffer_Release(&src);
        return PyErr_Format(PyExc_ValueError,
                            "channels must be 1, 3 or 4 (got %d)", channels);
    }

    /* Overflow-safe pixel count, then verify the buffer really holds it —
     * a short buffer here would be an out-of-bounds read in the kernel. */
    if ((size_t)width > SIZE_MAX / (size_t)height) {
        PyBuffer_Release(&src);
        PyErr_SetString(PyExc_ValueError, "image dimensions overflow");
        return NULL;
    }
    size_t npixels = (size_t)width * (size_t)height;
    if (npixels > SIZE_MAX / (size_t)channels) {
        PyBuffer_Release(&src);
        PyErr_SetString(PyExc_ValueError, "image dimensions overflow");
        return NULL;
    }
    if ((size_t)src.len < npixels * (size_t)channels) {
        PyBuffer_Release(&src);
        return PyErr_Format(PyExc_ValueError,
                            "buffer holds %zd bytes, need %zu for %dx%d x%d",
                            src.len, npixels * (size_t)channels,
                            width, height, channels);
    }

    PyObject *out = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)npixels);
    if (out == NULL) {
        PyBuffer_Release(&src);
        return NULL;
    }
    uint8_t *dst = (uint8_t *)PyBytes_AS_STRING(out);

    uint64_t hist[256];
    uint8_t lut[256];
    memset(hist, 0, sizeof(hist));

    /* Everything between these macros touches only plain C memory: the
     * source buffer is pinned by the buffer protocol and `out` is a fresh
     * object no other thread can see yet. No PyObject* may be touched here. */
    Py_BEGIN_ALLOW_THREADS
    if (channels == 1) {
        memcpy(dst, src.buf, npixels);
        hist_only(dst, npixels, hist);
    } else {
        gray_and_hist((const uint8_t *)src.buf, dst, npixels, channels, hist);
    }
    build_lut(hist, npixels, p_low, p_high, lut);
    apply_lut(dst, npixels, lut);
    Py_END_ALLOW_THREADS

    PyBuffer_Release(&src);
    return out;
}

static PyMethodDef ImgprocMethods[] = {
    {"enhance", imgproc_enhance, METH_VARARGS, enhance_doc},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef imgprocmodule = {
    PyModuleDef_HEAD_INIT,
    "dockbench_imgproc",
    "Fused scan-cleanup kernel (C, GIL released during pixel work).",
    -1,
    ImgprocMethods,
    NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit_dockbench_imgproc(void)
{
    return PyModule_Create(&imgprocmodule);
}

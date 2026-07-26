#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Helper: call a Python function with given arguments and write result to file
static int call_python_func(const char* func_name, int argc, char* argv[]) {
    PyObject *pName, *pModule, *pFunc;
    PyObject *pArgs, *pValue;
    int i, result = -1;

    // Ensure Python interpreter is initialized
    if (!Py_IsInitialized()) {
        Py_Initialize();
    }

    // Import the backend.premium_pdf module
    pName = PyUnicode_DecodeFSDefault("backend.premium_pdf");
    if (!pName) { fprintf(stderr, "Failed to decode module name\n"); goto cleanup; }
    pModule = PyImport_Import(pName);
    Py_DECREF(pName);
    if (!pModule) { PyErr_Print(); fprintf(stderr, "Failed to import module\n"); goto cleanup; }

    // Get the function object
    pFunc = PyObject_GetAttrString(pModule, func_name);
    if (!pFunc || !PyCallable_Check(pFunc)) {
        if (PyErr_Occurred()) PyErr_Print();
        fprintf(stderr, "Cannot find callable %s\n", func_name);
        goto cleanup;
    }

    // Build argument tuple for the function
    pArgs = PyTuple_New(argc);
    for (i = 0; i < argc; ++i) {
        pValue = PyUnicode_FromString(argv[i]);
        if (!pValue) {
            Py_DECREF(pArgs);
            fprintf(stderr, "Cannot convert argument\n");
            goto cleanup;
        }
        PyTuple_SetItem(pArgs, i, pValue); // steals reference
    }

    // Call the Python function
    PyObject *pResult = PyObject_CallObject(pFunc, pArgs);
    Py_DECREF(pArgs);
    if (!pResult) {
        PyErr_Print();
        fprintf(stderr, "Python function %s failed\n", func_name);
        goto cleanup;
    }

    // Expect the function to return a tuple (bytes, mime)
    if (!PyTuple_Check(pResult) || PyTuple_Size(pResult) != 2) {
        fprintf(stderr, "Unexpected return type from %s\n", func_name);
        Py_DECREF(pResult);
        goto cleanup;
    }

    PyObject *pBytes = PyTuple_GetItem(pResult, 0);
    PyObject *pMime = PyTuple_GetItem(pResult, 1);
    if (!PyBytes_Check(pBytes) || !PyUnicode_Check(pMime)) {
        fprintf(stderr, "Invalid return values from %s\n", func_name);
        Py_DECREF(pResult);
        goto cleanup;
    }

    // Write bytes to the output file specified as last argument in argv
    const char* out_path = argv[argc-1]; // convention: last arg is output path
    FILE *out = fopen(out_path, "wb");
    if (!out) {
        perror("Failed to open output file");
        Py_DECREF(pResult);
        goto cleanup;
    }
    const char *buf = PyBytes_AsString(pBytes);
    Py_ssize_t len = PyBytes_Size(pBytes);
    fwrite(buf, 1, (size_t)len, out);
    fclose(out);
    Py_DECREF(pResult);
    result = 0; // success

cleanup:
    Py_XDECREF(pFunc);
    Py_XDECREF(pModule);
    if (Py_IsInitialized()) {
        Py_Finalize();
    }
    return result;
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: pdf_engine <command> [args...]\n");
        return 1;
    }
    const char* cmd = argv[1];
    // Shift arguments so that argv[2] becomes first argument to Python function
    // We'll pass all following args (including output path) to the Python function.
    if (strcmp(cmd, "merge") == 0) {
        // Expected: merge <output_path> <input1.pdf> [<input2.pdf> ...]
        return call_python_func("run_merge_pdf_files", argc-2, &argv[2]);
    } else if (strcmp(cmd, "split") == 0) {
        // Expected: split <input.pdf> <output_zip_path>
        return call_python_func("run_split_pdf", argc-2, &argv[2]);
    } else if (strcmp(cmd, "range") == 0) {
        // Expected: range <input.pdf> <start_page> <end_page> <output_zip_path>
        return call_python_func("run_split_pdf_range", argc-2, &argv[2]);
    } else {
        fprintf(stderr, "Unknown command %s\n", cmd);
        return 1;
    }
}

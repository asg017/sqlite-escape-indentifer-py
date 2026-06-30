/*
 * _quote — a thin CPython wrapper over SQLite's sqlite3_mprintf() %w / %Q / %q
 * substitution types, the canonical way to safely quote SQL identifiers and
 * string literals.
 *
 * We compile against a vendored SQLite amalgamation and use ONLY sqlite3_mprintf
 * / sqlite3_free / sqlite3_initialize. No database is ever opened.
 *
 * Safety notes:
 *   - Input comes in via the "s"/"z" arg formats, which (a) encode to UTF-8,
 *     (b) reject embedded NUL bytes (a NUL would silently truncate a C-string
 *     based quote and change an identifier's meaning -- a real injection risk),
 *     and (c) reject lone surrogates.
 *   - We cap input length well below SQLite's internal SQLITE_MAX_LENGTH (1e9)
 *     so the 2x+2 worst-case expansion can never overflow it.
 *   - sqlite3_mprintf returns NULL on OOM *or* on exceeding the internal length
 *     limit; we surface that as MemoryError.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <string.h>

#include "sqlite3.h"

/*
 * Hard ceiling on input bytes (UTF-8). Worst-case output is 2*n + 2, which we
 * keep comfortably under SQLITE_MAX_LENGTH (default 1,000,000,000) so the
 * allocation inside SQLite never hits its own overflow path before we do.
 * The Python layer enforces a much smaller, user-tunable default on top.
 */
#define SQ_MAX_INPUT_BYTES ((Py_ssize_t)450000000)

/* Run the given format with one string argument, returning a new Python str. */
static PyObject *
run_mprintf(const char *fmt, const char *value, Py_ssize_t nbytes)
{
    if (nbytes > SQ_MAX_INPUT_BYTES) {
        PyErr_Format(
            PyExc_ValueError,
            "input is too large to quote (%zd bytes; limit is %zd)",
            nbytes, (Py_ssize_t)SQ_MAX_INPUT_BYTES);
        return NULL;
    }

    char *out;
    Py_BEGIN_ALLOW_THREADS
    out = sqlite3_mprintf(fmt, value);
    Py_END_ALLOW_THREADS

    if (out == NULL) {
        /* NULL == out-of-memory or SQLite's internal length limit was hit. */
        return PyErr_NoMemory();
    }

    PyObject *result = PyUnicode_FromString(out);
    sqlite3_free(out);
    return result;
}

PyDoc_STRVAR(quote_identifier_doc,
"quote_identifier(name, /)\n--\n\n"
"Return *name* as a double-quoted SQL identifier (via SQLite's \"%w\").\n"
"Inner double quotes are doubled. *name* must be str without NUL bytes.");

static PyObject *
quote_identifier(PyObject *self, PyObject *arg)
{
    const char *value;
    Py_ssize_t nbytes;
    value = PyUnicode_AsUTF8AndSize(arg, &nbytes);
    if (value == NULL) {
        return NULL;  /* not str / lone surrogate */
    }
    if ((Py_ssize_t)strlen(value) != nbytes) {
        PyErr_SetString(PyExc_ValueError,
                        "SQL identifier must not contain NUL characters");
        return NULL;
    }
    return run_mprintf("\"%w\"", value, nbytes);
}

PyDoc_STRVAR(quote_string_doc,
"quote_string(value, /)\n--\n\n"
"Return *value* as a single-quoted SQL string literal (via SQLite's \"%Q\").\n"
"Inner single quotes are doubled; None becomes the bare token NULL.");

static PyObject *
quote_string(PyObject *self, PyObject *arg)
{
    if (arg == Py_None) {
        return run_mprintf("%Q", NULL, 0);  /* -> "NULL" */
    }
    const char *value;
    Py_ssize_t nbytes;
    value = PyUnicode_AsUTF8AndSize(arg, &nbytes);
    if (value == NULL) {
        return NULL;
    }
    if ((Py_ssize_t)strlen(value) != nbytes) {
        PyErr_SetString(PyExc_ValueError,
                        "SQL string must not contain NUL characters");
        return NULL;
    }
    return run_mprintf("%Q", value, nbytes);
}

PyDoc_STRVAR(quote_string_bare_doc,
"quote_string_bare(value, /)\n--\n\n"
"Return *value* with single quotes doubled but WITHOUT surrounding quotes\n"
"(via SQLite's \"%q\"), for embedding inside a larger quoted literal.");

static PyObject *
quote_string_bare(PyObject *self, PyObject *arg)
{
    const char *value;
    Py_ssize_t nbytes;
    value = PyUnicode_AsUTF8AndSize(arg, &nbytes);
    if (value == NULL) {
        return NULL;
    }
    if ((Py_ssize_t)strlen(value) != nbytes) {
        PyErr_SetString(PyExc_ValueError,
                        "SQL string must not contain NUL characters");
        return NULL;
    }
    return run_mprintf("%q", value, nbytes);
}

static PyMethodDef methods[] = {
    {"quote_identifier", quote_identifier, METH_O, quote_identifier_doc},
    {"quote_string", quote_string, METH_O, quote_string_doc},
    {"quote_string_bare", quote_string_bare, METH_O, quote_string_bare_doc},
    {NULL, NULL, 0, NULL},
};

static int
exec_module(PyObject *module)
{
    int rc = sqlite3_initialize();
    if (rc != SQLITE_OK) {
        PyErr_Format(PyExc_RuntimeError,
                     "sqlite3_initialize() failed with code %d", rc);
        return -1;
    }
    if (PyModule_AddStringConstant(module, "sqlite_version",
                                   sqlite3_libversion()) < 0) {
        return -1;
    }
    if (PyModule_AddIntConstant(module, "max_input_bytes",
                                SQ_MAX_INPUT_BYTES) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot module_slots[] = {
    {Py_mod_exec, exec_module},
#if PY_VERSION_HEX >= 0x030C0000
    {Py_mod_multiple_interpreters, Py_MOD_MULTIPLE_INTERPRETERS_NOT_SUPPORTED},
#endif
    {0, NULL},
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "sqlite_quote._quote",
    "Safe SQL quoting backed by SQLite's sqlite3_mprintf().",
    0,
    methods,
    module_slots,
    NULL,
    NULL,
    NULL,
};

PyMODINIT_FUNC
PyInit__quote(void)
{
    return PyModuleDef_Init(&moduledef);
}

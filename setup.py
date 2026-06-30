"""Build the _quote C extension against the vendored SQLite amalgamation.

Project metadata lives in pyproject.toml; this file exists only to declare the
C extension. The amalgamation (vendor/sqlite3.c, vendor/sqlite3.h) must be
present -- run `python scripts/fetch_sqlite.py` first. It is included in the
sdist, so building a wheel from the sdist needs no network access.
"""

from __future__ import annotations

import os
import sys

from setuptools import Extension, setup

VENDOR = os.path.join(os.path.dirname(__file__), "vendor")

if not os.path.exists(os.path.join(VENDOR, "sqlite3.c")):
    sys.exit(
        "vendor/sqlite3.c is missing.\n"
        "Run:  python scripts/fetch_sqlite.py\n"
        "to download and verify the SQLite amalgamation before building."
    )

# We only ever call sqlite3_mprintf/sqlite3_free/sqlite3_initialize and never
# open a database, so we strip what we safely can. THREADSAFE=0 avoids linking
# pthreads and is fine because all calls happen while holding the GIL; the
# functions we use keep no shared mutable state once initialized.
define_macros = [
    ("SQLITE_THREADSAFE", "0"),
    ("SQLITE_DEFAULT_MEMSTATUS", "0"),
    ("SQLITE_OMIT_LOAD_EXTENSION", "1"),
    ("SQLITE_OMIT_DEPRECATED", "1"),
    ("SQLITE_DQS", "0"),
]

extra_compile_args: list[str] = []
if os.name != "nt":
    # The amalgamation is known-clean; quiet its noise without -Werror.
    extra_compile_args += ["-O2", "-w"]

ext = Extension(
    name="sqlite_quote._quote",
    sources=["src/sqlite_quote/_quote.c", "vendor/sqlite3.c"],
    include_dirs=[VENDOR],
    define_macros=define_macros,
    extra_compile_args=extra_compile_args,
    py_limited_api=False,
)

setup(ext_modules=[ext])

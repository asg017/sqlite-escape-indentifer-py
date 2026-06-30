#!/usr/bin/env python3
"""Download and verify the SQLite amalgamation, extracting sqlite3.c / sqlite3.h.

Stdlib-only on purpose: this runs in build environments before any
dependencies are installed (sdist build, cibuildwheel containers, etc.).

The SHA3-256 hash is the one published on https://sqlite.org/download.html.
Verifying it means a tampered or truncated download fails loudly instead of
silently compiling something we didn't intend to ship.
"""

from __future__ import annotations

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

# --- Pinned SQLite release -------------------------------------------------
# Bump these three together. The hash is the "SHA3-256" column on the
# SQLite download page for the sqlite-amalgamation zip.
SQLITE_YEAR = "2026"
SQLITE_VERSION = "3530300"  # 3.53.3
SQLITE_SHA3_256 = "d45c688a8cb23f68611a894a756a12d7eb6ab6e9e2468ca70adbeab3808b5ab9"

ZIP_NAME = f"sqlite-amalgamation-{SQLITE_VERSION}.zip"
URL = f"https://sqlite.org/{SQLITE_YEAR}/{ZIP_NAME}"

VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
WANTED = ("sqlite3.c", "sqlite3.h")


def _sha3_256(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()


def already_present() -> bool:
    stamp = VENDOR_DIR / ".sqlite-version"
    if not all((VENDOR_DIR / name).exists() for name in WANTED):
        return False
    return stamp.exists() and stamp.read_text().strip() == SQLITE_VERSION


def main() -> int:
    if "--force" not in sys.argv and already_present():
        print(f"vendor/ already has SQLite {SQLITE_VERSION}; skipping (use --force to refetch).")
        return 0

    print(f"Downloading {URL}")
    with urllib.request.urlopen(URL, timeout=120) as resp:  # noqa: S310 (fixed, trusted host)
        blob = resp.read()

    digest = _sha3_256(blob)
    if digest != SQLITE_SHA3_256:
        print(
            "SHA3-256 mismatch!\n"
            f"  expected {SQLITE_SHA3_256}\n"
            f"  got      {digest}",
            file=sys.stderr,
        )
        return 1
    print(f"SHA3-256 OK: {digest}")

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for member in zf.namelist():
            base = Path(member).name
            if base in WANTED:
                dest = VENDOR_DIR / base
                dest.write_bytes(zf.read(member))
                print(f"  extracted {base} ({dest.stat().st_size:,} bytes)")

    missing = [name for name in WANTED if not (VENDOR_DIR / name).exists()]
    if missing:
        print(f"archive did not contain: {missing}", file=sys.stderr)
        return 1

    (VENDOR_DIR / ".sqlite-version").write_text(SQLITE_VERSION + "\n")
    print(f"vendor/ populated with SQLite {SQLITE_VERSION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

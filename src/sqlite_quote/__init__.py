"""Safely quote SQL identifiers and string literals using SQLite's own C API.

This package is a thin, dependency-free wrapper over SQLite's ``sqlite3_mprintf``
``%w`` / ``%Q`` / ``%q`` substitution types -- the canonical, authoritative way
to quote SQL for SQLite. It bundles its own SQLite (no database is ever opened),
so it works alongside any driver: the stdlib :mod:`sqlite3`, ``apsw``, etc.

    >>> import sqlite_quote
    >>> sqlite_quote.quote_identifier('my "weird" table')
    '"my ""weird"" table"'
    >>> sqlite_quote.quote_string("O'Brien")
    "'O''Brien'"
    >>> sqlite_quote.quote_string(None)
    'NULL'

The functions are NOT general-purpose escapers for other databases -- the rules
are SQLite's. Prefer bound parameters for *values*; use :func:`quote_string`
only when you must inline a literal, and :func:`quote_identifier` for table or
column names that cannot be parameterised.
"""

from __future__ import annotations

from . import _quote

__all__ = [
    "quote_identifier",
    "quote_string",
    "quote_string_bare",
    "quote_qualified_name",
    "DEFAULT_MAX_LENGTH",
    "MAX_INPUT_BYTES",
    "sqlite_version",
]

#: Compiled-in SQLite library version (e.g. ``"3.53.3"``).
sqlite_version: str = _quote.sqlite_version

#: Absolute upper bound (UTF-8 bytes) enforced in C, regardless of ``max_length``.
MAX_INPUT_BYTES: int = _quote.max_input_bytes

#: Default cap (in characters) applied by the wrappers below. Identifiers and
#: sensible string literals are far shorter than this; the cap exists to turn a
#: runaway/accidental gigabyte input into an immediate :class:`ValueError`
#: instead of a large allocation. Pass ``max_length=None`` to opt out (you are
#: still protected by :data:`MAX_INPUT_BYTES` and SQLite's own limits).
DEFAULT_MAX_LENGTH: int = 1_000_000


def _check_length(value: str, max_length: int | None) -> None:
    if max_length is not None and len(value) > max_length:
        raise ValueError(
            f"input length {len(value)} exceeds max_length={max_length}; "
            f"pass a larger max_length (or None) if this is intentional"
        )


def quote_identifier(name: str, *, max_length: int | None = DEFAULT_MAX_LENGTH) -> str:
    """Return *name* as a double-quoted SQL identifier.

    Uses SQLite's ``%w``: the result is wrapped in double quotes and any inner
    double quotes are doubled, so ``foo"bar`` becomes ``"foo""bar"``.

    :param name: identifier text; must be :class:`str` without NUL characters.
    :param max_length: max input length in characters, or ``None`` to disable
        the wrapper's check. Defaults to :data:`DEFAULT_MAX_LENGTH`.
    :raises TypeError: if *name* is not a ``str``.
    :raises ValueError: if *name* contains a NUL or exceeds the length limit.
    :raises MemoryError: if SQLite cannot allocate the result.
    """
    if not isinstance(name, str):
        raise TypeError(f"identifier must be str, not {type(name).__name__}")
    _check_length(name, max_length)
    return _quote.quote_identifier(name)


def quote_string(
    value: str | None, *, max_length: int | None = DEFAULT_MAX_LENGTH
) -> str:
    """Return *value* as a single-quoted SQL string literal.

    Uses SQLite's ``%Q``: the result is wrapped in single quotes with inner
    single quotes doubled, and ``None`` becomes the bare token ``NULL``.

    :param value: literal text, or ``None`` for SQL ``NULL``.
    :param max_length: see :func:`quote_identifier`.
    :raises TypeError: if *value* is neither ``str`` nor ``None``.
    :raises ValueError: if *value* contains a NUL or exceeds the length limit.
    :raises MemoryError: if SQLite cannot allocate the result.
    """
    if value is None:
        return _quote.quote_string(None)
    if not isinstance(value, str):
        raise TypeError(f"value must be str or None, not {type(value).__name__}")
    _check_length(value, max_length)
    return _quote.quote_string(value)


def quote_string_bare(
    value: str, *, max_length: int | None = DEFAULT_MAX_LENGTH
) -> str:
    """Return *value* with inner single quotes doubled but no surrounding quotes.

    Uses SQLite's ``%q``, for embedding inside a larger literal you are building
    yourself. Most callers want :func:`quote_string` instead.
    """
    if not isinstance(value, str):
        raise TypeError(f"value must be str, not {type(value).__name__}")
    _check_length(value, max_length)
    return _quote.quote_string_bare(value)


def quote_qualified_name(
    *parts: str, max_length: int | None = DEFAULT_MAX_LENGTH
) -> str:
    """Quote and dot-join identifier *parts*, e.g. schema/table/column.

        >>> quote_qualified_name("main", "my table")
        '"main"."my table"'

    :raises ValueError: if no parts are given.
    """
    if not parts:
        raise ValueError("quote_qualified_name() requires at least one part")
    return ".".join(quote_identifier(p, max_length=max_length) for p in parts)

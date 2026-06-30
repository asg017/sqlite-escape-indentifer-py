"""Behavioural tests, cross-checked against SQLite's own output where possible."""

from __future__ import annotations

import sqlite3

import pytest

import sqlite_quote
from sqlite_quote import (
    quote_identifier,
    quote_qualified_name,
    quote_string,
    quote_string_bare,
)


def _sqlite_quote_via_driver(fmt: str, value):
    """Independent oracle: ask the stdlib driver's own SQLite to do printf()."""
    con = sqlite3.connect(":memory:")
    try:
        (out,) = con.execute("SELECT printf(?, ?)", (fmt, value)).fetchone()
        return out
    finally:
        con.close()


# --- identifiers (%w) ------------------------------------------------------

@pytest.mark.parametrize(
    "name, expected",
    [
        ("table", '"table"'),
        ('a"b', '"a""b"'),
        ('my "weird" table', '"my ""weird"" table"'),
        ('"; DROP TABLE users; --', '"""; DROP TABLE users; --"'),
        ("", '""'),
        ("ünïcøde", '"ünïcøde"'),
        ("emoji 😀", '"emoji 😀"'),
    ],
)
def test_quote_identifier(name, expected):
    assert quote_identifier(name) == expected


def test_quote_identifier_matches_driver():
    for name in ["plain", 'has"quote', "spaces here", "select"]:
        assert quote_identifier(name) == _sqlite_quote_via_driver('"%w"', name)


def test_quoted_identifier_round_trips_through_real_sqlite():
    weird = 'tab"le; DROP'
    con = sqlite3.connect(":memory:")
    try:
        con.execute(f"CREATE TABLE {quote_identifier(weird)} (x)")
        con.execute(f"INSERT INTO {quote_identifier(weird)} VALUES (1)")
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
        assert weird in names
    finally:
        con.close()


# --- string literals (%Q) --------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("O'Brien", "'O''Brien'"),
        ("", "''"),
        ("plain", "'plain'"),
        ("'; DROP TABLE t; --", "'''; DROP TABLE t; --'"),
        (None, "NULL"),
    ],
)
def test_quote_string(value, expected):
    assert quote_string(value) == expected


def test_quote_string_literal_evaluates_in_sqlite():
    value = "it's a \"test\" -- ;"
    con = sqlite3.connect(":memory:")
    try:
        (out,) = con.execute(f"SELECT {quote_string(value)}").fetchone()
        assert out == value
    finally:
        con.close()


def test_quote_string_bare():
    assert quote_string_bare("O'Brien") == "O''Brien"
    assert quote_string_bare("plain") == "plain"


# --- qualified names -------------------------------------------------------

def test_quote_qualified_name():
    assert quote_qualified_name("main", "my table") == '"main"."my table"'
    assert quote_qualified_name("col") == '"col"'


def test_quote_qualified_name_requires_parts():
    with pytest.raises(ValueError):
        quote_qualified_name()


# --- input validation / safety --------------------------------------------

def test_nul_rejected():
    with pytest.raises(ValueError, match="NUL"):
        quote_identifier("a\x00b")
    with pytest.raises(ValueError, match="NUL"):
        quote_string("a\x00b")


def test_type_errors():
    with pytest.raises(TypeError):
        quote_identifier(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        quote_string(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        quote_identifier(None)  # type: ignore[arg-type]


def test_max_length_default():
    big = "a" * (sqlite_quote.DEFAULT_MAX_LENGTH + 1)
    with pytest.raises(ValueError, match="max_length"):
        quote_identifier(big)


def test_max_length_override_allows_more():
    big = "a" * (sqlite_quote.DEFAULT_MAX_LENGTH + 1)
    out = quote_identifier(big, max_length=None)
    assert out == f'"{big}"'


def test_large_value_within_limits():
    value = "x" * 5_000_000
    out = quote_string(value, max_length=None)
    assert out.startswith("'") and out.endswith("'")
    assert len(out) == len(value) + 2


# --- metadata --------------------------------------------------------------

def test_sqlite_version_exposed():
    assert sqlite_quote.sqlite_version.count(".") == 2
    assert isinstance(sqlite_quote.MAX_INPUT_BYTES, int)

# sqlite-quote

Safely quote SQL identifiers and string literals using SQLite's own
`sqlite3_mprintf` (`%w` / `%Q` / `%q`). Bundles its own SQLite — no database is
ever opened, works alongside any driver.


This library should be a last resort. Always use bound parameters when possible (`?`, `:name`, `@age`, etc.). Or use `column in (select value from json_each(:list))` to unravel a list of items. But for instances when your SQL doesnt allow for parameters, like in `VIEW`s or `PRAGMA` definitions, consider this.

## Install

```sh
pip install sqlite-quote
# or
uv add sqlite-quote
```

## Usage

```python
import sqlite_quote

sqlite_quote.quote_identifier('my "weird" table')  # '"my ""weird"" table"'
sqlite_quote.quote_string("O'Brien")               # "'O''Brien'"
sqlite_quote.quote_string(None)                     # 'NULL'
```

# extjson

The `extjson` library is a small Python module for serializing and deserializing data to/from JSON,
following MongoDB Extended JSON conventions.

It currently adds support for these common types:

- `datetime.datetime` (timezone-aware)
- `bytes`
- `uuid.UUID`
- `decimal.Decimal`
- special floating-point values (`NaN`, `Infinity`, `-Infinity`)

For naive datetimes, or for separate dates/times, use JSON strings with your own formatting (e.g. `isoformat()`).

Serialization can be done in two modes:
- **Relaxed mode** (default): use native JSON numbers, iso-formatted dates, and simple
  `$uuid` wrappers, wherever possible.
- **Canonical mode**: use strict Extended JSON wrappers such as
  `$numberInt`, `$numberLong`, `$numberDouble`, `$binary`... for every value.
  Much less readable, but more straightforward to parse.

Note that the parser will transparently decode both formats.

For the complete Extended JSON specification, see https://www.mongodb.com/docs/languages/python/pymongo-driver/current/data-formats/extended-json/

## Installation

Install from PyPI:

```bash
pip install extjson
```

## Quick start

```python
from datetime import datetime, timezone
from decimal import Decimal
import uuid

from extjson import convert_from_extjson, convert_to_extjson

payload = {
    "id": uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479"),
    "created_at": datetime(2024, 1, 16, 12, 30, tzinfo=timezone.utc),
    "price": Decimal("19.99"),
    "raw": b"hello",
}

ext_doc = convert_to_extjson(payload, canonical=True)
roundtrip = convert_from_extjson(ext_doc)

assert roundtrip == payload
```

## Canonical vs relaxed mode

Use `convert_to_extjson(..., canonical=True|False)`:

```python
from extjson import convert_to_extjson

print(convert_to_extjson(42, canonical=True))   # {'$numberInt': '42'}
print(convert_to_extjson(42, canonical=False))  # 42
```

## High-level JSON helpers

If you want JSON strings/bytes/files directly, use the helper API:

- `dumps(obj, **json_kwargs)` / `loads(data, **json_kwargs)`: replacements for stdlib JSON functions
- `dump_to_json_str(data, **json_kwargs)` / `load_from_json_str(data, **json_kwargs)`: same as above, but 
  preconfigured for reproducibility (e.g. `sort_keys=True`)
- `dump_to_json_bytes(data, **json_kwargs)` / `load_from_json_bytes(data, **json_kwargs)`
- `dump_to_json_file(path, data, **json_kwargs)` / `load_from_json_file(path, **json_kwargs)`

All these functions accept a `canonical=True|False` argument, and forward the rest to the underlying `json` 
functions (e.g. `indent=2` for pretty-printing).

```python
import uuid
from extjson import dump_to_json_str, load_from_json_str

payload = {"name": "hello", "blob": b"xyz", "uid": uuid.uuid4()}

json_text = dump_to_json_str(payload)
back = load_from_json_str(json_text)

assert back == payload
```

## Notes and behavior details

- When encoding, datetimes must be timezone-aware.
- When encoding, tuples and their content remain untouched (only lists and dicts are recursively processed).
- Decoded datetimes are normalized to UTC timezone.
- `NaN` values round-trip, but `NaN != NaN` still applies in Python comparisons.

## License

MIT


# extjson

`extjson` is a small Python library for serializing and deserializing data to/from JSON,
following MongoDB ExtendedJSON conventions.

It currently adds support for these types (not MongoDB-specific):

- `datetime.datetime` (always timezone-aware)
- `bytes`
- `uuid.UUID`
- `decimal.Decimal`
- special floating-point values (`NaN`, `Infinity`, `-Infinity`)

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

- `canonical=True` (default): strict Extended JSON wrappers such as
  `$numberInt`, `$numberLong`, `$numberDouble`, `$binary`.
- `canonical=False`: uses native JSON numbers where possible and legacy `$uuid`
  for UUID values.

Example:

```python
from extjson import convert_to_extjson

print(convert_to_extjson(42, canonical=True))   # {'$numberInt': '42'}
print(convert_to_extjson(42, canonical=False))  # 42
```

## High-level JSON helpers

If you want JSON strings/bytes/files directly, use the helper API:

- `dumps(obj, **json_kwargs)` / `loads(data, **json_kwargs)`
- `dump_to_json_str(data, **json_kwargs)` / `load_from_json_str(data, **json_kwargs)`
- `dump_to_json_bytes(data, **json_kwargs)` / `load_from_json_bytes(data, **json_kwargs)`
- `dump_to_json_file(path, data, **json_kwargs)` / `load_from_json_file(path, **json_kwargs)`

```python
import uuid
from extjson import dump_to_json_str, load_from_json_str

payload = {"name": "hello", "blob": b"xyz", "uid": uuid.uuid4()}

json_text = dump_to_json_str(payload)  # sort_keys=True by default
back = load_from_json_str(json_text)

assert back == payload
```

## Notes and behavior details

- Datetimes must be timezone-aware when encoding.
- Decoded datetimes are normalized to UTC.
- `NaN` values round-trip, but `NaN != NaN` still applies in Python comparisons.
- Tuples are not specially handled (lists and dicts are recursively processed).

## License

MIT


# extjson

The `extjson` library is a small, dependency-free Python module for serializing and deserializing data
to/from JSON, following [MongoDB Extended JSON](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/data-formats/extended-json/)
conventions.

On top of standard JSON types, it supports:

- `datetime.datetime` (timezone-aware only)
- `bytes`
- `uuid.UUID`
- `decimal.Decimal` (where available)
- special floating-point values (`NaN`, `Infinity`, `-Infinity`), as standard-compliant `$numberDouble` wrappers

It only implements a subset of the Extended JSON specification, see
[Supported Extended JSON wrappers](#supported-extended-json-wrappers).

## Installation

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

ext_doc = convert_to_extjson(payload)  # JSON-compatible tree of dicts/lists/scalars
roundtrip = convert_from_extjson(ext_doc)

assert roundtrip == payload
```

## Canonical vs relaxed mode

All encoding functions take a `canonical` argument:

- **Relaxed mode** (`canonical=False`, the default): uses native JSON numbers, ISO-formatted dates
  and simple `$uuid` wrappers wherever possible. More readable.
- **Canonical mode** (`canonical=True`): wraps every number, date and UUID in a strict, type-preserving
  wrapper (`$numberInt`, `$numberLong`, `$numberDouble`, `$date` with `$numberLong`, `$binary`...).
  Less readable, but unambiguous to parse.

Strings, booleans and `None` are left as-is in both modes. The decoder transparently accepts both formats.

```python
from extjson import convert_to_extjson

print(convert_to_extjson(42))                  # 42
print(convert_to_extjson(42, canonical=True))  # {'$numberInt': '42'}
```

## High-level JSON helpers

To handle JSON strings, bytes or files directly:

| Encoding | Decoding | Notes |
|---|---|---|
| `dumps(obj, **json_kwargs)` | `loads(data, **json_kwargs)` | Drop-in replacements for `json.dumps`/`json.loads` |
| `dump_to_json_str(data, **json_kwargs)` | `load_from_json_str(data, **json_kwargs)` | Same, with `sort_keys=True` by default for reproducible output |
| `dump_to_json_bytes(data, **json_kwargs)` | `load_from_json_bytes(data, **json_kwargs)` | UTF-8 encoded `bytes` |
| `dump_to_json_file(path, data, **json_kwargs)` | `load_from_json_file(path, **json_kwargs)` | UTF-8 file; `dump_to_json_file` also returns the written bytes |

Encoding functions accept the `canonical` argument; all functions forward the remaining keyword
arguments to the underlying `json.dumps`/`json.loads` (e.g. `indent=2` for pretty-printing).

```python
import uuid
from extjson import dump_to_json_str, load_from_json_str

payload = {"name": "hello", "blob": b"xyz", "uid": uuid.uuid4()}

json_text = dump_to_json_str(payload, indent=2)
back = load_from_json_str(json_text)

assert back == payload
```

## Decoding with stdlib `json.loads`

If you already use Python's stdlib `json` module, you can decode Extended JSON on the fly
by passing `extjson_decoder_object_hook` as `object_hook`:

```python
import json

from extjson import extjson_decoder_object_hook

raw = '{"uid": {"$uuid": "7c0b18f5f4104e839263b38c2328e516"}, "blob": {"$binary": {"base64": "eHl6", "subType": "00"}}}'
decoded = json.loads(raw, object_hook=extjson_decoder_object_hook)

print(decoded)
# {'uid': UUID('7c0b18f5-f410-4e83-9263-b38c2328e516'), 'blob': b'xyz'}
```

There is no encoding counterpart (i.e. no `json.dumps(default=...)` hook): Python's JSON encoder
handles some values (e.g. `NaN` and infinite floats) with its own built-in logic, without ever calling
`default`, so such a hook could not reliably emit Extended JSON wrappers. Use `convert_to_extjson(...)`
or `dumps(...)` instead.

## Supported Extended JSON wrappers

Only the following `$`-wrappers are recognized on decoding; any other single-key dict
(e.g. `$oid`, `$regex`, `$code`, `$timestamp`, `$minKey`/`$maxKey`, `$dbPointer`, `$symbol`)
is left untouched, as `extjson` does not target full MongoDB/BSON compatibility:

| Wrapper | Decodes to | Encoded from |
|---|---|---|
| `$date` (ISO string) | `datetime.datetime`, with the offset given in the string | `datetime.datetime` (relaxed mode) |
| `$date` (`{"$numberLong": ...}` milliseconds) | `datetime.datetime` in UTC | `datetime.datetime` (canonical mode) |
| `$binary` (`subType` `"00"`) | `bytes` | `bytes` (both modes) |
| `$binary` (`subType` `"04"`) | `uuid.UUID` | `uuid.UUID` (canonical mode) |
| `$uuid` | `uuid.UUID` | `uuid.UUID` (relaxed mode) |
| `$numberInt` / `$numberLong` | `int` | `int` (canonical mode; `$numberInt` within the 32-bit range, else `$numberLong`) |
| `$numberDouble` | `float` | `float` (canonical mode; also relaxed mode for `NaN`/`Infinity`/`-Infinity`) |
| `$numberDecimal` | `decimal.Decimal` | `decimal.Decimal` (both modes) |
| `$undefined` | `None` | *(never; `None` always encodes to JSON `null`)* |

`bytes` and `decimal.Decimal` use the same wrapper in both modes, because Extended JSON has no relaxed
form for them.

A recognized wrapper with a wrongly-typed payload (e.g. `{"$numberInt": 42}`, or a `$binary` subtype other
than `00`/`04`, such as the legacy UUID subtype `03`) raises `TypeError` on decoding.

A well-typed but malformed payload lets the error of the underlying parser propagate instead: mostly
`ValueError` and its subclasses (e.g. `{"$numberInt": "1.5"}`, `{"$uuid": "nope"}`, an unparsable `$date`
string, invalid base64 raising `binascii.Error`), but also `OverflowError` for out-of-range `$date`
milliseconds, and `decimal.InvalidOperation` for an invalid `$numberDecimal`.

## Notes and behavior details

- Datetimes are truncated to millisecond precision in both modes, so microseconds are lost on round-trip.
- Naive datetimes raise `TypeError`, both when encoding a `datetime` and when decoding a `$date` string
  without an offset. For naive datetimes, or separate dates/times, store your own formatted strings
  (e.g. `isoformat()`) instead.
- In relaxed mode, a zero UTC offset is written as `Z`; other offsets are preserved.
- Tuples are encoded as JSON arrays, and therefore decode as lists.
- `NaN` values round-trip, but `NaN != NaN` still applies in Python comparisons.
- Dict keys are not converted, so only `json`-compatible keys work.
- Subclasses of supported types (e.g. `enum.IntEnum`) are encoded like their base type and decode as
  that base type.
- Values of other types (e.g. `datetime.timedelta`) are passed through unchanged, so `json.dumps()`
  raises its usual `TypeError: ... not JSON serializable`, unless you pass your own `default=` callback
  to `dumps(...)` or the `dump_to_json_*` helpers.
- `load_from_json_bytes` and `load_from_json_file` ignore a leading UTF-8 byte-order mark (BOM).
- `extjson.py` degrades gracefully on MicroPython:
  - it imports even without the `typing` and `decimal` modules;
  - if no `decimal` port is installed, decoding a `$numberDecimal` raises `ImportError`;
  - `sort_keys` is not applied by the `dump_to_json_*` helpers;
  - on single-precision float builds, `$numberDouble` values can't round-trip exactly.

## Development

```bash
poetry install
poetry run pytest test_extjson.py   # current interpreter
poetry run pytest test_extjson.py --cov   # with branch coverage report
poetry run tox                      # all supported Python versions
poetry run ruff check . && poetry run ruff format --check .
```

## License

MIT, see [LICENSE](LICENSE).

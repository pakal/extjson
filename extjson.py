"""
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


from __future__ import annotations

import base64
import calendar
import datetime
import decimal
import json
import math
import uuid
from typing import (
    Any,
    Callable,
    Mapping,
    Type,
    Union,
)


# Boundary between int32 and int64 for canonical representation of integers
_INT32_MAX = 2**31


# Only these two binary-data subtypes are supported
BINARY_SUBTYPE = 0
UUID_SUBTYPE = 4


# Default encoding for JSON strings when working with bytes
UTF8_ENCODING = "utf8"


# LOW LEVEL UTILITIES #


def convert_to_extjson(obj: Any, canonical: bool = False) -> Any:
    """Recursive helper method that converts BSON types so they can be
    converted into json.
    """
    assert canonical in (True, False), canonical
    if isinstance(obj, dict):
        return {k: convert_to_extjson(v, canonical=canonical) for k, v in obj.items()}
    elif isinstance(obj, list):  # Tuples are not handled!
        return [convert_to_extjson(v, canonical=canonical) for v in obj]

    return _convert_primitive_to_extjson(obj, canonical=canonical)


def _convert_primitive_to_extjson(obj: Any, canonical: bool) -> Any:
    # First see if the type is already cached. KeyError will only ever
    # happen once per subtype.
    try:
        encoder = _ENCODERS[type(obj)]
        return encoder(obj, canonical=canonical)
    except KeyError:
        pass

    # Then, test each base type. This will only happen once for
    # a subtype of a supported base type.
    for base in _EXTENDED_JSON_BUILT_IN_TYPES:
        if isinstance(obj, base):
            func = _ENCODERS[base]
            # Cache this type for faster subsequent lookup.
            _ENCODERS[type(obj)] = func
            return func(obj, canonical=canonical)

    # We give up and return the object unchanged
    # The "default" handler of json.dumps() might save the day
    return obj


def convert_from_extjson(ext_obj: Any) -> Any:
    """Recursive helper method that converts BSON types so they can be
    converted into json.
    """
    if isinstance(ext_obj, dict):
        ext_obj = {k: convert_from_extjson(v) for k, v in ext_obj.items()}
        return _convert_primitive_from_extjson_dict(ext_obj)
    elif isinstance(ext_obj, list):  # Tuples are not handled!
        return [convert_from_extjson(v) for v in ext_obj]
    return ext_obj  # Was already a proper native type


def _convert_primitive_from_extjson_dict(ext_obj_dict: Mapping[str, Any]) -> Any:
    assert isinstance(ext_obj_dict, dict), repr(ext_obj_dict)
    match = None
    if len(ext_obj_dict) != 1:
        return ext_obj_dict  # Not a {$type: ...} dict
    for k in ext_obj_dict:
        if k in _PARSERS:
            match = k
            break
    if match:
        return _PARSERS[match](ext_obj_dict)
    return ext_obj_dict


def _encode_canonical_binary(data: bytes, subtype: int) -> Any:
    return {"$binary": {"base64": base64.b64encode(data).decode(), "subType": "%02x" % subtype}}


def _encode_int(obj: int, canonical: bool) -> Any:
    if canonical:
        if -_INT32_MAX <= obj < _INT32_MAX:
            return {"$numberInt": str(obj)}
        return {"$numberLong": str(obj)}
    return obj


def _encode_noop(obj: Any, canonical: bool) -> Any:
    return obj


def _encode_float(obj: float, canonical: bool) -> Any:
    if math.isnan(obj):
        return {"$numberDouble": "NaN"}
    elif math.isinf(obj):
        representation = "Infinity" if obj > 0 else "-Infinity"
        return {"$numberDouble": representation}
    elif canonical:
        # repr() will return the shortest string guaranteed to produce the
        # original value, when float() is called on it.
        return {"$numberDouble": repr(obj)}
    return obj


def _encode_decimal(obj: decimal.Decimal, canonical: bool) -> dict:
    # Always use canonical representation for Decimal numbers
    return {"$numberDecimal": str(obj)}


def _encode_datetime(obj: datetime.datetime, canonical: bool) -> dict:
    if not _is_aware_datetime(obj):
        raise TypeError(f"Unsupported naive datetime encountered: {obj}")
    if canonical:
        millis = _datetime_to_millis(obj)
        return {"$date": {"$numberLong": str(millis)}}
    # We output datetime as "YYYY-MM-DDTHH:MM:SS[.fff]<offset>" (not microseconds)
    timespec = "milliseconds" if obj.microsecond != 0 else "seconds"
    dts = obj.isoformat(sep="T", timespec=timespec)
    dts = dts.replace("+00:00", "Z")  # We ASSUME that 0-offset means UTC...
    return {"$date": dts}


def _encode_bytes(obj: bytes, canonical: bool) -> dict:
    # Always use canonical representation for Bytes
    return _encode_canonical_binary(obj, BINARY_SUBTYPE)


def _encode_uuid(obj: uuid.UUID, canonical: bool) -> dict:
    if canonical:
        return _encode_canonical_binary(obj.bytes, UUID_SUBTYPE)
    return {"$uuid": obj.hex}


# Encoders for BSON types
# Each encoder function's signature is:
#   - obj: a Python data type, e.g. a Python int for _encode_int
#   - canonical: whether to use canonical Extended JSON representation
_ENCODERS: dict[Type, Callable[[Any, bool], Any]] = {
    bool: _encode_noop,
    bytes: _encode_bytes,
    uuid.UUID: _encode_uuid,
    datetime.datetime: _encode_datetime,
    float: _encode_float,
    decimal.Decimal: _encode_decimal,
    int: _encode_int,
    str: _encode_noop,
    type(None): _encode_noop,
}

_EXTENDED_JSON_BUILT_IN_TYPES = tuple(_ENCODERS)


def _parse_canonical_binary(doc: Any) -> Union[bytes, uuid.UUID]:
    binary = doc["$binary"]
    b64 = binary["base64"]
    subtype = binary["subType"]
    if not isinstance(b64, str):
        raise TypeError(f"$binary base64 must be a string: {doc}")
    if not isinstance(subtype, str) or len(subtype) > 2:
        raise TypeError(f"$binary subType must be a string at most 2 characters: {doc}")
    if len(binary) != 2:
        raise TypeError(f'$binary must include only "base64" and "subType" components: {doc}')

    data = base64.b64decode(b64.encode())
    return _get_as_binary_or_uuid(data, int(subtype, 16))


def _get_as_binary_or_uuid(data: Any, subtype: int) -> Union[bytes, uuid.UUID]:
    if subtype not in (BINARY_SUBTYPE, UUID_SUBTYPE):
        raise TypeError(f"Unsupported binary subtype: {subtype}")
    if subtype == UUID_SUBTYPE:
        return uuid.UUID(bytes=data)
    return data


def _parse_canonical_datetime(doc: Any) -> datetime.datetime:
    """Decode a JSON datetime to python datetime.datetime."""
    dtm = doc["$date"]
    if len(doc) != 1:
        raise TypeError(f"Bad $date, extra field(s): {doc}")
    if isinstance(dtm, str):
        return datetime.datetime.fromisoformat(dtm)
    return _millis_to_datetime(dtm)


def _get_single_str_field(doc: Any, key: str) -> str:
    value = doc[key]
    if len(doc) != 1:
        raise TypeError(f"Bad {key}, extra field(s): {doc}")
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string: {doc}")
    return value


def _parse_canonical_int32(doc: Any) -> int:
    return int(_get_single_str_field(doc, "$numberInt"))


def _parse_canonical_int64(doc: Any) -> int:
    return int(_get_single_str_field(doc, "$numberLong"))


def _parse_canonical_double(doc: Any) -> float:
    return float(_get_single_str_field(doc, "$numberDouble"))


def _parse_canonical_decimal(doc: Any) -> decimal.Decimal:
    return decimal.Decimal(_get_single_str_field(doc, "$numberDecimal"))


def _parse_legacy_uuid(doc: Any) -> Union[bytes, uuid.UUID]:
    return uuid.UUID(_get_single_str_field(doc, "$uuid"))


_PARSERS: dict[str, Callable[[Any], Any]] = {
    "$date": _parse_canonical_datetime,
    "$binary": _parse_canonical_binary,
    "$uuid": _parse_legacy_uuid,
    "$undefined": lambda _: None,
    "$numberInt": _parse_canonical_int32,
    "$numberLong": _parse_canonical_int64,
    "$numberDouble": _parse_canonical_double,
    "$numberDecimal": _parse_canonical_decimal,
}


_EPOCH_AWARE = datetime.datetime.fromtimestamp(0, datetime.timezone.utc)


def _is_aware_datetime(dt: datetime.datetime) -> bool:
    """Check if a datetime is timezone aware."""
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def _datetime_to_millis(dt: datetime.datetime) -> int:
    """Convert aware datetime to milliseconds since epoch UTC."""
    assert _is_aware_datetime(dt), f"Unsupported naive datetime encountered: {dt}"
    dt = dt - dt.utcoffset()  # type: ignore
    return int(calendar.timegm(dt.timetuple()) * 1000 + dt.microsecond // 1000)


def _millis_to_datetime(
    millis: int,
) -> datetime.datetime:
    """Convert milliseconds since epoch UTC to aware datetime."""
    assert isinstance(millis, int), repr(millis)
    diff = ((millis % 1000) + 1000) % 1000
    seconds = (millis - diff) // 1000
    micros = diff * 1000

    dt = _EPOCH_AWARE + datetime.timedelta(seconds=seconds, microseconds=micros)

    return dt  # UTC aware datetime


# HIGH LEVEL UTILITIES #


def dumps(obj: Any, *args: Any, canonical=False, **kwargs: Any) -> str:
    """Helper function that wraps :func:`json.dumps`.

    Recursive function that handles main ExtendedJSON types.
    """
    ext_obj = convert_to_extjson(obj, canonical=canonical)
    return json.dumps(ext_obj, *args, **kwargs)


def loads(s: Union[str, bytes, bytearray], *args: Any, **kwargs: Any) -> Any:
    """Helper function that wraps :func:`json.loads`.

    Recursive function that handles main ExtendedJSON types.
    """
    ext_obj = json.loads(s, *args, **kwargs)
    return convert_from_extjson(ext_obj)


def dump_to_json_str(data, **extra_options):
    """
    Dump a data tree to a json representation as string
    (with sort_keys=True by default).
    Supports advanced types like bytes, uuids, dates...
    """
    sort_keys = extra_options.pop("sort_keys", True)
    json_str = dumps(data, sort_keys=sort_keys, **extra_options)
    return json_str


def load_from_json_str(data, **extra_options):
    """
    Load a data tree from a json representation as string.
    Supports advanced types like bytes, uuids, dates...

    Raises exceptions.ValidationError on loading error.
    """
    assert isinstance(data, str), data
    return loads(data, **extra_options)


def dump_to_json_bytes(data, **extra_options):
    """
    Same as `dump_to_json_str`, but returns UTF8-encoded bytes.
    """
    json_str = dump_to_json_str(data, **extra_options)
    return json_str.encode(UTF8_ENCODING)


def load_from_json_bytes(data, **extra_options):
    """
    Same as `load_from_json_str`, but takes UTF8-encoded bytes as input.
    """
    json_str = data.decode(UTF8_ENCODING)
    return load_from_json_str(data=json_str, **extra_options)


def dump_to_json_file(filepath, data, **extra_options):
    """
    Same as `dump_to_json_bytes`, but writes data to filesystem (and returns bytes too).
    """
    json_bytes = dump_to_json_bytes(data, **extra_options)
    with open(filepath, "wb") as f:
        f.write(json_bytes)
    return json_bytes


def load_from_json_file(filepath, **extra_options):
    """
    Same as `load_from_json_bytes`, but reads data from filesystem.
    """
    with open(filepath, "rb") as f:
        json_bytes = f.read()
    return load_from_json_bytes(json_bytes, **extra_options)

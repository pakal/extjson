# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking changes

- Python 3.11+ is now required (Python 3.10 support dropped).
- `$date` ISO strings without a UTC offset are now rejected with `TypeError`, instead of being decoded
  to naive datetimes.
- `$date` values that are neither an ISO string nor an integer of milliseconds are now rejected with
  `TypeError` (previously, booleans were decoded as milliseconds, and floats raised `AssertionError`).

### Added

- `extjson_decoder_object_hook`, to decode Extended JSON directly with the stdlib's
  `json.loads(..., object_hook=...)`.
- Tuples are now converted like lists, so their items get Extended JSON wrappers too (they still
  decode as lists).
- MicroPython support: the module degrades gracefully when `decimal` is unavailable, and the
  `dump_to_json_*` helpers don't apply `sort_keys` there.
- PyPI classifiers, keywords and changelog URL in the package metadata.

### Changed

- A `$binary` wrapper that is not a dict with exactly the `base64` and `subType` keys now raises an
  explicit `TypeError` (previously a `KeyError` or a less explicit `TypeError`).
- The license metadata now uses an SPDX expression (`license = "MIT"`).

### Documentation

- README expanded: canonical vs relaxed modes, high-level helpers, stdlib `object_hook` usage,
  table of supported Extended JSON wrappers, decoding errors, and edge-case behaviors.

## [0.1.1] - 2026-04-07

### Added

- Repository URL in the package metadata.

## [0.1.0] - 2026-04-07

Initial release.

### Added

- `convert_to_extjson()` / `convert_from_extjson()` to convert data trees to/from MongoDB Extended JSON,
  in relaxed (default) or canonical mode.
- Supported types: timezone-aware `datetime.datetime`, `bytes`, `uuid.UUID`, `decimal.Decimal`,
  and special floats (`NaN`, `Infinity`, `-Infinity`).
- Supported wrappers: `$date`, `$binary` (subtypes `00` and `04`), `$uuid`, `$numberInt`,
  `$numberLong`, `$numberDouble`, `$numberDecimal`, and `$undefined` (decoding only).
- `dumps()` / `loads()` drop-in replacements for `json.dumps()` / `json.loads()`.
- `dump_to_json_str()` / `load_from_json_str()`, `dump_to_json_bytes()` / `load_from_json_bytes()`
  and `dump_to_json_file()` / `load_from_json_file()` helpers, with `sort_keys=True` by default.

[Unreleased]: https://github.com/pakal/extjson/compare/10877c3...HEAD
[0.1.1]: https://github.com/pakal/extjson/compare/6dfcb3c...10877c3
[0.1.0]: https://github.com/pakal/extjson/tree/6dfcb3c

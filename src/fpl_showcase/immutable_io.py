"""Shared strict JSON and atomic no-replace installation; no state authority."""
import json
import hashlib
import os
from pathlib import Path
import tempfile
from dataclasses import dataclass

from .json_utils import canonical_json


@dataclass(frozen=True, init=False)
class _CanonicalObject:
    """Invocation-local encoded JSON fields, not a verification receipt.

    Only capture from values; no caller-supplied hashes or encoded fragments.
    Nested envelopes reuse the exact captured bytes without joining a giant
    string. Owners must still validate decoded current values and bindings.
    """
    _fields: tuple

    def __init__(self, value, *, normalize_keys=True):
        if not isinstance(value, dict) or any(type(k) is not str for k in value):
            raise ValueError('canonical object requires string keys')
        def needs_normalization(v, seen):
            if not isinstance(v, (dict, list, tuple)) or id(v) in seen:
                return False
            seen.add(id(v))
            if isinstance(v, dict):
                return (any(type(k) is not str for k in v) or
                        any(needs_normalization(x, seen) for x in v.values()))
            return any(needs_normalization(x, seen) for x in v)
        def encode(v):
            text = canonical_json(v)
            # Preserve the existing JSON-clone contract for non-string nested
            # keys: decoding can change key order/collapse duplicate keys.
            if normalize_keys and needs_normalization(v, set()):
                text = canonical_json(json.loads(text))
            return text.encode('utf-8')
        object.__setattr__(self, '_fields', tuple((k, canonical_json(k).encode('utf-8'), encode(v))
                                                for k, v in sorted(value.items())))

    def with_field(self, key, value):
        if key in {k for k, _, _ in self._fields}:
            raise ValueError('canonical field already exists')
        result = _CanonicalObject({key: value})
        object.__setattr__(result, '_fields', tuple(sorted((*self._fields, *result._fields))))
        return result

    @classmethod
    def envelope(cls, value, **objects):
        result = cls(value)
        if set(value) & set(objects) or any(not isinstance(v, cls) for v in objects.values()):
            raise ValueError('invalid canonical envelope')
        object.__setattr__(result, '_fields', tuple(sorted((*result._fields,
            *((k, canonical_json(k).encode('utf-8'), v) for k, v in objects.items())))))
        return result

    def decoded(self):
        return {k: json.loads(v) for k, _, v in self._fields}

    def chunks(self, *, exclude=()):
        yield b'{'
        first = True
        for k, key, value in self._fields:
            if k in exclude:
                continue
            if not first:
                yield b','
            first = False
            yield key
            yield b':'
            if isinstance(value, _CanonicalObject):
                yield from value.chunks()
            else:
                yield value
        yield b'}'

    def digest(self, *, exclude=()):
        digest = hashlib.sha256()
        for chunk in self.chunks(exclude=exclude):
            digest.update(chunk)
        return digest.hexdigest()

    def matches(self, value):
        # Exact canonical comparison, including float spelling; never hashes
        # alone or Python's weaker numeric equality on an occupied slot.
        if not isinstance(value, dict) or set(value) != {k for k, _, _ in self._fields}:
            return False
        return all(v.matches(value[k]) if isinstance(v, _CanonicalObject)
                   else v == canonical_json(value[k]).encode('utf-8')
                   for k, _, v in self._fields)


def read_object(path, *, error):
    def pairs(items):
        # JSON keys are strings. dict's C-level construction preserves all
        # unique pairs; a shorter dictionary proves a duplicate exists. Only
        # the invalid path needs a Python traversal to name the duplicate.
        result = dict(items)
        if len(result) != len(items):
            seen = set()
            for key, _ in items:
                if key in seen:
                    raise error(f'duplicate JSON key: {key}')
                seen.add(key)
        return result
    def constant(value):
        raise error('nonfinite JSON value')
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=pairs, parse_constant=constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as cause:
        raise error(f'cannot read persisted artifact: {path.name}') from cause
    if not isinstance(value, dict):
        raise error('persisted artifact must be an object')
    return value


def install_json(path, value, *, inside, error):
    """Flush/fsync and hard-link an exclusive slot; never overwrite."""
    def identical():
        if canonical_json(read_object(path, error=error)) != canonical_json(value):
            raise error('different content in existing immutable slot')
    def write(handle):
        handle.write((canonical_json(value) + '\n').encode('utf-8'))
    return _install(path, write, identical, inside=inside, error=error)


def _install_canonical(path, value, *, inside, error):
    """Install owner-captured canonical fields; return exact bytes written."""
    def identical():
        if not value.matches(read_object(path, error=error)):
            raise error('different content in existing immutable slot')
    size = 0
    def write(handle):
        nonlocal size
        for chunk in value.chunks():
            size += handle.write(chunk)
        size += handle.write(b'\n')
    created = _install(path, write, identical, inside=inside, error=error)
    return created, size if created else 0


def _install(path, write, identical, *, inside, error):
    inside(path)
    temporary = None
    try:
        if path.exists():
            identical()
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix='.pending-', dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            write(handle)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            identical()
            return False
        return True
    except OSError as cause:
        raise error('atomic no-replace persistence failed') from cause
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cause:
                raise error('staging cleanup failed; verify the persisted slot before retrying') from cause


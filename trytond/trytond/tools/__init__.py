# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import posixpath
from functools import cached_property
from weakref import WeakKeyDictionary

try:
    from werkzeug.security import safe_join
except ImportError:
    safe_join = posixpath.join

from .decimal_ import decistmt
from .misc import (
    entry_points, escape_wildcard, file_open, find_dir, find_path, firstline,
    get_smtp_server, grouped_slice, import_module, is_full_text,
    is_instance_method, likify, lstrip_wildcard, pairwise_longest,
    reduce_domain, reduce_ids, remove_forbidden_chars, resolve,
    rstrip_wildcard, slugify, sortable_values, sql_pairing, strip_wildcard,
    unescape_wildcard)

_NOT_FOUND = object()


class cached_property(cached_property):
    _cache = None

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        cache = getattr(instance, '__dict__', None)
        if cache is None:  # __slots__
            if self._cache is None:
                self._cache = WeakKeyDictionary()
            val = self._cache.get(instance, _NOT_FOUND)
            if val is _NOT_FOUND:
                self._cache[instance] = val = self.func(instance)
            return val
        else:
            return super().__get__(instance, owner)

    def __delete__(self, instance):
        cache = getattr(instance, '__dict__', None)
        try:
            if cache:
                del cache[self.attrname]
            elif self._cache:
                del self._cache[instance]
        except KeyError:
            pass


class ClassProperty(property):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


def cursor_dict(cursor, size=None):
    size = cursor.arraysize if size is None else size
    while True:
        rows = cursor.fetchmany(size)
        if not rows:
            break
        for row in rows:
            yield {d[0]: v for d, v in zip(cursor.description, row)}


__all__ = [
    ClassProperty,
    cached_property,
    cursor_dict,
    decistmt,
    entry_points,
    escape_wildcard,
    file_open,
    find_dir,
    find_path,
    firstline,
    get_smtp_server,
    grouped_slice,
    import_module,
    is_full_text,
    is_instance_method,
    likify,
    lstrip_wildcard,
    pairwise_longest,
    reduce_domain,
    reduce_ids,
    remove_forbidden_chars,
    resolve,
    rstrip_wildcard,
    safe_join,
    slugify,
    sortable_values,
    sql_pairing,
    strip_wildcard,
    unescape_wildcard,
    ]

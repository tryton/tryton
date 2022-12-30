# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import posixpath

try:
    from functools import cached_property
except ImportError:
    from werkzeug.utils import cached_property

try:
    from werkzeug.security import safe_join
except ImportError:
    safe_join = posixpath.join

from .decimal_ import decistmt
from .misc import (
    escape_wildcard, file_open, find_dir, find_path, firstline,
    get_smtp_server, grouped_slice, is_full_text, is_instance_method,
    lstrip_wildcard, reduce_domain, reduce_ids, remove_forbidden_chars,
    resolve, rstrip_wildcard, slugify, sortable_values, sql_pairing,
    strip_wildcard, unescape_wildcard)


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
    escape_wildcard,
    file_open,
    find_dir,
    find_path,
    firstline,
    get_smtp_server,
    grouped_slice,
    is_full_text,
    is_instance_method,
    lstrip_wildcard,
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

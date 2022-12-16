# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    from functools import cached_property
except ImportError:
    from werkzeug.utils import cached_property

from .misc import (
    file_open, get_smtp_server, reduce_ids, reduce_domain,
    grouped_slice, is_instance_method, resolve, strip_wildcard,
    lstrip_wildcard, rstrip_wildcard, slugify, sortable_values,
    escape_wildcard, unescape_wildcard, is_full_text, sql_pairing, firstline)
from .decimal_ import decistmt

__all__ = ['file_open', 'get_smtp_server', 'reduce_ids',
    'reduce_domain', 'grouped_slice', 'is_instance_method', 'resolve',
    'strip_wildcard', 'lstrip_wildcard', 'rstrip_wildcard', 'slugify',
    'decistmt', 'ClassProperty', 'cursor_dict', 'cached_property',
    'sortable_values', 'escape_wildcard', 'unescape_wildcard', 'is_full_text',
    'sql_pairing', 'firstline']


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

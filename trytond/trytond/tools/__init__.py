# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from .misc import *
from .decimal_ import *


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

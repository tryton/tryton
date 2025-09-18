# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['MoveLineMixin']


def __getattr__(name):
    if name == 'MoveLineMixin':
        from .move import MoveLineMixin
        return MoveLineMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['ROUNDING_OPPOSITES']


def __getattr__(name):
    if name == 'ROUNDING_OPPOSITES':
        from .currency import ROUNDING_OPPOSITES
        return ROUNDING_OPPOSITES
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

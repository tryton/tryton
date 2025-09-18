# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['LotSledMixin']


def __getattr__(name):
    if name == 'LotSledMixin':
        from .stock import LotSledMixin
        return LotSledMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

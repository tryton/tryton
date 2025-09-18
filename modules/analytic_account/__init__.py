# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['AnalyticMixin']


def __getattr__(name):
    if name == 'AnalyticMixin':
        from .account import AnalyticMixin
        return AnalyticMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

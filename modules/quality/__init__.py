# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['ControlledMixin']


def __getattr__(name):
    if name == 'ControlledMixin':
        from .quality import ControlledMixin
        return ControlledMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

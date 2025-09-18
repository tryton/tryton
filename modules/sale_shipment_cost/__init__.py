# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['ShipmentCostSaleMixin']


def __getattr__(name):
    if name == 'ShipmentCostSaleMixin':
        from .stock import ShipmentCostSaleMixin
        return ShipmentCostSaleMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

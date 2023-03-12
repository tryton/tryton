# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import production, quality, stock
from .quality import ControlledMixin

__all__ = ['register', 'ControlledMixin']


def register():
    Pool.register(
        quality.Configuration,
        quality.ConfigurationSequence,
        quality.Control,
        quality.ControlPoint,
        quality.Inspection,
        quality.Alert,
        quality.InspectStore,
        module='quality', type_='model')
    Pool.register(
        quality.Inspect,
        module='quality', type_='wizard')
    Pool.register(
        stock.ShipmentIn,
        stock.ShipmentOut,
        stock.ShipmentOutReturn,
        stock.ShipmentInternal,
        module='quality', type_='model', depends=['stock'])
    Pool.register(
        production.Production,
        module='quality', type_='model', depends=['production'])

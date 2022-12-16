# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import configuration
from . import sale
from . import stock

__all__ = ['register']


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationShipmentTolerance,
        sale.Line,
        stock.Move,
        module='sale_shipment_tolerance', type_='model')

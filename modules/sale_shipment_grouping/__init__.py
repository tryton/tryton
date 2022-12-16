# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import party
from . import sale
from . import configuration


def register():
    Pool.register(
        party.Party,
        party.PartySaleShipmentGroupingMethod,
        sale.Sale,
        configuration.Configuration,
        configuration.ConfigurationSaleMethod,
        module='sale_shipment_grouping', type_='model')

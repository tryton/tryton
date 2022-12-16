# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import routing
from . import production
from . import product


def register():
    Pool.register(
        routing.Routing,
        routing.RoutingOperation,
        routing.RoutingStep,
        routing.Routing_BOM,
        production.Production,
        product.ProductBom,
        product.ProductionLeadTime,
        module='production_routing', type_='model')

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .routing import *
from .production import *
from .product import *


def register():
    Pool.register(
        Routing,
        Operation,
        RoutingStep,
        Routing_BOM,
        Production,
        ProductBom,
        ProductionLeadTime,
        module='production_routing', type_='model')

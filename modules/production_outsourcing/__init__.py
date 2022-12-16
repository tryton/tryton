# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import production
from . import purchase

__all__ = ['register']


def register():
    Pool.register(
        production.Routing,
        production.Production,
        purchase.Line,
        module='production_outsourcing', type_='model')
    Pool.register(
        module='production_outsourcing', type_='wizard')
    Pool.register(
        module='production_outsourcing', type_='report')

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import party
from . import sale


def register():
    Pool.register(
        party.Party,
        sale.Sale,
        module='sale_credit_limit', type_='model')

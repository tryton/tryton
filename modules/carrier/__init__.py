# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import carrier
from . import party


def register():
    Pool.register(
        carrier.Carrier,
        carrier.Selection,
        module='carrier', type_='model')
    Pool.register(
        party.Replace,
        module='carrier', type_='wizard')

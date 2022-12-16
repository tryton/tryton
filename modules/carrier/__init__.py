# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .carrier import *
from .party import PartyReplace


def register():
    Pool.register(
        Carrier,
        CarrierSelection,
        module='carrier', type_='model')
    Pool.register(
        PartyReplace,
        module='carrier', type_='wizard')

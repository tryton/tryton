# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import party
from . import address


def register():
    Pool.register(
        party.Party,
        address.Address,
        module='party_siret', type_='model')

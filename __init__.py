# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import country


def register():
    Pool.register(
        country.Country,
        country.Subdivision,
        country.Zip,
        module='country', type_='model')

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool


def register():
    # Prevent to import backend when importing scripts
    from . import country
    Pool.register(
        country.Country,
        country.Subdivision,
        country.Zip,
        module='country', type_='model')

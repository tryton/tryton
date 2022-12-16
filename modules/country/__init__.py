# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool


def register():
    # Prevent to import backend when importing scripts
    from . import country
    Pool.register(
        country.Organization,
        country.OrganizationMember,
        country.Region,
        country.Country,
        country.Subdivision,
        country.PostalCode,
        module='country', type_='model')

# This file is part of Tryton. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import account


def register():
    Pool.register(
        account.TaxTemplate,
        module='account_de_skr03', type_='model')

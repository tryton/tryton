# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    intrastat_currency = fields.Function(
        fields.Many2One('currency.currency', "Intrastat Currency"),
        'get_intrastat_currency')

    @classmethod
    def get_intrastat_currency(cls, companies, name):
        pool = Pool()
        Currency = pool.get('currency.currency')

        currencies = {}
        eur = None
        for company in companies:
            if company.currency.code == 'EUR':
                currency = company.currency
            else:
                if not eur:
                    eur, = Currency.search([('code', '=', 'EUR')], limit=1)
                currency = eur
            currencies[company.id] = currency
        return currencies

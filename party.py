# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = ['PartyReplace', 'PartyErase']


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('sale.sale', 'party'),
            ('sale.sale', 'shipment_party'),
            ]


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    @classmethod
    def __setup__(cls):
        super(PartyErase, cls).__setup__()
        cls._error_messages.update({
                'pending_sale': (
                    'The party "%(party)s" can not be erased '
                    'because he has pending sales '
                    'for the company "%(company)s".'),
                })

    def check_erase_company(self, party, company):
        pool = Pool()
        Sale = pool.get('sale.sale')
        super(PartyErase, self).check_erase_company(party, company)

        sales = Sale.search([
                ['OR',
                    ('party', '=', party.id),
                    ('shipment_party', '=', party.id),
                    ],
                ('state', 'not in', ['done', 'cancel']),
                ])
        if sales:
            self.raise_user_error('pending_sale', {
                    'party': party.rec_name,
                    'company': company.rec_name,
                    })

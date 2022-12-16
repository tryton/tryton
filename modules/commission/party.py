# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = ['PartyReplace', 'PartyErase']


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('commission.agent', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    @classmethod
    def __setup__(cls):
        super(PartyErase, cls).__setup__()
        cls._error_messages.update({
                'pending_commission': (
                    'The party "%(party)s" can not be erased '
                    'because he has pending commissions '
                    'for the company "%(company)s".'),
                })

    def check_erase_company(self, party, company):
        pool = Pool()
        Commission = pool.get('commission')
        super(PartyErase, self).check_erase_company(party, company)

        commissions = Commission.search([
                ('agent.party', '=', party.id),
                ('invoice_line', '=', None),
                ])
        if commissions:
            self.raise_user_error('pending_commission', {
                    'party': party.rec_name,
                    'company': company.rec_name,
                    })

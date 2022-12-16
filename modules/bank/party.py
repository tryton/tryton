#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields


__all__ = ['Party']
__metaclass__ = PoolMeta


class Party:
    __name__ = 'party.party'
    bank_accounts = fields.Many2Many('bank.account-party.party', 'owner',
        'account', 'Bank Accounts')

    @classmethod
    def search_rec_name(cls, name, clause):
        result = super(Party, cls).search_rec_name(name, clause)
        parties = cls.search([('bank_accounts',) + tuple(clause[1:])],
            order=[])
        if parties:
            parties += cls.search(result, order=[])
            return [('id', 'in', [p.id for p in parties])]
        return result

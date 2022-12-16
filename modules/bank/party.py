# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields


__all__ = ['Party', 'PartyReplace']


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'
    bank_accounts = fields.Many2Many('bank.account-party.party', 'owner',
        'account', 'Bank Accounts')

    @classmethod
    def search_rec_name(cls, name, clause):
        domain = super(Party, cls).search_rec_name(name, clause)
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            domain,
            ('bank_accounts',) + tuple(clause[1:]),
            ]


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('bank', 'party'),
            ('bank.account-party.party', 'owner'),
            ]

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Party(metaclass=PoolMeta):
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
            ('bank_accounts.numbers.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def copy(cls, parties, default=None):
        context = Transaction().context
        default = default.copy() if default else {}
        if context.get('_check_access'):
            default.setdefault(
                'bank_accounts',
                cls.default_get(
                    ['bank_accounts'],
                    with_rec_name=False).get('bank_accounts'))
        return super().copy(parties, default=default)


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('bank', 'party'),
            ('bank.account-party.party', 'owner'),
            ]

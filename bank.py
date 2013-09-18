#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


__all__ = ['Bank', 'BankAccount', 'BankAccountNumber', 'BankAccountParty']


class Bank(ModelSQL, ModelView):
    'Bank'
    __name__ = 'bank'
    _rec_name = 'party'
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE')
    bic = fields.Char('BIC', size=11, help='Bank/Business Identifier Code')

    def get_rec_name(self, name):
        return self.party.rec_name


class BankAccount(ModelSQL, ModelView):
    'Bank Account'
    __name__ = 'bank.account'
    bank = fields.Many2One('bank', 'Bank', required=True)
    owners = fields.Many2Many('bank.account-party.party', 'account', 'owner',
        'Owners')
    currency = fields.Many2One('currency.currency', 'Currency')
    numbers = fields.One2Many('bank.account.number', 'account', 'Numbers',
        required=True)

    def get_rec_name(self, name):
        return self.numbers[0].number

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('numbers',) + tuple(clause[1:])]


class BankAccountNumber(ModelSQL, ModelView):
    'Bank Account Number'
    __name__ = 'bank.account.number'
    _rec_name = 'number'
    account = fields.Many2One('bank.account', 'Account', required=True,
        ondelete='CASCADE')
    type = fields.Selection([
            ('iban', 'IBAN'),
            ('other', 'Other'),
            ], 'Type', required=True)
    number = fields.Char('Number')
    sequence = fields.Integer('Sequence')

    @classmethod
    def __setup__(cls):
        super(BankAccountNumber, cls).__setup__()
        cls._order.insert(0, ('account', 'ASC'))
        cls._order.insert(1, ('sequence', 'ASC'))

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    # TODO validate IBAN


class BankAccountParty(ModelSQL, ModelView):
    'Bank Account - Party'
    __name__ = 'bank.account-party.party'
    account = fields.Many2One('bank.account', 'Account',
        ondelete='CASCADE', select=True, required=True)
    owner = fields.Many2One('party.party', 'Owner', ondelete='CASCADE',
        select=True, required=True)

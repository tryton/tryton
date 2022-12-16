#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from stdnum import iban

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
        cls._error_messages.update({
                'invalid_iban': 'Invalid IBAN "%s".',
                })

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    @property
    def compact_iban(self):
        return (iban.compact(self.number) if self.type == 'iban'
            else self.number)

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if values.get('type') == 'iban' and 'number' in values:
                values['number'] = iban.format(values['number'])
        return super(BankAccountNumber, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for numbers, values in zip(actions, actions):
            values = values.copy()
            if values.get('type') == 'iban' and 'number' in values:
                values['number'] = iban.format(values['number'])
            args.extend((numbers, values))

        super(BankAccountNumber, cls).write(*args)

        to_write = []
        for number in sum(args[::2], []):
            if number.type == 'iban':
                formated_number = iban.format(number.number)
                if formated_number != number.number:
                    to_write.extend(([number], {
                                'number': formated_number,
                                }))
        if to_write:
            cls.write(*to_write)

    @fields.depends('type', 'number')
    def pre_validate(self):
        super(BankAccountNumber, self).pre_validate()
        if (self.type == 'iban' and self.number
                and not iban.is_valid(self.number)):
            self.raise_user_error('invalid_iban', self.number)


class BankAccountParty(ModelSQL):
    'Bank Account - Party'
    __name__ = 'bank.account-party.party'
    account = fields.Many2One('bank.account', 'Account',
        ondelete='CASCADE', select=True, required=True)
    owner = fields.Many2One('party.party', 'Owner', ondelete='CASCADE',
        select=True, required=True)

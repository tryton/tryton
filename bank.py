# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import stdnum.exceptions
from sql import Literal, operators
from sql.operators import Equal
from stdnum import bic, iban

try:
    from schwifty import BIC, IBAN
except ImportError:
    BIC = IBAN = None

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Exclude, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import Pool
from trytond.tools import lstrip_wildcard

from .exceptions import AccountValidationError, IBANValidationError, InvalidBIC


class Bank(ModelSQL, ModelView):
    'Bank'
    __name__ = 'bank'
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE')
    bic = fields.Char('BIC', size=11, help="Bank/Business Identifier Code.")

    def get_rec_name(self, name):
        return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        bic_value = clause[2]
        if clause[1].endswith('like'):
            bic_value = lstrip_wildcard(clause[2])
        return [bool_op,
            ('party.rec_name',) + tuple(clause[1:]),
            ('bic', clause[1], bic_value) + tuple(clause[3:]),
            ]

    @fields.depends('bic')
    def on_change_with_bic(self):
        try:
            return bic.compact(self.bic)
        except stdnum.exceptions.ValidationError:
            pass
        return self.bic

    def pre_validate(self):
        super().pre_validate()
        self.check_bic()

    @fields.depends('bic')
    def check_bic(self):
        if self.bic and not bic.is_valid(self.bic):
            raise InvalidBIC(gettext('bank.msg_invalid_bic', bic=self.bic))

    @classmethod
    def from_bic(cls, bic):
        "Return or create bank from BIC instance"
        pool = Pool()
        Party = pool.get('party.party')
        if IBAN:
            assert isinstance(bic, BIC)
            banks = cls.search([
                    ('bic', '=', bic.compact),
                    ], limit=1)
            if banks:
                bank, = banks
                return bank
            cls.lock()
            names = bic.bank_names
            if names:
                name = names[0]
            else:
                name = None
            bank = cls(party=Party(name=name), bic=bic.compact)
            bank.save()
            return bank


class Account(DeactivableMixin, ModelSQL, ModelView):
    'Bank Account'
    __name__ = 'bank.account'
    bank = fields.Many2One(
        'bank', "Bank",
        help="The bank where the account is open.")
    owners = fields.Many2Many('bank.account-party.party', 'account', 'owner',
        'Owners')
    currency = fields.Many2One('currency.currency', 'Currency')
    numbers = fields.One2Many('bank.account.number', 'account', 'Numbers',
        help="Add the numbers which identify the bank account.")

    def get_rec_name(self, name):
        if self.numbers:
            number = self.numbers[0].number
        else:
            number = '(%s)' % self.id
        name = '%s @ %s' % (number, self.bank.rec_name)
        if self.currency:
            name += ' [%s]' % self.currency.code
        return name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('bank.rec_name',) + tuple(clause[1:]),
            ('currency.rec_name',) + tuple(clause[1:]),
            ('numbers.rec_name',) + tuple(clause[1:]),
            ]

    @property
    def iban(self):
        for number in self.numbers:
            if number.type == 'iban':
                return number.number

    @classmethod
    def validate(cls, accounts):
        super().validate(accounts)
        for account in accounts:
            account.check_bank()

    def check_bank(self):
        if not self.bank or not self.bank.bic:
            return
        if IBAN:
            iban = IBAN(self.iban)
            if iban.bic and iban.bic != self.bank.bic:
                raise AccountValidationError(
                    gettext('bank.msg_invalid_iban_bic',
                        account=self.rec_name,
                        bic=iban.bic))

    @classmethod
    def create(cls, vlist):
        accounts = super().create(vlist)
        for account in accounts:
            if not account.bank:
                bank = account.guess_bank()
                if bank:
                    account.bank = bank
        cls.save(accounts)
        return accounts

    def guess_bank(self):
        pool = Pool()
        Bank = pool.get('bank')
        if IBAN:
            iban = IBAN(self.iban)
            if iban.bic:
                return Bank.from_bic(iban.bic)


class AccountNumber(sequence_ordered(), ModelSQL, ModelView):
    'Bank Account Number'
    __name__ = 'bank.account.number'
    _rec_name = 'number'
    account = fields.Many2One('bank.account', 'Account', required=True,
        ondelete='CASCADE', select=True,
        help="The bank account which is identified by the number.")
    type = fields.Selection([
            ('iban', 'IBAN'),
            ('other', 'Other'),
            ], 'Type', required=True)
    number = fields.Char('Number')
    number_compact = fields.Char('Number Compact', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('number_iban_exclude',
                Exclude(table, (table.number_compact, Equal),
                    where=table.type == 'iban'),
                'bank.msg_number_iban_unique'),
            ('account_iban_exclude',
                Exclude(table, (table.account, Equal),
                    where=table.type == 'iban'),
                'bank.msg_account_iban_unique'),
            ]
        cls.__access__.add('account')
        cls._order.insert(0, ('account', 'ASC'))

    @classmethod
    def default_type(cls):
        return 'iban'

    @classmethod
    def domain_number(cls, domain, tables):
        table, _ = tables[None]
        name, operator, value = domain
        Operator = fields.SQL_OPERATORS[operator]
        result = None
        for field in (cls.number, cls.number_compact):
            column = field.sql_column(table)
            expression = Operator(column, field._domain_value(operator, value))
            if isinstance(expression, operators.In) and not expression.right:
                expression = Literal(False)
            elif (isinstance(expression, operators.NotIn)
                    and not expression.right):
                expression = Literal(True)
            expression = field._domain_add_null(
                column, operator, value, expression)
            if result:
                result |= expression
            else:
                result = expression
        return result

    @property
    def compact_iban(self):
        return (iban.compact(self.number) if self.type == 'iban'
            else self.number)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        number_value = clause[2]
        if clause[1].endswith('like'):
            number_value = lstrip_wildcard(clause[2])
        return [bool_op,
            ('number', clause[1], number_value) + tuple(clause[3:]),
            ]

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if values.get('type') == 'iban' and 'number' in values:
                values['number'] = iban.format(values['number'])
                values['number_compact'] = iban.compact(values['number'])
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for numbers, values in zip(actions, actions):
            values = values.copy()
            if values.get('type') == 'iban' and 'number' in values:
                values['number'] = iban.format(values['number'])
                values['number_compact'] = iban.compact(values['number'])
            args.extend((numbers, values))

        super().write(*args)

        to_write = []
        for number in sum(args[::2], []):
            if number.type == 'iban':
                formated_number = iban.format(number.number)
                compacted_number = iban.compact(number.number)
                if ((formated_number != number.number)
                        or (compacted_number != number.number_compact)):
                    to_write.extend(([number], {
                                'number': formated_number,
                                'number_compact': compacted_number,
                                }))
        if to_write:
            cls.write(*to_write)

    @fields.depends('type', 'number')
    def pre_validate(self):
        super().pre_validate()
        if (self.type == 'iban' and self.number
                and not iban.is_valid(self.number)):
            raise IBANValidationError(
                gettext('bank.msg_invalid_iban',
                    number=self.number))


class AccountParty(ModelSQL):
    'Bank Account - Party'
    __name__ = 'bank.account-party.party'
    account = fields.Many2One('bank.account', 'Account',
        ondelete='CASCADE', select=True, required=True)
    owner = fields.Many2One('party.party', 'Owner', ondelete='CASCADE',
        select=True, required=True)

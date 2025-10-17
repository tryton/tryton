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
    DeactivableMixin, Exclude, Index, ModelSQL, ModelView, fields,
    sequence_ordered)
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.tools import is_full_text, lstrip_wildcard

from .exceptions import AccountValidationError, IBANValidationError, InvalidBIC


class Bank(ModelSQL, ModelView):
    __name__ = 'bank'
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE')
    bic = fields.Char('BIC', size=11, help="Bank/Business Identifier Code.")

    def get_rec_name(self, name):
        return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        bic_value = operand
        if operator.endswith('like') and is_full_text(operand):
            bic_value = lstrip_wildcard(operand)
        return [bool_op,
            ('party.rec_name', operator, operand, *extra),
            ('bic', operator, bic_value, *extra),
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
            bank.party.save()
            bank.save()
            return bank


class Account(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'bank.account'
    bank = fields.Many2One(
        'bank', "Bank",
        help="The bank where the account is open.")
    owners = fields.Many2Many('bank.account-party.party', 'account', 'owner',
        'Owners')
    owners_sequence = fields.Integer("Owners Sequence")
    currency = fields.Many2One('currency.currency', 'Currency')
    numbers = fields.One2Many(
        'bank.account.number', 'account', 'Numbers',
        domain=[
            If(~Eval('active'), ('active', '=', False), ()),
            ],
        help="Add the numbers which identify the bank account.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls._sql_indexes.add(
            Index(table,
                (table.owners_sequence, Index.Range(order='ASC NULLS FIRST')),
                (table.id, Index.Range(order='ASC'))))

    def get_rec_name(self, name):
        for number in self.numbers:
            if number.number:
                name = number.number
                break
        else:
            name = '(%s)' % self.id
        if self.bank:
            name += ' @ %s' % self.bank.rec_name
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
        if IBAN and BIC and self.iban:
            iban = IBAN(self.iban)
            bic = BIC(self.bank.bic)
            if (iban.bic
                    and iban.bic != bic
                    and (
                        iban.country_code != bic.country_code
                        or (iban.bank_code or iban.branch_code)
                        not in bic.domestic_bank_codes)):
                raise AccountValidationError(
                    gettext('bank.msg_account_iban_invalid_bic',
                        account=self.rec_name,
                        bic=iban.bic))

    @classmethod
    def on_modification(cls, mode, accounts, field_names=None):
        super().on_modification(mode, accounts, field_names=field_names)
        if mode == 'create':
            for account in accounts:
                if not account.bank:
                    bank = account.guess_bank()
                    if bank:
                        account.bank = bank
            cls.save(accounts)

    def guess_bank(self):
        pool = Pool()
        Bank = pool.get('bank')
        if IBAN and self.iban:
            iban = IBAN(self.iban)
            if iban.bic:
                return Bank.from_bic(iban.bic)


class AccountNumber(DeactivableMixin, sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'bank.account.number'
    _rec_name = 'number'
    account = fields.Many2One(
        'bank.account', "Account", required=True, ondelete='CASCADE',
        domain=[
            If(Eval('active'), ('active', '=', True), ()),
            ],
        help="The bank account which is identified by the number.")
    type = fields.Selection([
            ('iban', 'IBAN'),
            ('other', 'Other'),
            ], 'Type', required=True)
    number = fields.Char("Number", required=True)
    number_compact = fields.Char(
        "Number Compact", readonly=True,
        states={
            'required': Eval('type').in_(['iban']),
            })

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        cls.number_compact.search_unaccented = False
        super().__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('number_iban_active_exclude',
                Exclude(table, (table.number_compact, Equal),
                    where=(table.type == 'iban') & table.active),
                'bank.msg_number_iban_unique'),
            ('account_iban_active_exclude',
                Exclude(table, (table.account, Equal),
                    where=(table.type == 'iban') & table.active),
                'bank.msg_account_iban_unique'),
            ]
        cls.__access__.add('account')
        cls._order.insert(0, ('account', 'ASC'))

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        super().__register__(module)

        # Migration from 7.0: replace iban exclude
        table_h.drop_constraint('number_iban_exclude')
        table_h.drop_constraint('account_iban_exclude')

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
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create':
            if (values.get('type') == 'iban'
                    and (number := values.get('number'))):
                values['number'] = iban.format(number)
                values['number_compact'] = iban.compact(number)
        return values

    def compute_fields(self, field_names=None):
        values = super().compute_fields(field_names=field_names)
        if ((not field_names or {'type', 'number'} & field_names)
                and getattr(self, 'type', None) == 'iban'):
            number = getattr(self, 'number', None)
            if number:
                number = iban.format(number)
                number_compact = iban.compact(number)
                if getattr(self, 'number') != number:
                    values['number'] = number
                if getattr(self, 'number_compact', None) != number_compact:
                    values['number_compact'] = number_compact
        return values

    @fields.depends('type', 'number')
    def pre_validate(self):
        super().pre_validate()
        if (self.type == 'iban' and self.number
                and not iban.is_valid(self.number)):
            raise IBANValidationError(
                gettext('bank.msg_invalid_iban',
                    number=self.number))


class AccountParty(ModelSQL):
    __name__ = 'bank.account-party.party'
    account = fields.Many2One(
        'bank.account', "Account", ondelete='CASCADE', required=True)
    owner = fields.Many2One(
        'party.party', "Owner", ondelete='CASCADE', required=True)

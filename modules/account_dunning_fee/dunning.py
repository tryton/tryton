# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.model import ModelView, ModelSQL, DeactivableMixin, fields, Unique
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Fee(DeactivableMixin, ModelSQL, ModelView):
    'Account Dunning Fee'
    __name__ = 'account.dunning.fee'
    name = fields.Char('Name', required=True, translate=True)
    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'service'),
            ('template.type', '=', 'service'),
            ])
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    compute_method = fields.Selection([
            ('list_price', 'List Price'),
            ('percentage', 'Percentage'),
            ], 'Compute Method', required=True,
        help='Method to compute the fee amount')
    percentage = fields.Numeric('Percentage', digits=(16, 8),
        states={
            'invisible': Eval('compute_method') != 'percentage',
            'required': Eval('compute_method') == 'percentage',
            },
        depends=['compute_method'])

    def get_amount(self, dunning):
        'Return fee amount and currency'
        amount, currency = None, None
        if self.compute_method == 'list_price':
            assert Transaction().context.get('company') == dunning.company.id
            currency = dunning.company.currency
            amount = currency.round(self.product.list_price)
        elif self.compute_method == 'percentage':
            if dunning.second_currency:
                amount = dunning.amount_second_currency
                currency = dunning.second_currency
            else:
                amount = dunning.amount
                currency = dunning.company.currency
            amount = currency.round(amount * self.percentage)
        return amount, currency


class Level(metaclass=PoolMeta):
    __name__ = 'account.dunning.level'
    fee = fields.Many2One('account.dunning.fee', 'Fee')


class Dunning(metaclass=PoolMeta):
    __name__ = 'account.dunning'

    fees = fields.One2Many(
        'account.dunning.fee.dunning_level', 'dunning', 'Fees', readonly=True)

    @classmethod
    def process(cls, dunnings):
        pool = Pool()
        FeeDunningLevel = pool.get('account.dunning.fee.dunning_level')

        fees = []
        for dunning in dunnings:
            if dunning.blocked or not dunning.level.fee:
                continue
            if dunning.level in {f.level for f in dunning.fees}:
                continue
            fee = FeeDunningLevel(dunning=dunning, level=dunning.level)
            fee.amount, fee.currency = dunning.level.fee.get_amount(dunning)
            fees.append(fee)
        FeeDunningLevel.save(fees)
        FeeDunningLevel.process(fees)

        super(Dunning, cls).process(dunnings)


class FeeDunningLevel(ModelSQL, ModelView):
    'Account Dunning Fee Dunning-Level'
    __name__ = 'account.dunning.fee.dunning_level'

    dunning = fields.Many2One(
        'account.dunning', 'Dunning', required=True, select=True)
    level = fields.Many2One('account.dunning.level', 'Level', required=True)
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency')
    moves = fields.One2Many('account.move', 'origin', 'Moves', readonly=True)

    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')

    @classmethod
    def __setup__(cls):
        super(FeeDunningLevel, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('dunning_level_unique', Unique(t, t.dunning, t.level),
                'account_dunning_fee.msg_fee_dunning_level_unique'),
            ]

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    def get_rec_name(self, name):
        return '%s @ %s' % (self.dunning.rec_name, self.level.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('dunning.rec_name',) + tuple(clause[1:]),
            ('level.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def process(cls, fees):
        pool = Pool()
        Move = pool.get('account.move')
        moves = []
        for fee in fees:
            move = fee.get_move_process()
            moves.append(move)
        Move.save(moves)
        Move.post(moves)

    def get_move_process(self):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Date = pool.get('ir.date')
        Period = pool.get('account.period')
        Currency = pool.get('currency.currency')

        today = Date.today()
        move = Move()
        move.company = self.dunning.company
        move.journal = self.level.fee.journal
        move.date = today
        move.period = Period.find(move.company.id, date=today)
        move.origin = self
        move.description = self.level.fee.name

        line = Line()
        if self.currency == move.company.currency:
            line.debit = self.amount
        else:
            line.second_currency = self.currency
            line.amount_second_currency = self.amount
            line.debit = Currency.compute(
                self.currency, self.amount, move.company.currency)
        line.account = self.dunning.line.account
        line.party = self.dunning.line.party

        counterpart = Line()
        counterpart.credit = line.debit
        counterpart.account = self.level.fee.product.account_revenue_used
        if counterpart.account and counterpart.account.party_required:
            counterpart.party = self.dunning.party

        move.lines = [line, counterpart]
        return move

    # TODO create move with taxes on reconcile of process move line


class Letter(metaclass=PoolMeta):
    __name__ = 'account.dunning.letter'

    @classmethod
    def get_party_letter(cls):
        PartyLetter = super(Letter, cls).get_party_letter()

        class PartyLetterFee(PartyLetter):

            @property
            def fees(self):
                fees = defaultdict(int)
                fees.update(super(PartyLetterFee, self).fees)
                for dunning in self.dunnings:
                    for fee in dunning.fees:
                        fees[fee.currency] += fee.amount
                return fees

        return PartyLetterFee

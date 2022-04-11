# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    statement_lines = fields.One2Many(
        'account.statement.line', 'related_to', "Statement Lines",
        readonly=True)

    @property
    def clearing_lines(self):
        clearing_account = self.journal.clearing_account
        yield from super().clearing_lines
        for statement_line in self.statement_lines:
            if statement_line.move:
                for line in statement_line.move.lines:
                    if line.account == clearing_account:
                        yield line


class PaymentGroup(metaclass=PoolMeta):
    __name__ = 'account.payment.group'

    statement_lines = fields.One2Many(
        'account.statement.line', 'related_to', "Statement Lines",
        readonly=True)

    @property
    def clearing_lines(self):
        clearing_account = self.journal.clearing_account
        yield from super().clearing_lines
        for statement_line in self.statement_lines:
            if statement_line.move:
                for line in statement_line.move.lines:
                    if line.account == clearing_account:
                        yield line


class Statement(metaclass=PoolMeta):
    __name__ = 'account.statement'

    @classmethod
    def create_move(cls, statements):
        pool = Pool()
        Payment = pool.get('account.payment')

        moves = super(Statement, cls).create_move(statements)

        to_success = defaultdict(set)
        to_fail = defaultdict(set)
        for move, statement, lines in moves:
            for line in lines:
                if line.payment:
                    payments = {line.payment}
                    kind = line.payment.kind
                elif line.payment_group:
                    payments = set(line.payment_group.payments)
                    kind = line.payment_group.kind
                else:
                    continue
                if (kind == 'receivable') == (line.amount >= 0):
                    to_success[line.date].update(payments)
                else:
                    to_fail[line.date].update(payments)
        # The failing should be done last because success is usually not a
        # definitive state
        if to_success:
            for date, payments in to_success.items():
                with Transaction().set_context(clearing_date=date):
                    Payment.succeed(Payment.browse(payments))
        if to_fail:
            for date, payments in to_fail.items():
                with Transaction().set_context(clearing_date=date):
                    Payment.fail(Payment.browse(payments))

        Payment.__queue__.reconcile_clearing(
            list(set.union(*to_success.values(), *to_fail.values())))
        return moves

    def _group_key(self, line):
        key = super(Statement, self)._group_key(line)
        if hasattr(line, 'payment'):
            key += (('payment', line.payment),)
        return key


class StatementLine(metaclass=PoolMeta):
    __name__ = 'account.statement.line'

    @classmethod
    def __setup__(cls):
        super(StatementLine, cls).__setup__()
        cls.related_to.domain['account.payment'] = [
            cls.related_to.domain.get('account.payment', []),
            If(Eval('statement_state') == 'draft',
                ('clearing_reconciled', '!=', True),
                ()),
            ]
        cls.related_to.domain['account.payment.group'] = [
            ('company', '=', Eval('company', -1)),
            ('currency', '=', Eval('currency', -1)),
            If(Eval('statement_state') == 'draft',
                ('clearing_reconciled', '!=', True),
                ()),
            ]

    @classmethod
    def _get_relations(cls):
        return super()._get_relations() + ['account.payment.group']

    @property
    @fields.depends('related_to')
    def payment_group(self):
        pool = Pool()
        PaymentGroup = pool.get('account.payment.group')
        related_to = getattr(self, 'related_to', None)
        if isinstance(related_to, PaymentGroup) and related_to.id >= 0:
            return related_to

    @payment_group.setter
    def payment_group(self, value):
        self.related_to = value

    @fields.depends(methods=['payment', 'payment_group'])
    def on_change_related_to(self):
        super().on_change_related_to()
        if self.payment:
            clearing_account = self.payment.journal.clearing_account
            if clearing_account:
                self.account = clearing_account
        if self.payment_group:
            self.party = None
            clearing_account = self.payment_group.journal.clearing_account
            if clearing_account:
                self.account = clearing_account

    @fields.depends('party', methods=['payment'])
    def on_change_party(self):
        super(StatementLine, self).on_change_party()
        if self.payment:
            if self.payment.party != self.party:
                self.payment = None
        if self.party:
            self.payment_group = None

    @fields.depends('account', methods=['payment', 'payment_group'])
    def on_change_account(self):
        super(StatementLine, self).on_change_account()
        if self.payment:
            clearing_account = self.payment.journal.clearing_account
        elif self.payment_group:
            clearing_account = self.payment_group.journal.clearing_account
        else:
            return
        if self.account != clearing_account:
            self.payment = None

    @classmethod
    def post_move(cls, lines):
        pool = Pool()
        Move = pool.get('account.move')
        super(StatementLine, cls).post_move(lines)
        Move.post([l.payment.clearing_move for l in lines
                if l.payment
                and l.payment.clearing_move
                and l.payment.clearing_move.state == 'draft'])


class StatementRuleLine(metaclass=PoolMeta):
    __name__ = 'account.statement.rule.line'

    def get_line(self, origin, keywords, **context):
        line = super().get_line(origin, keywords, **context)
        if line:
            line.payment = self._get_payment(origin, keywords)
            if (line.payment and line.party
                    and line.payment.party != line.party):
                return
            line.payment_group = self._get_payment_group(origin, keywords)
        return line

    def _get_payment(self, origin, keywords):
        pool = Pool()
        Payment = pool.get('account.payment')
        if keywords.get('payment'):
            payments = Payment.search([('rec_name', '=', keywords['payment'])])
            if len(payments) == 1:
                payment, = payments
                return payment

    def _get_payment_group(self, origin, keywords):
        pool = Pool()
        Payment = pool.get('account.payment.group')
        if keywords.get('payment_group'):
            groups, = Payment.search(
                [('rec_name', '=', keywords['payment_group'])])
            if len(groups) == 1:
                group, = groups
                return group

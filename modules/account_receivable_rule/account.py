# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt

from sql import Literal, Null
from sql.aggregate import Sum
from sql.operators import Equal

from trytond import backend
from trytond.model import (
    DeactivableMixin, Exclude, ModelSQL, ModelView, Unique, Workflow,
    dualmethod, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import sqlite_apply_types
from trytond.transaction import Transaction


class Account(metaclass=PoolMeta):
    __name__ = 'account.account'

    receivable_rules = fields.One2Many(
        'account.account.receivable.rule', 'account',
        "Receivable Rules", readonly=True)


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['account.account.receivable.rule']


class AccountRuleAbstract(DeactivableMixin, ModelSQL, ModelView):

    company = fields.Many2One(
        'company.company', "Company", required=True, ondelete='CASCADE')
    account = fields.Many2One(
        'account.account', "Account", required=True, ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    journal = fields.Many2One(
        'account.journal', "Journal", required=True, ondelete='CASCADE',
        domain=[
            ('type', '=', 'general'),
            ],
        context={
            'company': Eval('company', -1),
            })
    priorities = fields.Selection([
            ('maturity_date|account', "Maturity Date, Account"),
            ('account|maturity_date', "Account, Maturity Date"),
            ], "Priorities", required=True)

    accounts = NotImplemented

    overflow_account = fields.Many2One(
        'account.account', "Overflow Account", ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('id', '!=', Eval('account', -1)),
            ('party_required', '=', Eval('account_party_required', None)),
            ('type.receivable', '=', Eval('account_receivable', None)),
            ('type.payable', '=', Eval('account_payable', None)),
            ],
        help="The account to move exceeded amount.\n"
        "Leave empty to keep it in the current account.")

    account_party_required = fields.Function(fields.Boolean(
            "Account Party Required"), 'on_change_with_account_party_required')
    account_receivable = fields.Function(fields.Boolean(
            "Account Receivable"), 'on_change_with_account_receivable')
    account_payable = fields.Function(fields.Boolean(
            "Account Payable"), 'on_change_with_account_payable')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.account.domain = [
            cls.account.domain,
            cls._account_domain(),
            ]
        t = cls.__table__()
        cls._sql_constraints = [
            ('account_exclude', Exclude(
                    t, (t.account, Equal), where=t.active == Literal(True)),
                'account_receivable_rule.msg_account_unique'),
            ]
        cls._order.insert(0, ('account', 'ASC'))
        cls._buttons.update({
                'apply': {},
                })

    @classmethod
    def _account_domain(cls):
        raise NotImplementedError

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('account', '_parent_account.party_required')
    def on_change_with_account_party_required(self, name=None):
        if self.account:
            return self.account.party_required

    @fields.depends('account', '_parent_account.type')
    def on_change_with_account_receivable(self, name=None):
        if self.account and self.account.type:
            return self.account.type.receivable

    @fields.depends('account', '_parent_account.type')
    def on_change_with_account_payable(self, name=None):
        if self.account and self.account.type:
            return self.account.type.payable

    def get_account_rule(self, account):
        for account_rule in self.accounts:
            if account_rule.account == account:
                return account_rule

    @dualmethod
    @ModelView.button
    def apply(cls, rules=None):
        pool = Pool()
        User = pool.get('res.user')
        Move = pool.get('account.move')
        company = User(Transaction().user).company
        if rules is None:
            rules = cls.search([
                    ('company', '=', company.id),
                    ])
        moves = []
        for rule in rules:
            moves.extend(rule._apply())
        Move.post(moves)

    def _apply(self):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        moves = []
        lines = []
        to_reconcile = []
        to_reconcile_delegate = []
        for party, amount in self._amounts():
            for line in self._lines_to_reconcile(party):
                line_amount = -self._amount(line)
                account_rule = self.get_account_rule(line.account)
                if line_amount <= amount:
                    move, m_lines, reconcile, delegate_to = self._reconcile(
                        line, line_amount)
                    moves.append(move)
                    lines.extend(m_lines)
                    if reconcile:
                        if delegate_to:
                            to_reconcile_delegate.append(
                                (reconcile, delegate_to))
                        else:
                            to_reconcile.append(reconcile)
                    amount -= line_amount
                    if amount > 0:
                        continue
                elif not account_rule.only_reconcile:
                    move, m_lines, reconcile, delegate_to = self._reconcile(
                        line, amount, delegate=line_amount - amount)
                    moves.append(move)
                    lines.extend(m_lines)
                    if reconcile:
                        if delegate_to:
                            to_reconcile_delegate.append(
                                (reconcile, delegate_to))
                        else:
                            to_reconcile.append(reconcile)
                break
            else:
                if amount > 0 and self.overflow_account:
                    move, m_lines = self._move_overflow(amount, party)
                    moves.append(move)
                    lines.extend(m_lines)
        Move.save(moves)
        Line.save(lines)
        Line.reconcile(*to_reconcile)
        for lines, delegate_to in to_reconcile_delegate:
            Line.reconcile(lines, delegate_to=delegate_to)
        return moves

    def _reconcile(self, line, amount, delegate=None, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        debit, credit = self._debit_credit(amount)

        if date is None:
            with Transaction().set_context(company=self.company.id):
                date = Date.today()
        period = Period.find(self.company, date=date)

        move = Move(
            journal=self.journal,
            period=period,
            date=date,
            origin=self,
            company=self.company,
            )

        lines = [
            Line(
                move=move,
                account=self.account,
                credit=credit,
                debit=debit,
                party=line.party if self.account.party_required else None,
                ),
            Line(
                move=move,
                account=line.account,
                credit=debit,
                debit=credit,
                party=line.party,
                ),
            ]
        if delegate:
            debit, credit = self._debit_credit(delegate)
            lines[1].credit += debit
            lines[1].debit += credit
            lines.append(
                Line(
                    move=move,
                    account=line.account,
                    credit=credit,
                    debit=debit,
                    party=line.party,
                    maturity_date=line.maturity_date,
                    ),
                )
        return move, lines, [line, lines[1]], lines[-1] if delegate else None

    def _move_overflow(self, amount, party, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        debit, credit = self._debit_credit(amount)

        if date is None:
            with Transaction().set_context(company=self.company.id):
                date = Date.today()
        period = Period.find(self.company, date=date)

        move = Move(
            journal=self.journal,
            period=period,
            date=date,
            origin=self,
            company=self.company,
            )

        lines = [
            Line(
                move=move,
                account=self.account,
                credit=credit,
                debit=debit,
                party=party if self.account.party_required else None,
                ),
            Line(
                move=move,
                account=self.overflow_account,
                credit=debit,
                debit=credit,
                party=party if self.overflow_account.party_required else None,
                ),
            ]
        return move, lines

    def _amounts(self):
        "Yield party id and amount to dispatch"
        pool = Pool()
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        line = Line.__table__()
        move = Move.__table__()
        cursor = Transaction().connection.cursor()

        amount = Sum(self._amount(line))
        query = (line
            .join(move, condition=line.move == move.id)
            .select(
                line.party,
                amount.as_('amount'),
                where=(
                    (line.account == self.account.id)
                    & (line.reconciliation == Null)
                    & (move.state == 'posted')),
                group_by=line.party,
                having=amount > 0))
        if backend.name == 'sqlite':
            sqlite_apply_types(query, [None, 'NUMERIC'])
        cursor.execute(*query)
        for party_id, amount in cursor:
            if amount > 0:
                yield party_id, amount

    def _amount(self, line):
        raise NotImplementedError

    def _debit_credit(self, amount):
        raise NotImplementedError

    def _lines_to_reconcile(self, party):
        "Return the list of lines to reconcile ordered per priority"
        pool = Pool()
        Line = pool.get('account.move.line')

        lines = Line.search([
                ('account', 'in', [a.account.id for a in self.accounts]),
                ('party', '=', int(party)),
                ('reconciliation', '=', None),
                ('move.state', '=', 'posted'),
                ],
            order=[])
        lines = filter(lambda l: self._amount(l) < 0, lines)
        return Line.browse(sorted(lines, key=self._line_priority))

    def _line_priority(self, line):
        if self.priorities == 'maturity_date|account':
            account = self.get_account_rule(line.account)
            return (
                line.maturity_date or dt.date.max,
                (account.sequence or 0, account.id),
                )
        elif self.priorities == 'account|maturity_date':
            account = self.get_account_rule(line.account)
            return (
                (account.sequence or 0, account.id),
                line.maturity_date or dt.date.max,
                )


class AccountRuleAccountAbstract(sequence_ordered(), ModelSQL, ModelView):

    rule = NotImplemented

    account = fields.Many2One(
        'account.account', "Account", required=True, ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('id', '!=', Eval('_parent_rule.account', -1)),
            ('party_required', '=', Eval('account_party_required', None)),
            ('reconcile', '=', True),
            ('receivable_rules', '=', None),
            ('type.receivable', '=', Eval('account_receivable', None)),
            ('type.payable', '=', Eval('account_payable', None)),
            ])
    only_reconcile = fields.Boolean(
        "Only Reconcile",
        help="Distribute only to fully reconcile.")

    company = fields.Function(fields.Many2One(
            'company.company', "Company"), 'on_change_with_company')
    account_party_required = fields.Function(fields.Boolean(
            "Account Party Required"), 'on_change_with_account_party_required')
    account_receivable = fields.Function(fields.Boolean(
            "Account Receivable"), 'on_change_with_account_receivable')
    account_payable = fields.Function(fields.Boolean(
            "Account Payable"), 'on_change_with_account_payable')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('rule')
        t = cls.__table__()
        cls._sql_constraints = [
            ('rule_account_unique', Unique(t, t.rule, t.account),
                'account_receivable_rule.msg_rule_account_unique'),
            ]

    @classmethod
    def default_only_reconcile(cls):
        return True

    @fields.depends('rule', '_parent_rule.company')
    def on_change_with_company(self, name=None):
        return self.rule.company if self.rule else None

    @fields.depends('rule', '_parent_rule.account_party_required')
    def on_change_with_account_party_required(self, name=None):
        if self.rule:
            return self.rule.account_party_required

    @fields.depends('rule', '_parent_rule.account_receivable')
    def on_change_with_account_receivable(self, name=None):
        if self.rule:
            return self.rule.account_receivable

    @fields.depends('rule', '_parent_rule.account_payable')
    def on_change_with_account_payable(self, name=None):
        if self.rule:
            return self.rule.account_payable


class AccountReceivableRule(AccountRuleAbstract):
    __name__ = 'account.account.receivable.rule'

    accounts = fields.One2Many(
        'account.account.receivable.rule.account', 'rule', "Accounts",
        states={
            'readonly': ~Eval('account'),
            })

    @classmethod
    def _account_domain(cls):
        return [
            ('type.receivable', '=', True),
            ('type.payable', '!=', True),
            ]

    def _amount(self, line):
        return line.credit - line.debit

    def _debit_credit(self, amount):
        if amount >= 0:
            return amount, 0
        else:
            return 0, -amount


class AccountReceivableRuleAccount(AccountRuleAccountAbstract):
    __name__ = 'account.account.receivable.rule.account'

    rule = fields.Many2One(
        'account.account.receivable.rule', "Rule",
        required=True, ondelete='CASCADE')


class AccountReceivableRule_Dunning(metaclass=PoolMeta):
    __name__ = 'account.account.receivable.rule'

    def _lines_to_reconcile(self, party):
        lines = super()._lines_to_reconcile(party)
        return [l for l in lines if not any(d.blocked for d in l.dunnings)]


class Statement(metaclass=PoolMeta):
    __name__ = 'account.statement'

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, statements):
        pool = Pool()
        Rule = pool.get('account.account.receivable.rule')
        super().post(statements)
        rules = set()
        for statement in statements:
            for line in statement.lines:
                rules.update(line.account.receivable_rules)
        Rule.apply(Rule.browse(rules))

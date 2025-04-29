# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from sql import Literal

from trytond.model import Check, Index, ModelSQL, ModelView, dualmethod, fields
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import StateAction, Wizard


class Line(ModelSQL, ModelView):
    __name__ = 'analytic_account.line'
    debit = Monetary(
        "Debit", currency='currency', digits='currency', required=True,
        domain=[
            If(Eval('credit', 0), ('debit', '=', 0), ()),
            ])
    credit = Monetary(
        "Credit", currency='currency', digits='currency', required=True,
        domain=[
            If(Eval('debit', 0), ('credit', '=', 0), ()),
            ])
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency')
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company', searcher='search_company')
    account = fields.Many2One(
        'analytic_account.account', "Account", required=True,
        domain=[
            ('type', '=', 'normal'),
            ('company', '=', Eval('company', -1)),
            ])
    move_line = fields.Many2One('account.move.line', 'Account Move Line',
            ondelete='CASCADE', required=True)
    date = fields.Date('Date', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('credit_debit_',
                Check(t, t.credit * t.debit == 0),
                'account.msg_line_debit_credit'),
            ]
        cls._sql_indexes.update({
                Index(t, (t.account, Index.Range())),
                Index(t, (t.date, Index.Range())),
                })
        cls._order.insert(0, ('date', 'ASC'))

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_debit():
        return Decimal(0)

    @staticmethod
    def default_credit():
        return Decimal(0)

    @fields.depends('move_line', '_parent_move_line.account')
    def on_change_with_currency(self, name=None):
        if self.move_line and self.move_line.account:
            return self.move_line.account.company.currency

    @fields.depends('move_line', '_parent_move_line.account')
    def on_change_with_company(self, name=None):
        if self.move_line and self.move_line.account:
            return self.move_line.account.company

    @classmethod
    def search_company(cls, name, clause):
        return [('move_line.account.' + clause[0],) + tuple(clause[1:])]

    @fields.depends('move_line', '_parent_move_line.date',
        '_parent_move_line.debit', '_parent_move_line.credit')
    def on_change_move_line(self):
        if self.move_line:
            self.date = self.move_line.date
            self.debit = self.move_line.debit
            self.credit = self.move_line.credit

    @staticmethod
    def query_get(table):
        '''
        Return SQL clause for analytic line depending of the context.
        table is the SQL instance of the analytic_account_line table.
        '''
        clause = Literal(True)
        if Transaction().context.get('start_date'):
            clause &= table.date >= Transaction().context['start_date']
        if Transaction().context.get('end_date'):
            clause &= table.date <= Transaction().context['end_date']
        return clause

    @classmethod
    def on_modification(cls, mode, lines, field_names=None):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        super().on_modification(mode, lines, field_names=field_names)
        if mode in {'create', 'write'}:
            move_lines = MoveLine.browse({l.move_line for l in lines})
            MoveLine.set_analytic_state(move_lines)
            MoveLine.save(move_lines)

    @classmethod
    def on_delete(cls, lines):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        callback = super().on_delete(lines)
        move_lines = MoveLine.browse({l.move_line for l in lines})
        if move_lines:
            def set_state():
                MoveLine.set_analytic_state(move_lines)
                MoveLine.save(move_lines)
            callback.append(set_state)
        return callback


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @dualmethod
    @ModelView.button
    def post(cls, moves):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        super().post(moves)
        lines = [l for m in moves for l in m.lines]
        MoveLine.apply_rule(lines)
        MoveLine.set_analytic_state(lines)
        MoveLine.save(lines)

    def _cancel_default(self, reversal=False):
        default = super()._cancel_default(reversal=reversal)
        if reversal:
            default['lines.analytic_lines.debit'] = (
                lambda data: data['credit'])
            default['lines.analytic_lines.credit'] = (
                lambda data: data['debit'])
        else:
            default['lines.analytic_lines.debit'] = (
                lambda data: data['debit'] * -1)
            default['lines.analytic_lines.credit'] = (
                lambda data: data['credit'] * -1)
        return default


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'
    analytic_lines = fields.One2Many('analytic_account.line', 'move_line',
            'Analytic Lines')
    analytic_state = fields.Selection([
            ('draft', 'Draft'),
            ('valid', 'Valid'),
            ], "Analytic State", readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'apply_analytic_rules': {
                'invisible': Eval('analytic_state') != 'draft',
                'depends': ['analytic_state'],
                },
            })
        cls._check_modify_exclude |= {'analytic_lines', 'analytic_state'}

    @classmethod
    def default_analytic_state(cls):
        return 'draft'

    @property
    def rule_pattern(self):
        return {
            'company': self.move.company.id,
            'account': self.account.id,
            'journal': self.move.journal.id,
            'party': self.party.id if self.party else None,
            }

    @property
    def must_have_analytic(self):
        "If the line must have analytic lines set"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        if self.account.type:
            return self.account.type.statement == 'income' and not (
                # ignore balance move of non-deferral account
                self.journal.type == 'situation'
                and self.period.type == 'adjustment'
                and isinstance(self.move.origin, FiscalYear))

    @classmethod
    def apply_rule(cls, lines):
        pool = Pool()
        Rule = pool.get('analytic_account.rule')

        rules = Rule.search([])

        for line in lines:
            if not line.must_have_analytic:
                continue
            if line.analytic_lines:
                continue
            pattern = line.rule_pattern
            for rule in rules:
                if rule.match(pattern):
                    break
            else:
                continue
            analytic_lines = []
            for entry in rule.analytic_accounts:
                analytic_lines.extend(
                    entry.get_analytic_lines(line, line.date))
            line.analytic_lines = analytic_lines

    @classmethod
    def set_analytic_state(cls, lines):
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')

        roots = AnalyticAccount.search([
                ('parent', '=', None),
                ],
            order=[('company', 'ASC')])
        company2roots = {
            company: set(roots)
            for company, roots in groupby(roots, key=lambda r: r.company)}

        for line in lines:
            if not line.must_have_analytic:
                if not line.analytic_lines:
                    line.analytic_state = 'valid'
                else:
                    line.analytic_state = 'draft'
                continue
            amounts = defaultdict(Decimal)
            for analytic_line in line.analytic_lines:
                amount = analytic_line.debit - analytic_line.credit
                amounts[analytic_line.account.root] += amount
            roots = company2roots.get(line.move.company, set())
            if not roots <= set(amounts.keys()):
                line.analytic_state = 'draft'
                continue
            amount = line.debit - line.credit
            for analytic_amount in amounts.values():
                if analytic_amount != amount:
                    line.analytic_state = 'draft'
                    break
            else:
                line.analytic_state = 'valid'

    @classmethod
    @ModelView.button
    def apply_analytic_rules(cls, lines):
        cls.apply_rule(lines)
        cls.set_analytic_state(lines)
        cls.save(lines)


class OpenAccount(Wizard):
    __name__ = 'analytic_account.line.open_account'
    start_state = 'open_'
    _readonly = True
    open_ = StateAction('analytic_account.act_line_form')

    def do_open_(self, action):
        action['pyson_domain'] = [
            ('account', '=', self.record.id if self.record else None),
            ]
        if Transaction().context.get('start_date'):
            action['pyson_domain'].append(
                ('date', '>=', Transaction().context['start_date'])
                )
        if Transaction().context.get('end_date'):
            action['pyson_domain'].append(
                ('date', '<=', Transaction().context['end_date'])
                )
        if self.record:
            action['name'] += ' (%s)' % self.record.rec_name
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        return action, {}

    def transition_open_(self):
        return 'end'

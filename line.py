# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict

from sql import Literal

from trytond.model import ModelView, ModelSQL, fields, Check
from trytond.wizard import Wizard, StateAction
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta


class Line(ModelSQL, ModelView):
    'Analytic Line'
    __name__ = 'analytic_account.line'
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
        required=True, depends=['currency_digits'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
        required=True, depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company', searcher='search_company')
    account = fields.Many2One('analytic_account.account', 'Account',
        required=True, select=True, domain=[
            ('type', 'not in', ['view', 'distribution']),
            ['OR',
                ('company', '=', None),
                ('company', '=', Eval('company', -1)),
                ],
            ],
        depends=['company'])
    move_line = fields.Many2One('account.move.line', 'Account Move Line',
            ondelete='CASCADE', required=True)
    date = fields.Date('Date', required=True)

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('credit_debit_',
                Check(t, t.credit * t.debit == 0),
                'account.msg_line_debit_credit'),
            ]
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Line, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 4.0: remove name and journal
        for field_name in ['name', 'journal']:
            table.not_null_action(field_name, action='remove')

        # Migration from 5.0: replace credit_debit constraint by credit_debit_
        table.drop_constraint('credit_debit')

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
    def on_change_with_currency_digits(self, name=None):
        if self.move_line and self.move_line.account:
            return self.move_line.account.company.currency.digits
        return 2

    @fields.depends('move_line', '_parent_move_line.account')
    def on_change_with_company(self, name=None):
        if self.move_line and self.move_line.account:
            return self.move_line.account.company.id

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
    def create(cls, vlist):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        lines = super(Line, cls).create(vlist)
        move_lines = [l.move_line for l in lines]
        MoveLine.set_analytic_state(move_lines)
        MoveLine.save(move_lines)
        return lines

    @classmethod
    def write(cls, *args):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        super(Line, cls).write(*args)
        lines = sum(args[0:None:2], [])
        move_lines = [l.move_line for l in lines]
        MoveLine.set_analytic_state(move_lines)
        MoveLine.save(move_lines)

    @classmethod
    def delete(cls, lines):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        move_lines = [l.move_line for l in lines]
        super(Line, cls).delete(lines)
        MoveLine.set_analytic_state(move_lines)
        MoveLine.save(move_lines)


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    @ModelView.button
    def post(cls, moves):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        super(Move, cls).post(moves)
        lines = [l for m in moves for l in m.lines]
        MoveLine.apply_rule(lines)
        MoveLine.set_analytic_state(lines)
        MoveLine.save(lines)

    def cancel(self, default=None):
        'Reverse credit/debit of analytic lines'
        pool = Pool()
        AnalyticLine = pool.get('analytic_account.line')
        cancel_move = super(Move, self).cancel(default)
        analytic_lines = []
        for line in cancel_move.lines:
            for analytic_line in line.analytic_lines:
                analytic_line.debit, analytic_line.credit = (
                    analytic_line.credit, analytic_line.debit)
                analytic_lines.append(analytic_line)
        AnalyticLine.save(analytic_lines)
        return cancel_move


class MoveLine(ModelSQL, ModelView):
    __name__ = 'account.move.line'
    analytic_lines = fields.One2Many('analytic_account.line', 'move_line',
            'Analytic Lines')
    analytic_state = fields.Selection([
            ('draft', 'Draft'),
            ('valid', 'Valid'),
            ], 'Analytic State', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._buttons.update({
            'apply_analytic_rules': {
                'invisible': Eval('analytic_state') != 'draft',
                'depends': ['analytic_state'],
                },
            })
        cls._check_modify_exclude |= {'analytic_lines', 'analytic_state'}

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        state_exist = table.column_exist('analytic_state')

        super(MoveLine, cls).__register__(module_name)

        # Migration from 4.0: add analytic_state
        if not state_exist:
            cursor.execute(
                *sql_table.update([sql_table.analytic_state], ['valid']))

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
                ])
        roots = set(roots)

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
    'Open Account'
    __name__ = 'analytic_account.line.open_account'
    start_state = 'open_'
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

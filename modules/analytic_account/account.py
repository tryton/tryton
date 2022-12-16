# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict

from sql import Column, Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond import backend
from trytond.i18n import gettext
from trytond.model import (ModelView, ModelSQL, DeactivableMixin, fields,
    Unique, tree)
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval, If, PYSONEncoder, PYSONDecoder
from trytond.transaction import Transaction
from trytond.pool import Pool

from .exceptions import AccountValidationError


class Account(
        DeactivableMixin, tree('distribution_parents'), tree(),
        ModelSQL, ModelView):
    'Analytic Account'
    __name__ = 'analytic_account.account'
    name = fields.Char('Name', required=True, translate=True, select=True)
    code = fields.Char('Code', select=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    type = fields.Selection([
        ('root', 'Root'),
        ('view', 'View'),
        ('normal', 'Normal'),
        ('distribution', 'Distribution'),
        ], 'Type', required=True)
    root = fields.Many2One('analytic_account.account', 'Root', select=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('parent', '=', None),
            ('type', '=', 'root'),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            },
        depends=['company', 'type'])
    parent = fields.Many2One('analytic_account.account', 'Parent', select=True,
        domain=['OR',
            ('root', '=', Eval('root', -1)),
            ('parent', '=', None),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            },
        depends=['root', 'type'])
    childs = fields.One2Many('analytic_account.account', 'parent', 'Children',
        states={
            'invisible': Eval('id', -1) < 0,
            },
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    balance = fields.Function(fields.Numeric('Balance',
        digits=(16, Eval('currency_digits', 1)), depends=['currency_digits']),
        'get_balance')
    credit = fields.Function(fields.Numeric('Credit',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_credit_debit')
    debit = fields.Function(fields.Numeric('Debit',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_credit_debit')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('opened', 'Opened'),
        ('closed', 'Closed'),
        ], 'State', required=True)
    note = fields.Text('Note')
    distributions = fields.One2Many(
        'analytic_account.account.distribution', 'parent',
        "Distributions",
        states={
            'invisible': Eval('type') != 'distribution',
            'required': Eval('type') == 'distribution',
            },
        depends=['type'])
    distribution_parents = fields.Many2Many(
        'analytic_account.account.distribution', 'account', 'parent',
        "Distribution Parents", readonly=True)

    @classmethod
    def __setup__(cls):
        super(Account, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))
        cls._order.insert(1, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Account, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 4.0: remove currency
        table.not_null_action('currency', action='remove')

        # Migration from 5.0: remove display_balance
        table.drop_column('display_balance')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_type():
        return 'normal'

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def validate(cls, accounts):
        super(Account, cls).validate(accounts)
        for account in accounts:
            account.check_distribution()

    def check_distribution(self):
        if self.type != 'distribution':
            return
        if sum((d.ratio for d in self.distributions)) != 1:
            raise AccountValidationError(
                gettext('analytic_account.msg_invalid_distribution',
                    account=self.rec_name))

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id

    @fields.depends('company')
    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    @fields.depends('parent', 'type',
        '_parent_parent.id', '_parent_parent.root', '_parent_parent.type')
    def on_change_parent(self):
        if (self.parent and self.parent.id is not None and self.parent.id > 0
                and self.type != 'root'):
            if self.parent.type == 'root':
                self.root = self.parent
            else:
                self.root = self.parent.root
        else:
            self.root = None

    @classmethod
    def get_balance(cls, accounts, name):
        pool = Pool()
        Line = pool.get('analytic_account.line')
        MoveLine = pool.get('account.move.line')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        line = Line.__table__()
        move_line = MoveLine.__table__()

        ids = [a.id for a in accounts]
        childs = cls.search([('parent', 'child_of', ids)])
        all_ids = list({}.fromkeys(ids + [c.id for c in childs]).keys())

        id2account = {}
        all_accounts = cls.browse(all_ids)
        for account in all_accounts:
            id2account[account.id] = account

        line_query = Line.query_get(line)
        cursor.execute(*table.join(line, 'LEFT',
                condition=table.id == line.account
                ).join(move_line, 'LEFT',
                condition=move_line.id == line.move_line
                ).select(table.id,
                Sum(Coalesce(line.credit, 0) - Coalesce(line.debit, 0)),
                where=(table.type != 'view')
                & table.id.in_(all_ids)
                & (table.active == Literal(True)) & line_query,
                group_by=table.id))
        account_sum = defaultdict(Decimal)
        for account_id, value in cursor.fetchall():
            account_sum.setdefault(account_id, Decimal('0.0'))
            # SQLite uses float for SUM
            if not isinstance(value, Decimal):
                value = Decimal(str(value))
            account_sum[account_id] += value

        balances = {}
        for account in accounts:
            balance = Decimal()
            childs = cls.search([
                    ('parent', 'child_of', [account.id]),
                    ])
            for child in childs:
                balance += account_sum[child.id]
            exp = Decimal(str(10.0 ** -account.currency_digits))
            balances[account.id] = balance.quantize(exp)
        return balances

    @classmethod
    def get_credit_debit(cls, accounts, names):
        pool = Pool()
        Line = pool.get('analytic_account.line')
        MoveLine = pool.get('account.move.line')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        line = Line.__table__()
        move_line = MoveLine.__table__()

        result = {}
        ids = [a.id for a in accounts]
        for name in names:
            if name not in ('credit', 'debit'):
                raise Exception('Bad argument')
            result[name] = {}.fromkeys(ids, Decimal('0.0'))

        id2account = {}
        for account in accounts:
            id2account[account.id] = account

        line_query = Line.query_get(line)
        columns = [table.id]
        for name in names:
            columns.append(Sum(Coalesce(Column(line, name), 0)))
        cursor.execute(*table.join(line, 'LEFT',
                condition=table.id == line.account
                ).join(move_line, 'LEFT',
                condition=move_line.id == line.move_line
                ).select(*columns,
                where=(table.type != 'view')
                & table.id.in_(ids)
                & (table.active == Literal(True)) & line_query,
                group_by=table.id))

        for row in cursor.fetchall():
            account_id = row[0]
            for i, name in enumerate(names, 1):
                value = row[i]
                # SQLite uses float for SUM
                if not isinstance(value, Decimal):
                    value = Decimal(str(value))
                result[name][account_id] += value
        for account in accounts:
            for name in names:
                exp = Decimal(str(10.0 ** -account.currency_digits))
                result[name][account.id] = (
                    result[name][account.id].quantize(exp))
        return result

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + str(self.name)
        else:
            return str(self.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        accounts = cls.search([('code',) + tuple(clause[1:])], limit=1)
        if accounts:
            return [('code',) + tuple(clause[1:])]
        else:
            return [(cls._rec_name,) + tuple(clause[1:])]

    def distribute(self, amount):
        "Return a list of (account, amount) distribution"
        assert self.type in {'normal', 'distribution'}
        if self.type == 'normal':
            return [(self, amount)]
        else:
            result = []
            remainder = amount
            for distribution in self.distributions:
                account = distribution.account
                ratio = distribution.ratio
                current_amount = self.currency.round(amount * ratio)
                remainder -= current_amount
                result.extend(account.distribute(current_amount))
            if remainder:
                i = 0
                while remainder:
                    account, amount = result[i]
                    rounding = self.currency.rounding.copy_sign(remainder)
                    result[i] = (account, amount - rounding)
                    remainder -= rounding
                    i = (i + 1) % len(result)
            return result


class OpenChartAccountStart(ModelView):
    'Open Chart of Accounts'
    __name__ = 'analytic_account.open_chart.start'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


class OpenChartAccount(Wizard):
    'Open Chart of Accounts'
    __name__ = 'analytic_account.open_chart'
    start = StateView('analytic_account.open_chart.start',
        'analytic_account.open_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('analytic_account.act_account_tree2')

    def do_open_(self, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'start_date': self.start.start_date,
                'end_date': self.start.end_date,
                })
        return action, {}

    def transition_open_(self):
        return 'end'


class AccountDistribution(ModelView, ModelSQL):
    "Analytic Account Distribution"
    __name__ = 'analytic_account.account.distribution'
    parent = fields.Many2One(
        'analytic_account.account', "Parent", required=True, select=True)
    root = fields.Function(
        fields.Many2One('analytic_account.account', "Root"),
        'on_change_with_root')
    account = fields.Many2One(
        'analytic_account.account', "Account", required=True,
        domain=[
            ('root', '=', Eval('root', -1)),
            ],
        depends=['root'])
    ratio = fields.Numeric("Ratio", required=True,
        domain=[
            ('ratio', '>=', 0),
            ('ratio', '<=', 1),
            ])

    @classmethod
    def __setup__(cls):
        super(AccountDistribution, cls).__setup__()
        cls._order.insert(0, ('ratio', 'DESC'))

    @fields.depends('parent', '_parent_parent.root')
    def on_change_with_root(self, name=None):
        if self.parent:
            return self.parent.root.id


class AnalyticAccountEntry(ModelView, ModelSQL):
    'Analytic Account Entry'
    __name__ = 'analytic.account.entry'
    origin = fields.Reference('Origin', selection='get_origin', select=True)
    root = fields.Many2One(
        'analytic_account.account', "Root Analytic", required=True,
        domain=[
            If(~Eval('company'),
                # No constraint if the origin is not set
                (),
                ('company', '=', Eval('company', -1))),
            ('type', '=', 'root'),
            ],
        depends=['company'])
    account = fields.Many2One('analytic_account.account', 'Account',
        ondelete='RESTRICT',
        domain=[
            ('root', '=', Eval('root')),
            ('type', 'in', ['normal', 'distribution']),
            ],
        depends=['root', 'company'])
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company', searcher='search_company')

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Account = pool.get('analytic_account.account')
        cursor = Transaction().connection.cursor()

        # Migration from 3.4: use origin as the key for One2Many
        migration_3_4 = False
        old_table = 'analytic_account_account_selection_rel'
        if backend.TableHandler.table_exist(old_table):
            backend.TableHandler.table_rename(old_table, cls._table)
            migration_3_4 = True

        # Don't create table before renaming
        table = cls.__table_handler__(module_name)

        super(AnalyticAccountEntry, cls).__register__(module_name)

        # Migration from 3.4: set root value and remove required
        if migration_3_4:
            account = Account.__table__()
            cursor.execute(*account.select(account.id, account.root,
                    where=account.type != 'root'))
            entry = cls.__table__()
            for account_id, root_id in cursor.fetchall():
                cursor.execute(*entry.update(
                        columns=[entry.root],
                        values=[root_id],
                        where=entry.account == account_id))
            table.not_null_action('selection', action='remove')
        table.not_null_action('account', action='remove')

    @classmethod
    def __setup__(cls):
        super(AnalyticAccountEntry, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('root_origin_uniq', Unique(t, t.origin, t.root),
                'analytic_account.msg_root_origin_unique'),
            ]

    @classmethod
    def _get_origin(cls):
        return ['analytic_account.rule']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    def on_change_with_company(self, name=None):
        return None

    @classmethod
    def search_company(cls, name, clause):
        return []

    def get_analytic_lines(self, line, date):
        "Yield analytic lines for the accounting line and the date"
        pool = Pool()
        AnalyticLine = pool.get('analytic_account.line')

        if not self.account:
            return
        amount = line.debit or line.credit
        for account, amount in self.account.distribute(amount):
            analytic_line = AnalyticLine()
            analytic_line.debit = amount if line.debit else Decimal(0)
            analytic_line.credit = amount if line.credit else Decimal(0)
            analytic_line.account = account
            analytic_line.date = date
            yield analytic_line


class AnalyticMixin(object):
    __slots__ = ()
    analytic_accounts = fields.One2Many('analytic.account.entry', 'origin',
        'Analytic Accounts',
        size=Eval('analytic_accounts_size', 0),
        depends=['analytic_accounts_size'])
    analytic_accounts_size = fields.Function(fields.Integer(
            'Analytic Accounts Size'), 'get_analytic_accounts_size')

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        AccountEntry = pool.get('analytic.account.entry')
        cursor = Transaction().connection.cursor()

        super(AnalyticMixin, cls).__register__(module_name)

        handler = cls.__table_handler__(module_name)
        # Migration from 3.4: analytic accounting changed to reference field
        if handler.column_exist('analytic_accounts'):
            entry = AccountEntry.__table__()
            table = cls.__table__()
            cursor.execute(*table.select(table.id, table.analytic_accounts,
                    where=table.analytic_accounts != Null))
            for line_id, selection_id in cursor.fetchall():
                cursor.execute(*entry.update(
                        columns=[entry.origin],
                        values=['%s,%s' % (cls.__name__, line_id)],
                        where=entry.selection == selection_id))
            handler.drop_column('analytic_accounts')

    @classmethod
    def analytic_accounts_domain(cls):
        context = Transaction().context.copy()
        context['context'] = context
        return PYSONDecoder(context).decode(
            PYSONEncoder().encode(cls.analytic_accounts.domain))

    @classmethod
    def default_analytic_accounts(cls):
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')

        accounts = []
        root_accounts = AnalyticAccount.search(
            cls.analytic_accounts_domain() + [
                ('parent', '=', None),
                ])
        for account in root_accounts:
            accounts.append({
                    'root': account.id,
                    })
        return accounts

    @classmethod
    def default_analytic_accounts_size(cls):
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')
        return len(AnalyticAccount.search(
            cls.analytic_accounts_domain() + [
                    ('type', '=', 'root'),
                    ]))

    @classmethod
    def get_analytic_accounts_size(cls, records, name):
        roots = cls.default_analytic_accounts_size()
        return {r.id: roots for r in records}

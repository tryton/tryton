# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from sql import Column
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond import backend
from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Account', 'OpenChartAccountStart', 'OpenChartAccount',
    'AnalyticAccountEntry', 'AnalyticMixin']


class Account(ModelSQL, ModelView):
    'Analytic Account'
    __name__ = 'analytic_account.account'
    name = fields.Char('Name', required=True, translate=True, select=True)
    code = fields.Char('Code', select=True)
    active = fields.Boolean('Active', select=True)
    company = fields.Many2One('company.company', 'Company')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    type = fields.Selection([
        ('root', 'Root'),
        ('view', 'View'),
        ('normal', 'Normal'),
        ], 'Type', required=True)
    root = fields.Many2One('analytic_account.account', 'Root', select=True,
        domain=[
            ('parent', '=', None),
            ('type', '=', 'root'),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            },
        depends=['type'])
    parent = fields.Many2One('analytic_account.account', 'Parent', select=True,
        domain=[('parent', 'child_of', Eval('root'))],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            },
        depends=['root', 'type'])
    childs = fields.One2Many('analytic_account.account', 'parent', 'Children')
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
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    mandatory = fields.Boolean('Mandatory', states={
            'invisible': Eval('type') != 'root',
            },
        depends=['type'])

    @classmethod
    def __setup__(cls):
        super(Account, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_type():
        return 'normal'

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_display_balance():
        return 'credit-debit'

    @staticmethod
    def default_mandatory():
        return False

    @classmethod
    def validate(cls, accounts):
        super(Account, cls).validate(accounts)
        cls.check_recursion(accounts)

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @classmethod
    def get_balance(cls, accounts, name):
        res = {}
        pool = Pool()
        Line = pool.get('analytic_account.line')
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        line = Line.__table__()
        move_line = MoveLine.__table__()
        a_account = Account.__table__()
        company = Company.__table__()

        ids = [a.id for a in accounts]
        childs = cls.search([('parent', 'child_of', ids)])
        all_ids = {}.fromkeys(ids + [c.id for c in childs]).keys()

        id2account = {}
        all_accounts = cls.browse(all_ids)
        for account in all_accounts:
            id2account[account.id] = account

        line_query = Line.query_get(line)
        cursor.execute(*table.join(line, 'LEFT',
                condition=table.id == line.account
                ).join(move_line, 'LEFT',
                condition=move_line.id == line.move_line
                ).join(a_account, 'LEFT',
                condition=a_account.id == move_line.account
                ).join(company, 'LEFT',
                condition=company.id == a_account.company
                ).select(table.id,
                Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                company.currency,
                where=(table.type != 'view')
                & table.id.in_(all_ids)
                & (table.active == True) & line_query,
                group_by=(table.id, company.currency)))
        account_sum = {}
        id2currency = {}
        for account_id, sum, currency_id in cursor.fetchall():
            account_sum.setdefault(account_id, Decimal('0.0'))
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            if currency_id != id2account[account_id].currency.id:
                currency = None
                if currency_id in id2currency:
                    currency = id2currency[currency_id]
                else:
                    currency = Currency(currency_id)
                    id2currency[currency.id] = currency
                account_sum[account_id] += Currency.compute(currency, sum,
                        id2account[account_id].currency, round=True)
            else:
                account_sum[account_id] += \
                    id2account[account_id].currency.round(sum)

        for account_id in ids:
            res.setdefault(account_id, Decimal('0.0'))
            childs = cls.search([
                    ('parent', 'child_of', [account_id]),
                    ])
            to_currency = id2account[account_id].currency
            for child in childs:
                from_currency = id2account[child.id].currency
                res[account_id] += Currency.compute(from_currency,
                        account_sum.get(child.id, Decimal('0.0')), to_currency,
                        round=True)
            res[account_id] = to_currency.round(res[account_id])
            if id2account[account_id].display_balance == 'credit-debit':
                res[account_id] = - res[account_id]
        return res

    @classmethod
    def get_credit_debit(cls, accounts, names):
        pool = Pool()
        Line = pool.get('analytic_account.line')
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        line = Line.__table__()
        move_line = MoveLine.__table__()
        a_account = Account.__table__()
        company = Company.__table__()

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
        columns = [table.id, company.currency]
        for name in names:
            columns.append(Sum(Coalesce(Column(line, name), 0)))
        cursor.execute(*table.join(line, 'LEFT',
                condition=table.id == line.account
                ).join(move_line, 'LEFT',
                condition=move_line.id == line.move_line
                ).join(a_account, 'LEFT',
                condition=a_account.id == move_line.account
                ).join(company, 'LEFT',
                condition=company.id == a_account.company
                ).select(*columns,
                where=(table.type != 'view')
                & table.id.in_(ids)
                & (table.active == True) & line_query,
                group_by=(table.id, company.currency)))

        id2currency = {}
        for row in cursor.fetchall():
            account = id2account[row[0]]
            currency_id = row[1]
            for i, name in enumerate(names, 2):
                # SQLite uses float for SUM
                sum = row[i]
                if not isinstance(sum, Decimal):
                    sum = Decimal(str(sum))
                if currency_id != account.currency.id:
                    currency = None
                    if currency_id in id2currency:
                        currency = id2currency[currency_id]
                    else:
                        currency = Currency(currency_id)
                        id2currency[currency.id] = currency
                    result[name][account.id] += Currency.compute(currency, sum,
                            account.currency, round=True)
                else:
                    result[name][account.id] += account.currency.round(sum)
        return result

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + unicode(self.name)
        else:
            return unicode(self.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        accounts = cls.search([('code',) + tuple(clause[1:])], limit=1)
        if accounts:
            return [('code',) + tuple(clause[1:])]
        else:
            return [(cls._rec_name,) + tuple(clause[1:])]


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


class AnalyticAccountEntry(ModelView, ModelSQL):
    'Analytic Account Entry'
    __name__ = 'analytic.account.entry'
    origin = fields.Reference('Origin', selection='get_origin', select=True)
    root = fields.Many2One('analytic_account.account', 'Root Analytic',
        domain=[('type', '=', 'root')])
    account = fields.Many2One('analytic_account.account', 'Account',
        ondelete='RESTRICT',
        states={
            'required': Eval('required', False),
            },
        domain=[
            ('root', '=', Eval('root')),
            ('type', '=', 'normal'),
            ],
        depends=['root', 'required'])
    required = fields.Function(fields.Boolean('Required'),
        'on_change_with_required')

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Account = pool.get('analytic_account.account')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        # Migration from 3.4: use origin as the key for One2Many
        migration_3_4 = False
        old_table = 'analytic_account_account_selection_rel'
        if TableHandler.table_exist(old_table):
            TableHandler.table_rename(old_table, cls._table)
            migration_3_4 = True

        # Don't create table before renaming
        table = TableHandler(cls, module_name)

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
                'Only one account is allowed per analytic root and origin.'),
            ]

    @classmethod
    def _get_origin(cls):
        return []

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @fields.depends('root')
    def on_change_with_required(self, name=None):
        if self.root:
            return self.root.mandatory
        return False


class AnalyticMixin(ModelSQL):

    analytic_accounts = fields.One2Many('analytic.account.entry', 'origin',
        'Analytic Accounts',
        size=Eval('analytic_accounts_size', 0),
        depends=['analytic_accounts_size'])
    analytic_accounts_size = fields.Function(fields.Integer(
            'Analytic Accounts Size'), 'get_analytic_accounts_size')

    @classmethod
    def __setup__(cls):
        super(AnalyticMixin, cls).__setup__()
        cls._error_messages.update({
                'root_account': ('Some mandatory root account are missing '
                    'on "%(name)s"'),
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        AccountEntry = pool.get('analytic.account.entry')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        super(AnalyticMixin, cls).__register__(module_name)

        handler = TableHandler(cls, module_name)
        # Migration from 3.4: analytic accounting changed to reference field
        if handler.column_exist('analytic_accounts'):
            entry = AccountEntry.__table__()
            table = cls.__table__()
            cursor.execute(*table.select(table.id, table.analytic_accounts,
                    where=table.analytic_accounts != None))
            for line_id, selection_id in cursor.fetchall():
                cursor.execute(*entry.update(
                        columns=[entry.origin],
                        values=['%s,%s' % (cls.__name__, line_id)],
                        where=entry.selection == selection_id))
            handler.drop_column('analytic_accounts')

    @staticmethod
    def default_analytic_accounts():
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')

        accounts = []
        root_accounts = AnalyticAccount.search([
                ('parent', '=', None),
                ])
        for account in root_accounts:
            accounts.append({
                    'required': account.mandatory,
                    'root': account.id,
                    })
        return accounts

    @staticmethod
    def default_analytic_accounts_size():
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')
        return len(AnalyticAccount.search([('type', '=', 'root')]))

    @classmethod
    def get_analytic_accounts_size(cls, records, name):
        roots = cls.default_analytic_accounts_size()
        return {r.id: roots for r in records}

    @classmethod
    def validate(cls, analytics):
        super(AnalyticMixin, cls).validate(analytics)
        cls.check_roots(analytics)

    @classmethod
    def check_roots(cls, analytics):
        "Check that all mandatory root entries are defined in entries"
        pool = Pool()
        Account = pool.get('analytic_account.account')
        mandatory_roots = {a for a in Account.search([
                ('type', '=', 'root'),
                ('mandatory', '=', True),
                ])}
        for analytic in analytics:
            analytic_roots = {e.root for e in analytic.analytic_accounts}
            if not mandatory_roots <= analytic_roots:
                cls.raise_user_error('root_account', {
                        'name': analytic.rec_name,
                        })

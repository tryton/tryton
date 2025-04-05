# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from sql import Column, Literal
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond import backend
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, ModelSQL, ModelView, Unique, fields, sum_tree,
    tree)
from trytond.model.exceptions import AccessError
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval, If, PYSONDecoder, PYSONEncoder
from trytond.tools import (
    grouped_slice, is_full_text, lstrip_wildcard, sqlite_apply_types)
from trytond.transaction import Transaction

from .exceptions import AccountValidationError


class Account(
        DeactivableMixin, tree('distribution_parents'), tree(),
        ModelSQL, ModelView):
    __name__ = 'analytic_account.account'
    name = fields.Char("Name", required=True, translate=True)
    code = fields.Char("Code")
    company = fields.Many2One('company.company', 'Company', required=True)
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    type = fields.Selection([
        ('root', 'Root'),
        ('view', 'View'),
        ('normal', 'Normal'),
        ('distribution', 'Distribution'),
        ], 'Type', required=True)
    root = fields.Many2One(
        'analytic_account.account', "Root",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('parent', '=', None),
            ('type', '=', 'root'),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            })
    parent = fields.Many2One(
        'analytic_account.account', "Parent",
        domain=['OR',
            ('root', '=', Eval('root', -1)),
            ('parent', '=', None),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            })
    childs = fields.One2Many('analytic_account.account', 'parent', 'Children',
        states={
            'invisible': Eval('id', -1) < 0,
            },
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    balance = fields.Function(Monetary(
            "Balance", currency='currency', digits='currency'),
        'get_balance')
    credit = fields.Function(Monetary(
            "Credit", currency='currency', digits='currency'),
        'get_credit_debit')
    debit = fields.Function(Monetary(
            "Debit", currency='currency', digits='currency'),
        'get_credit_debit')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('opened', 'Opened'),
        ('closed', 'Closed'),
        ], "State", required=True, sort=False)
    note = fields.Text('Note')
    distributions = fields.One2Many(
        'analytic_account.account.distribution', 'parent',
        "Distributions",
        states={
            'invisible': Eval('type') != 'distribution',
            'required': Eval('type') == 'distribution',
            })
    distribution_parents = fields.Many2Many(
        'analytic_account.account.distribution', 'account', 'parent',
        "Distribution Parents", readonly=True)

    @classmethod
    def __setup__(cls):
        cls.code.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(t, (t.code, Index.Similarity())))
        cls._order.insert(0, ('code', 'ASC'))
        cls._order.insert(1, ('name', 'ASC'))

    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_type():
        return 'normal'

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def validate_fields(cls, accounts, field_names):
        super().validate_fields(accounts, field_names)
        cls.check_distribution(accounts, field_names)
        cls.check_move_domain(accounts, field_names)

    @classmethod
    def check_distribution(cls, accounts, field_names=None):
        if field_names and not (field_names & {'distributions', 'type'}):
            return
        for account in accounts:
            if account.type != 'distribution':
                return
            if sum((d.ratio for d in account.distributions)) != 1:
                raise AccountValidationError(
                    gettext('analytic_account.msg_invalid_distribution',
                        account=account.rec_name))

    @classmethod
    def check_move_domain(cls, accounts, field_names):
        pool = Pool()
        Line = pool.get('analytic_account.line')
        if field_names and 'type' not in field_names:
            return
        accounts = [
            a for a in accounts if a.type in {'root', 'view', 'distribution'}]
        for sub_accounts in grouped_slice(accounts):
            sub_accounts = list(sub_accounts)
            lines = Line.search([
                    ('account', 'in', [a.id for a in sub_accounts]),
                    ], order=[], limit=1)
            if lines:
                line, = lines
                raise AccountValidationError(gettext(
                        'analytic_account.msg_account_wrong_type_line',
                        account=line.account.rec_name))

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        return self.company.currency if self.company else None

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
        query = (table.join(line, 'LEFT',
                condition=table.id == line.account
                ).join(move_line, 'LEFT',
                condition=move_line.id == line.move_line
                ).select(table.id,
                Sum(Coalesce(line.credit, 0) - Coalesce(line.debit, 0)
                    ).as_('balance'),
                where=(table.type != 'view')
                & table.id.in_(all_ids)
                & (table.active == Literal(True)) & line_query,
                group_by=table.id))
        if backend.name == 'sqlite':
            sqlite_apply_types(query, [None, 'NUMERIC'])
        cursor.execute(*query)
        values = defaultdict(Decimal)
        values.update(cursor)

        balances = sum_tree(childs, values)
        for account in accounts:
            balances[account.id] = account.currency.round(balances[account.id])
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
            result[name] = {}.fromkeys(ids, Decimal(0))

        id2account = {}
        for account in accounts:
            id2account[account.id] = account

        line_query = Line.query_get(line)
        columns = [table.id]
        types = [None]
        for name in names:
            columns.append(Sum(Coalesce(Column(line, name), 0)).as_(name))
            types.append('NUMERIC')
        query = (table.join(line, 'LEFT',
                condition=table.id == line.account
                ).join(move_line, 'LEFT',
                condition=move_line.id == line.move_line
                ).select(*columns,
                where=(table.type != 'view')
                & table.id.in_(ids)
                & (table.active == Literal(True)) & line_query,
                group_by=table.id))
        if backend.name == 'sqlite':
            sqlite_apply_types(query, types)
        cursor.execute(*query)
        for row in cursor:
            account_id = row[0]
            for i, name in enumerate(names, 1):
                result[name][account_id] += row[i]
        for account in accounts:
            for name in names:
                result[name][account.id] = account.currency.round(
                    result[name][account.id])
        return result

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + str(self.name)
        else:
            return str(self.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        return [bool_op,
            ('code', operator, code_value, *extra),
            (cls._rec_name, operator, operand, *extra),
            ]

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
                    account, current_amount = result[i]
                    rounding = self.currency.rounding.copy_sign(remainder)
                    result[i] = (account, current_amount + rounding)
                    remainder -= rounding
                    i = (i + 1) % len(result)
            assert sum(a for _, a in result) == amount
            return result

    @classmethod
    def check_modification(cls, mode, accounts, values=None, external=False):
        pool = Pool()
        Entry = pool.get('analytic.account.entry')

        super().check_modification(
            mode, accounts, values=values, external=external)

        if mode == 'write' and 'root' in values:
            for sub_records in grouped_slice(accounts):
                entries = Entry.search([
                        ('account', 'in', list(map(int, sub_records))),
                        ],
                    limit=1, order=[])
                if entries:
                    entry, = entries
                    raise AccessError(gettext(
                            'analytic_account'
                            '.msg_analytic_account_root_change',
                            account=entry.account.rec_name))


class AccountContext(ModelView):
    __name__ = 'analytic_account.account.context'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


class AccountDistribution(ModelView, ModelSQL):
    __name__ = 'analytic_account.account.distribution'
    parent = fields.Many2One(
        'analytic_account.account', "Parent", required=True)
    root = fields.Function(
        fields.Many2One('analytic_account.account', "Root"),
        'on_change_with_root')
    account = fields.Many2One(
        'analytic_account.account', "Account", required=True,
        domain=[
            ('root', '=', Eval('root', -1)),
            ('type', 'in', ['normal', 'distribution']),
            ])
    ratio = fields.Numeric("Ratio", required=True,
        domain=[
            ('ratio', '>=', 0),
            ('ratio', '<=', 1),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('ratio', 'DESC'))

    @fields.depends('parent', '_parent_parent.root')
    def on_change_with_root(self, name=None):
        return self.parent.root if self.parent else None


class AnalyticAccountEntry(ModelView, ModelSQL):
    __name__ = 'analytic.account.entry'

    _states = {
        'readonly': ~Eval('editable', True),
        }
    origin = fields.Reference(
        "Origin", selection='get_origin', states=_states)
    root = fields.Many2One(
        'analytic_account.account', "Root Analytic", required=True,
        domain=[
            If(~Eval('company'),
                # No constraint if the origin is not set
                (),
                ('company', '=', Eval('company', -1))),
            ('type', '=', 'root'),
            ],
        states=_states)
    account = fields.Many2One('analytic_account.account', 'Account',
        ondelete='RESTRICT',
        domain=[
            ('root', '=', Eval('root', -1)),
            ('type', 'in', ['normal', 'distribution']),
            ],
        states=_states)
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company', searcher='search_company')
    editable = fields.Function(
        fields.Boolean("Editable"), 'on_change_with_editable')
    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('root_origin_uniq', Unique(t, t.origin, t.root),
                'analytic_account.msg_root_origin_unique'),
            ]
        cls._sql_indexes.add(Index(t, (t.origin, Index.Equality())))

    @classmethod
    def _get_origin(cls):
        return ['analytic_account.rule']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    def on_change_with_company(self, name=None):
        return None

    @classmethod
    def search_company(cls, name, clause):
        return []

    @fields.depends()
    def on_change_with_editable(self, name=None):
        return True

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
        size=Eval('analytic_accounts_size', 0))
    analytic_accounts_size = fields.Function(fields.Integer(
            'Analytic Accounts Size'), 'get_analytic_accounts_size')

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

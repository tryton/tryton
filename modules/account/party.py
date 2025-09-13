# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from sql import Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond import backend
from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.modules.currency.fields import Monetary
from trytond.modules.party.exceptions import EraseError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.tools import grouped_slice, reduce_ids, sqlite_apply_types
from trytond.tools import timezone as tz
from trytond.transaction import Transaction

from .exceptions import AccountMissing

account_names = [
    'account_payable', 'account_receivable',
    'customer_tax_rule', 'supplier_tax_rule']


class Party(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party'
    accounts = fields.One2Many('party.party.account', 'party', "Accounts")
    account_payable = fields.MultiValue(fields.Many2One(
            'account.account', "Account Payable",
            domain=[
                ('closed', '!=', True),
                ('type.payable', '=', True),
                ('party_required', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }))
    account_receivable = fields.MultiValue(fields.Many2One(
            'account.account', "Account Receivable",
            domain=[
                ('closed', '!=', True),
                ('type.receivable', '=', True),
                ('party_required', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }))
    customer_tax_rule = fields.MultiValue(fields.Many2One(
            'account.tax.rule', "Customer Tax Rule",
            domain=[
                ('company', '=', Eval('context', {}).get('company', -1)),
                ('kind', 'in', ['sale', 'both']),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }, help='Apply this rule on taxes when party is customer.'))
    supplier_tax_rule = fields.MultiValue(fields.Many2One(
            'account.tax.rule', "Supplier Tax Rule",
            domain=[
                ('company', '=', Eval('context', {}).get('company', -1)),
                ('kind', 'in', ['purchase', 'both']),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }, help='Apply this rule on taxes when party is supplier.'))
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'get_currency')
    receivable = fields.Function(Monetary(
            "Receivable", currency='currency', digits='currency'),
        'get_receivable_payable', searcher='search_receivable_payable')
    payable = fields.Function(Monetary(
            "Payable", currency='currency', digits='currency'),
        'get_receivable_payable', searcher='search_receivable_payable')
    receivable_today = fields.Function(Monetary(
            "Receivable Today", currency='currency', digits='currency'),
        'get_receivable_payable', searcher='search_receivable_payable')
    payable_today = fields.Function(Monetary(
            "Payable Today", currency='currency', digits='currency'),
        'get_receivable_payable', searcher='search_receivable_payable')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in account_names:
            return pool.get('party.party.account')
        return super().multivalue_model(field)

    @classmethod
    def _default_tax_rule(cls, type_, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        assert type_ in {'customer', 'supplier'}
        tax_rule = config.get_multivalue(
            'default_%s_tax_rule' % type_, **pattern)
        return tax_rule.id if tax_rule else None

    @classmethod
    def default_customer_tax_rule(cls, **pattern):
        return cls._default_tax_rule('customer', **pattern)

    @classmethod
    def default_supplier_tax_rule(cls, **pattern):
        return cls._default_tax_rule('supplier', **pattern)

    def get_currency(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id is not None and company_id >= 0:
            company = Company(company_id)
            return company.currency

    @classmethod
    def _receivable_payable_query(cls, names, company, parties=None):
        pool = Pool()
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')

        transaction = Transaction()
        context = transaction.context
        account = Account.__table__()
        account_type = AccountType.__table__()
        move = Move.__table__()
        move_line = MoveLine.__table__()

        if date := context.get('date'):
            today = date
        elif datetime := context.get('_datetime'):
            if company.timezone:
                timezone = tz.ZoneInfo(company.timezone)
                datetime = datetime.astimezone(timezone)
            today = datetime.date()
        else:
            with transaction.set_context(company=company.id):
                today = Date.today()

        date = Coalesce(move_line.maturity_date, move.date)
        expressions = {
            'receivable': Sum(
                move_line.debit - move_line.credit,
                filter_=account_type.receivable),
            'receivable_today': Sum(
                move_line.debit - move_line.credit,
                filter_=account_type.receivable & (date <= today)),
            'payable': Sum(
                move_line.debit - move_line.credit,
                filter_=account_type.payable),
            'payable_today': Sum(
                move_line.debit - move_line.credit,
                filter_=account_type.payable & (date <= today)),
            }
        columns = []
        for name in names:
            columns.append(Coalesce(expressions[name], Decimal()).as_(name))

        if parties is not None:
            party_where = reduce_ids(move_line.party, [p.id for p in parties])
        else:
            party_where = Literal(True)

        query = (
            move_line
            .join(move, condition=move_line.move == move.id)
            .join(account, condition=move_line.account == account.id)
            .join(account_type, condition=account.type == account_type.id)
            .select(
                move_line.party.as_('party'),
                *columns,
                where=(
                    (move_line.reconciliation == Null)
                    & (account.company == company.id)
                    & party_where),
                group_by=move_line.party))
        return query

    @classmethod
    def get_receivable_payable(cls, parties, names):
        pool = Pool()
        User = pool.get('res.user')

        transaction = Transaction()
        cursor = transaction.connection.cursor()
        amounts = {name: defaultdict(Decimal) for name in names}

        user = User(transaction.user)
        if not user.company:
            return amounts

        company = user.company
        currency = company.currency
        for sub_parties in grouped_slice(parties):
            query = cls._receivable_payable_query(names, company, sub_parties)
            if backend.name == 'sqlite':
                sqlite_apply_types(query, [None] + ['NUMERIC'] * 4)
            cursor.execute(*query)
            for party_id, *values in cursor:
                for name, value in zip(names, values):
                    amounts[name][party_id] = currency.round(value)
        return amounts

    @classmethod
    def search_receivable_payable(cls, name, clause):
        pool = Pool()
        User = pool.get('res.user')
        MoveLine = pool.get('account.move.line')

        transaction = Transaction()
        user = User(transaction.user)
        if not user.company:
            return [('id', '=', -1)]

        company = user.company
        query = cls._receivable_payable_query([name], company)
        columns = list(query.columns)
        amount = columns.pop(1).expression
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        if backend.name == 'sqlite':
            cast_ = MoveLine.debit.sql_cast
            if operator in {'in', 'not in'}:
                value = [cast_(Literal(Decimal(v or 0))) for v in value]
            else:
                value = cast_(Literal(Decimal(value or 0)))
            amount = cast_(amount)

        query.having = Operator(amount, value)
        query.columns = columns
        return [('id', 'in', query)]

    @property
    def account_payable_used(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        account = self.account_payable
        if not account:
            with Transaction().set_context(self._context):
                config = Configuration(1)
                account = config.get_multivalue('default_account_payable')
        # Allow empty values on on_change
        if not account and not Transaction().readonly:
            raise AccountMissing(
                gettext('account.msg_party_missing_payable_account',
                    party=self.rec_name))
        if account:
            return account.current()

    @property
    def account_receivable_used(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        account = self.account_receivable
        if not account:
            with Transaction().set_context(self._context):
                config = Configuration(1)
                account = config.get_multivalue('default_account_receivable')
        # Allow empty values on on_change
        if not account and not Transaction().readonly:
            raise AccountMissing(
                gettext('account.msg_party_missing_receivable_account',
                    party=self.rec_name))
        if account:
            return account.current()

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree/field[@name="receivable_today"]',
                'visual', If(Eval('receivable_today', 0) > 0, 'danger', '')),
            ('/tree/field[@name="payable_today"]',
                'visual', If(Eval('payable_today', 0) < 0, 'warning', '')),
            ]

    @classmethod
    def copy(cls, parties, default=None):
        default = default.copy() if default else {}
        if Transaction().check_access:
            fields = [
                'accounts',
                'account_payable', 'account_receivable',
                'customer_tax_rule', 'supplier_tax_rule']
            default_values = cls.default_get(fields, with_rec_name=False)
            for fname in fields:
                default.setdefault(fname, default_values.get(fname))
        return super().copy(parties, default=default)


class PartyAccount(ModelSQL, CompanyValueMixin):
    __name__ = 'party.party.account'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    account_payable = fields.Many2One(
        'account.account', "Account Payable",
        domain=[
            ('type.payable', '=', True),
            ('party_required', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        ondelete='RESTRICT')
    account_receivable = fields.Many2One(
        'account.account', "Account Receivable",
        domain=[
            ('type.receivable', '=', True),
            ('party_required', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        ondelete='RESTRICT')
    customer_tax_rule = fields.Many2One(
        'account.tax.rule', "Customer Tax Rule",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', 'in', ['sale', 'both']),
            ],
        ondelete='RESTRICT')
    supplier_tax_rule = fields.Many2One(
        'account.tax.rule', "Supplier Tax Rule",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', 'in', ['purchase', 'both']),
            ],
        ondelete='RESTRICT')


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.move.line', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        super().check_erase_company(party, company)
        if party.receivable or party.payable:
            raise EraseError(
                gettext('account.msg_erase_party_receivable_payable',
                    party=party.rec_name,
                    company=company.rec_name))

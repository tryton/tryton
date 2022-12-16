# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond import backend
from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import reduce_ids, grouped_slice
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.modules.party.exceptions import EraseError

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
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    receivable = fields.Function(fields.Numeric('Receivable',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_receivable_payable', searcher='search_receivable_payable')
    payable = fields.Function(fields.Numeric('Payable',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_receivable_payable', searcher='search_receivable_payable')
    receivable_today = fields.Function(fields.Numeric('Receivable Today',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_receivable_payable', searcher='search_receivable_payable')
    payable_today = fields.Function(fields.Numeric('Payable Today',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_receivable_payable', searcher='search_receivable_payable')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in account_names:
            return pool.get('party.party.account')
        return super(Party, cls).multivalue_model(field)

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

    @classmethod
    def get_currency_digits(cls, parties, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            digits = company.currency.digits
        else:
            digits = 2
        return {p.id: digits for p in parties}

    @classmethod
    def get_receivable_payable(cls, parties, names):
        '''
        Function to compute receivable, payable (today or not) for party ids.
        '''
        result = {}
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        cursor = Transaction().connection.cursor()

        line = MoveLine.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()

        for name in names:
            if name not in ('receivable', 'payable',
                    'receivable_today', 'payable_today'):
                raise Exception('Bad argument')
            result[name] = dict((p.id, Decimal('0.0')) for p in parties)

        user = User(Transaction().user)
        if not user.company:
            return result
        company_id = user.company.id
        exp = Decimal(str(10.0 ** -user.company.currency.digits))

        amount = Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0))
        for name in names:
            code = name
            today_where = Literal(True)
            if name in ('receivable_today', 'payable_today'):
                code = name[:-6]
                today_where = ((line.maturity_date <= Date.today())
                    | (line.maturity_date == Null))
            for sub_parties in grouped_slice(parties):
                sub_ids = [p.id for p in sub_parties]
                party_where = reduce_ids(line.party, sub_ids)
                cursor.execute(*line.join(account,
                        condition=account.id == line.account
                        ).join(account_type,
                        condition=account.type == account_type.id
                        ).select(line.party, amount,
                        where=(getattr(account_type, code)
                            & (line.reconciliation == Null)
                            & (account.company == company_id)
                            & party_where
                            & today_where),
                        group_by=line.party))
                for party, value in cursor.fetchall():
                    # SQLite uses float for SUM
                    if not isinstance(value, Decimal):
                        value = Decimal(str(value))
                    result[name][party] = value.quantize(exp)
        return result

    @classmethod
    def search_receivable_payable(cls, name, clause):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        User = pool.get('res.user')
        Date = pool.get('ir.date')

        line = MoveLine.__table__()
        account = Account.__table__()
        account_type = AccountType.__table__()

        if name not in ('receivable', 'payable',
                'receivable_today', 'payable_today'):
            raise Exception('Bad argument')
        _, operator, value = clause

        user = User(Transaction().user)
        if not user.company:
            return []
        company_id = user.company.id

        code = name
        today_query = Literal(True)
        if name in ('receivable_today', 'payable_today'):
            code = name[:-6]
            today_query = ((line.maturity_date <= Date.today())
                | (line.maturity_date == Null))

        Operator = fields.SQL_OPERATORS[operator]

        # Need to cast numeric for sqlite
        cast_ = MoveLine.debit.sql_cast
        amount = cast_(Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)))
        if operator in {'in', 'not in'}:
            value = [cast_(Literal(Decimal(v or 0))) for v in value]
        else:
            value = cast_(Literal(Decimal(value or 0)))
        query = (line.join(account, condition=account.id == line.account
                ).join(account_type, condition=account.type == account_type.id
                ).select(line.party,
                where=(getattr(account_type, code)
                    & (line.party != Null)
                    & (line.reconciliation == Null)
                    & (account.company == company_id)
                    & today_query),
                group_by=line.party,
                having=Operator(amount, value)))
        return [('id', 'in', query)]

    @property
    def account_payable_used(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        account = self.account_payable
        if not account:
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
        return [
            ('/tree/field[@name="receivable_today"]',
                'visual', If(Eval('receivable_today', 0) > 0, 'danger', '')),
            ('/tree/field[@name="payable_today"]',
                'visual', If(Eval('payable_today', 0) < 0, 'warning', '')),
            ]


class PartyAccount(ModelSQL, CompanyValueMixin):
    "Party Account"
    __name__ = 'party.party.account'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    account_payable = fields.Many2One(
        'account.account', "Account Payable",
        domain=[
            ('type.payable', '=', True),
            ('party_required', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account_receivable = fields.Many2One(
        'account.account', "Account Receivable",
        domain=[
            ('type.receivable', '=', True),
            ('party_required', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    customer_tax_rule = fields.Many2One(
        'account.tax.rule', "Customer Tax Rule",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', 'in', ['sale', 'both']),
            ],
        depends=['company'])
    supplier_tax_rule = fields.Many2One(
        'account.tax.rule', "Supplier Tax Rule",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', 'in', ['purchase', 'both']),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(PartyAccount, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(account_names)
        value_names.extend(account_names)
        fields.append('company')
        migrate_property(
            'party.party', field_names, cls, value_names,
            parent='party', fields=fields)


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('account.move.line', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        super(PartyErase, self).check_erase_company(party, company)
        if party.receivable or party.payable:
            raise EraseError(
                gettext('account.msg_erase_party_receivable_payable',
                    party=party.rec_name,
                    company=company.rec_name))

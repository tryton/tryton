from collections import defaultdict
from decimal import Decimal
from functools import wraps
from itertools import groupby, zip_longest
from operator import attrgetter

from dateutil.relativedelta import relativedelta
from sql.conditionals import Coalesce

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields, sequence_ordered, tree
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.report import Report
from trytond.transaction import Transaction

from .exceptions import InvoiceConsolidationCompanyError


def with_currency_date(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        transaction = Transaction()
        context = transaction.context
        with transaction.set_context(
                date=context.get('date', context.get('to_date', today))):
            return func(*args, **kwargs)
    return wrapper


class Type(metaclass=PoolMeta):
    __name__ = 'account.account.type'
    consolidation = fields.Many2One(
        'account.consolidation', "Consolidation",
        domain=[
            ('statement', '=', Eval('statement')),
            If(Eval('statement') == 'balance',
                ('assets', '=', Eval('assets', False)),
                ()),
            ])


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    consolidation_company = fields.Many2One(
        'company.company', "Consolidation Company",
        domain=[
            ('id', '!=', Eval('company', -1)),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._check_modify_exclude.append('consolidation_company')


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    consolidation_company = fields.Function(fields.Many2One(
            'company.company', "Consolidation Company"),
        'get_move_field',
        setter='set_move_field',
        searcher='search_move_field')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._check_modify_exclude.add('consolidation_company')

    @classmethod
    def query_get(cls, table):
        pool = Pool()
        Move = pool.get('account.move')
        move = Move.__table__()
        context = Transaction().context
        query, fiscalyear_id = super().query_get(table)
        if context.get('consolidated') and context.get('companies'):
            query &= table.move.in_(move.select(move.id, where=~Coalesce(
                move.consolidation_company, -1).in_(context['companies'])))
        return query, fiscalyear_id


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    consolidation_company = fields.Many2One(
        'company.company', "Consolidation Company",
        domain=[
            ('party', '=', Eval('party')),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })

    @fields.depends('party', 'consolidation_company')
    def on_change_party(self):
        pool = Pool()
        Company = pool.get('company.company')
        super().on_change_party()
        if self.party:
            companies = Company.search([
                    ('party', '=', self.party.id),
                    ])
            if len(companies) == 1:
                self.consolidation_company, = companies

    @classmethod
    def set_number(cls, invoices):
        pool = Pool()
        Company = pool.get('company.company')

        super().set_number(invoices)

        companies = Company.search([], order=[('party', None)])
        party2company = {
            party: list(companies)
            for party, companies in groupby(companies, attrgetter('party'))}
        for invoice in invoices:
            if not invoice.consolidation_company:
                companies = party2company.get(invoice.party, [])
                if len(companies) == 1:
                    invoice.consolidation_company, = companies
                elif companies:
                    raise InvoiceConsolidationCompanyError(
                        gettext('account_consolidation.'
                            'msg_invoice_consolidation_company_ambiguous',
                            invoice=invoice.rec_name,
                            party=invoice.party.rec_name))
        cls.save(invoices)

    def get_move(self):
        previous_move = self.move
        move = super().get_move()
        if move != previous_move:
            move.consolidation_company = self.consolidation_company
        return move


class Consolidation(
        sequence_ordered(), tree(separator='\\'), ModelSQL, ModelView):
    "Account Consolidation"
    __name__ = 'account.consolidation'

    parent = fields.Many2One(
        'account.consolidation', "Parent", ondelete="RESTRICT",
        domain=['OR',
            If(Eval('statement') == 'off-balance',
                ('statement', '=', 'off-balance'),
                If(Eval('statement') == 'balance',
                    ('statement', '=', 'balance'),
                    ('statement', '!=', 'off-balance')),
                ),
            ('statement', '=', None),
            ])
    name = fields.Char("Name", required=True)
    statement = fields.Selection([
            (None, ""),
            ('balance', "Balance"),
            ('income', "Income"),
            ('off-balance', "Off-Balance"),
            ], "Statement",
        states={
            'required': Bool(Eval('parent')),
            })
    assets = fields.Boolean(
        "Assets",
        states={
            'invisible': Eval('statement') != 'balance',
            })
    types = fields.One2Many(
        'account.account.type', 'consolidation', "Types",
        domain=[
            ('statement', '=', Eval('statement')),
            If(Eval('statement') == 'balance',
                ('assets', '=', Eval('assets', False)),
                ()),
            ],
        add_remove=[
            ('consolidation', '=', None),
            ])
    children = fields.One2Many('account.consolidation', 'parent', "Children")
    amount = fields.Function(Monetary(
            "Amount", currency='currency', digits='currency'),
        'get_amount')
    currency = fields.Function(fields.Many2One(
        'currency.currency', 'Currency'), 'get_currency')
    amount_cmp = fields.Function(Monetary(
            "Amount", currency='currency', digits='currency'),
        'get_amount_cmp')

    @classmethod
    def default_assets(cls):
        return False

    @fields.depends('parent', '_parent_parent.statement')
    def on_change_parent(self):
        if self.parent:
            self.statement = self.parent.statement

    def get_currency(self, name):
        return Transaction().context.get('currency')

    @classmethod
    @with_currency_date
    def get_amount(cls, consolidations, name):
        pool = Pool()
        AccountType = pool.get('account.account.type')
        Currency = pool.get('currency.currency')
        User = pool.get('res.user')
        transaction = Transaction()
        context = transaction.context
        user = User(transaction.user)

        result = defaultdict(Decimal)
        children = cls.search([
                ('parent', 'child_of', [c.id for c in consolidations]),
                ])

        types = sum((c.types for c in children), ())
        key = attrgetter('company')
        companies = set(context.get('companies', [])).intersection(
                map(int, user.companies))
        id2types = {}
        for company, types in groupby(sorted(types, key=key), key):
            if company.id not in companies:
                company = None
            else:
                company = company.id
            with transaction.set_context(company=company, consolidated=True):
                types = AccountType.browse(types)
                id2types.update((t.id, t) for t in types)

        consolidation_sum = defaultdict(Decimal)
        for consolidation in children:
            currency = consolidation.currency
            if not currency:
                continue
            for type_ in consolidation.types:
                type_ = id2types[type_.id]
                if type_.company.id not in companies:
                    continue
                value = type_.amount
                if type_.statement == 'balance' and type_.assets:
                    value *= -1
                if type_.company.currency != currency:
                    value = Currency.compute(
                        type_.company.currency, value, currency, round=False)
                consolidation_sum[consolidation.id] += value
        for consolidation in consolidations:
            children = cls.search([
                    ('parent', 'child_of', [consolidation.id]),
                    ])
            for child in children:
                result[consolidation.id] += consolidation_sum[child.id]
            if consolidation.currency:
                result[consolidation.id] = consolidation.currency.round(
                    result[consolidation.id])
            if consolidation.statement == 'balance' and consolidation.assets:
                result[consolidation.id] *= -1
        return result

    @classmethod
    def get_amount_cmp(cls, consolidations, name):
        transaction = Transaction()
        current = transaction.context
        if not current.get('comparison'):
            return dict.fromkeys([c.id for c in consolidations], None)
        new = {}
        for key, value in current.items():
            if key.endswith('_cmp'):
                new[key[:-4]] = value
        with transaction.set_context(new):
            return cls.get_amount(consolidations, name)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree/field[@name="amount_cmp"]', 'tree_invisible',
                ~Eval('comparison', False)),
            ]

    @classmethod
    def copy(cls, consolidations, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('types', None)
        return super().copy(consolidations, default=default)


class ConsolidationBalanceSheetContext(ModelView):
    "Consolidation Balance Sheet Context"
    __name__ = 'account.consolidation.balance_sheet.context'
    date = fields.Date("Date", required=True)
    posted = fields.Boolean("Posted Move", help="Only include posted moves.")
    companies = fields.Many2Many('company.company', None, None, "Companies")
    currency = fields.Many2One('currency.currency', "Currency", required=True)

    comparison = fields.Boolean("Comparison")
    date_cmp = fields.Date(
        "Date",
        states={
            'required': Eval('comparison', False),
            'invisible': ~Eval('comparison', False),
            })

    @classmethod
    def default_date(cls):
        Date = Pool().get('ir.date')
        return Transaction().context.get('date', Date.today())

    @classmethod
    def default_posted(cls):
        return Transaction().context.get('posted', False)

    @classmethod
    def default_currency(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            return Company(company_id).currency.id

    @classmethod
    def default_companies(cls):
        context = Transaction().context
        return context.get(
            'companies',
            [context['company']] if context.get('company') else None)

    @classmethod
    def default_comparison(cls):
        return False

    @fields.depends('comparison', 'date', 'date_cmp')
    def on_change_comparison(self):
        self.date_cmp = None
        if self.comparison and self.date:
            self.date_cmp = self.date - relativedelta(years=1)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/form/separator[@id="comparison"]', 'states', {
                    'invisible': ~Eval('comparison', False),
                    }),
            ]


class ConsolidationIncomeStatementContext(ModelView):
    "Consolidation Income Statement Context"
    __name__ = 'account.consolidation.income_statement.context'
    from_date = fields.Date(
        "From Date",
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ])
    to_date = fields.Date(
        "To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ])
    companies = fields.Many2Many('company.company', None, None, "Companies")
    currency = fields.Many2One('currency.currency', "Currency", required=True)
    posted = fields.Boolean('Posted Move', help="Only include posted moves.")
    comparison = fields.Boolean('Comparison')
    from_date_cmp = fields.Date(
        "From Date",
        domain=[
            If(Eval('to_date_cmp') & Eval('from_date_cmp'),
                ('from_date_cmp', '<=', Eval('to_date_cmp')),
                ()),
            ],
        states={
            'invisible': ~Eval('comparison', False),
            })
    to_date_cmp = fields.Date(
        "To Date",
        domain=[
            If(Eval('from_date_cmp') & Eval('to_date_cmp'),
                ('to_date_cmp', '>=', Eval('from_date_cmp')),
                ()),
            ],
        states={
            'invisible': ~Eval('comparison', False),
            })

    @classmethod
    def default_posted(cls):
        return False

    @classmethod
    def default_comparison(cls):
        return False

    @classmethod
    def default_currency(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            return Company(company_id).currency.id

    @classmethod
    def default_companies(cls):
        context = Transaction().context
        return context.get(
            'companies',
            [context['company']] if context.get('company') else None)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/form/separator[@id="comparison"]', 'states', {
                    'invisible': ~Eval('comparison', False),
                    }),
            ]


class ConsolidationStatement(Report):
    __name__ = 'account.consolidation.statement'

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Company = pool.get('company.company')
        User = pool.get('res.user')
        transaction = Transaction()
        context = transaction.context
        user = User(transaction.user)

        report_context = super().get_context(records, header, data)

        companies = set(context.get('companies', [])).intersection(
                map(int, user.companies))
        report_context['companies'] = Company.browse(companies)

        if data.get('model_context') is not None:
            Context = pool.get(data['model_context'])
            values = {}
            for field in Context._fields:
                if field in context:
                    values[field] = context[field]
            report_context['ctx'] = Context(**values)

        report_context['consolidations'] = zip_longest(
            records, data.get('paths') or [], fillvalue=[])
        return report_context

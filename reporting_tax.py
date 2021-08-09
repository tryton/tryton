# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import csv
import unicodedata
from io import StringIO

from collections import defaultdict
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from operator import attrgetter

from sql import Cast, Null, Literal
from sql.aggregate import Count, Min, Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Substring, Position, Extract, CurrentTimestamp
from sql.operators import Exists

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.model.modelsql import convert_from
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, StateReport, \
    Button
from trytond.modules.account_eu.account import ECSalesList, ECSalesListContext

from .exceptions import PrintError

# XXX fix: https://genshi.edgewall.org/ticket/582
from genshi.template.astutil import ASTCodeGenerator, ASTTransformer
if not hasattr(ASTCodeGenerator, 'visit_NameConstant'):
    def visit_NameConstant(self, node):
        if node.value is None:
            self._write('None')
        elif node.value is True:
            self._write('True')
        elif node.value is False:
            self._write('False')
        else:
            raise Exception("Unknown NameConstant %r" % (node.value,))
    ASTCodeGenerator.visit_NameConstant = visit_NameConstant
if not hasattr(ASTTransformer, 'visit_NameConstant'):
    # Re-use visit_Name because _clone is deleted
    ASTTransformer.visit_NameConstant = ASTTransformer.visit_Name


def justify(string, size):
    return string[:size].ljust(size)


def format_decimal(n, include_sign=False):
    if not isinstance(n, Decimal):
        n = Decimal(n)
    sign = ''
    if include_sign:
        sign = 'N' if n < 0 else ''
    return sign + ('{0:.2f}'.format(abs(n))).replace('.', '').rjust(
        17 - len(sign), '0')


def format_integer(n, size=8):
    return ('%d' % n).rjust(size, '0')


def format_percentage(n, size=5):
    return ('{0:.2f}'.format(n)).replace('.', '').rjust(size, '0')


def identifier_code(identifier):
    if identifier:
        return identifier.es_code()
    return ''


def country_code(record):
    code = None
    if record.party_tax_identifier:
        code = record.party_tax_identifier.es_country()
    if code is None or code == 'ES':
        return ''
    return code


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn')


class AEATReport(Report):

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)

        periods = sorted(records, key=attrgetter('start_date'))

        context['year'] = str(periods[0].start_date.year)
        context['company'] = periods[0].fiscalyear.company

        start_month = periods[0].start_date.month
        end_month = periods[-1].end_date.month
        if end_month - start_month > 0:
            context['period'] = str(end_month // 3) + 'T'
        else:
            context['period'] = str(start_month).rjust(2, '0')

        context['justify'] = justify
        context['format_decimal'] = format_decimal
        context['format_integer'] = format_integer
        context['format_percentage'] = format_percentage

        with Transaction().set_context(periods=data['ids']):
            context['amounts'] = cls.compute_amounts()

        return context

    @classmethod
    def compute_amounts(cls):
        amounts = defaultdict(Decimal)
        for tax_code in cls.tax_codes():
            amounts[tax_code.code] += tax_code.amount
        return amounts

    @classmethod
    def tax_codes(cls):
        pool = Pool()
        TaxCode = pool.get('account.tax.code')
        return TaxCode.search([('aeat_report', '=', cls._aeat_report)])


class AEATPartyReport(AEATReport):

    @classmethod
    def aeat_party_expression(cls, tables):
        '''
        Returns a couple of sql expression and tables used by sql query to
        compute the aeat party.
        '''
        pool = Pool()
        Invoice = pool.get('account.invoice')

        table, _ = tables[None]
        is_invoice = table.origin.like(Invoice.__name__ + ',%')

        if 'invoice' in tables:
            invoice, _ = tables['invoice']
        else:
            invoice = Invoice.__table__()
            tables['invoice'] = {
                None: (invoice, (is_invoice
                        & (invoice.id == Cast(
                                Substring(table.origin,
                                    Position(',', table.origin) + Literal(1)),
                                Invoice.id.sql_type().base)))),
                }

        return Case((is_invoice, invoice.party), else_=Null), tables

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')
        Tax = pool.get('account.tax')

        context = super().get_context(records, header, data)
        cursor = Transaction().connection.cursor()

        move = Move.__table__()
        move_line = Line.__table__()
        tax_line = TaxLine.__table__()

        tables = {
            None: (move, None),
            'lines': {
                None: (move_line, move_line.move == move.id),
                'tax_lines': {
                    None: (tax_line, tax_line.move_line == move_line.id),
                    },
                },
            }

        expression, tables = cls.aeat_party_expression(tables)

        parties = defaultdict(int)
        for tax_code in cls.tax_codes():
            domain = ['OR']
            for line in tax_code.lines:
                domain.append(line._line_domain)

            with Transaction().set_context(periods=data['ids']):
                tax_line_domain = [Tax._amount_domain(), domain]
            _, where = Move.search_domain([
                    ('lines', 'where', [
                            ('tax_lines', 'where', tax_line_domain),
                            ]),
                    ], tables=tables)

            from_ = convert_from(None, tables)
            cursor.execute(*from_.select(
                    expression, where=where, group_by=(expression,)).select(
                        Count(Literal('*'))))
            row = cursor.fetchone()
            if row:
                parties[tax_code.code] += row[0]
        context['parties'] = parties
        return context


class AEAT111(AEATPartyReport):
    __name__ = 'account.reporting.aeat111'
    _aeat_report = '111'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        amounts = context['amounts']
        for code in ['28', '30']:
            assert code not in amounts, (
                "computed code %s already defined" % code)
        amounts['28'] = (amounts['03'] + amounts['06'] + amounts['09']
            + amounts['12'] + amounts['15'] + amounts['18'] + amounts['21']
            + amounts['24'] + amounts['27'])
        amounts['30'] = amounts['28'] - amounts['29']
        return context


class AEAT115(AEATPartyReport):
    __name__ = 'account.reporting.aeat115'
    _aeat_report = '115'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        amounts = context['amounts']
        assert '05' not in amounts, (
            "computed code 05 already defined")
        amounts['05'] = amounts['03'] - amounts['04']
        return context


class AEAT303(AEATReport):
    __name__ = 'account.reporting.aeat303'
    _aeat_report = '303'

    @classmethod
    def compute_amounts(cls):
        amounts = super().compute_amounts()
        amounts['65'] = 100.0
        return amounts

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Account = pool.get('account.account')
        TaxCodeLine = pool.get('account.tax.code.line')
        transaction = Transaction()
        context = super().get_context(records, header, data)
        amounts = context['amounts']

        periods = records
        start_date = periods[0].start_date
        end_date = periods[-1].end_date

        lines = TaxCodeLine.search([
                ('code', 'in', cls.tax_codes()),
                ('code.code', 'in', ['03', '06', '09', '18', '21', '24']),
                ('tax', 'where', [
                        ('type', '=', 'percentage'),
                        ['OR',
                            ('start_date', '=', None),
                            ('start_date', '<=', end_date),
                            ],
                        ['OR',
                            ('end_date', '=', None),
                            ('end_date', '>=', start_date),
                            ],
                        ]),
                ])
        for line in lines:
            code = str(int(line.code.code) - 1).rjust(2, '0')
            amounts[code] = float(line.tax.rate * Decimal(100))

        amount_to_compensate = Decimal(0)
        fiscalyear = periods[0].fiscalyear
        with transaction.set_context({
                    'fiscalyear': fiscalyear.id,
                    'to_date': end_date,
                    }):
            for account in Account.search([
                        ('company', '=', fiscalyear.company.id),
                        ('code', 'like', '4700%'),
                        ]):
                amount_to_compensate += account.balance

        for code in ['46', '64', '66', '67', '69', '71', '88']:
            assert code not in amounts, (
                "computed code %s already defined" % code)
        amounts['46'] = amounts['27'] - amounts['45']
        amounts['64'] = amounts['46'] + amounts['58'] + amounts['76']
        amounts['66'] = amounts['64'] * Decimal(amounts['65']) / Decimal(100.0)
        amounts['110'] = amounts['78'] = amount_to_compensate
        amounts['87'] = amounts['110'] - amounts['78']
        amounts['69'] = (amounts['66'] + amounts['77'] - amounts['78']
            + amounts['68'])
        amounts['71'] = (amounts['69'] - amounts['70'])
        amounts['88'] = (amounts['80'] + amounts['81'] - amounts['93']
            + amounts['94'] + amounts['83'] + amounts['84'] + amounts['85']
            + amounts['86'] + amounts['95'] + amounts['96'] + amounts['97']
            + amounts['98'] - amounts['79'] - amounts['99'])

        last_period = [p for p in periods[0].fiscalyear.periods
            if p.type == 'standard'][-1]
        declaration_type = 'N'
        if amounts['69'] > 0:
            declaration_type = 'I'
        elif amounts['69'] < 0:
            declaration_type = 'D' if last_period in periods else 'C'
        context['declaration_type'] = declaration_type
        return context


class PrintAEATStart(ModelView):
    'Print AEAT Start'
    __name__ = 'account.reporting.aeat.start'

    report = fields.Selection([
            ('111', "Model 111"),
            ('115', "Model 115"),
            ('303', "Model 303"),
            ], "Report", required=True)
    periods = fields.Many2Many('account.period', None, None, 'Periods',
        required=True)


class PrintAEAT(Wizard):
    'Print AEAT'
    __name__ = 'account.reporting.aeat'
    start = StateView('account.reporting.aeat.start',
        'account_es.print_aeat_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'choice', 'tryton-ok', default=True),
            ])
    choice = StateTransition()
    model_111 = StateReport('account.reporting.aeat111')
    model_115 = StateReport('account.reporting.aeat115')
    model_303 = StateReport('account.reporting.aeat303')

    def transition_choice(self):
        validate = getattr(self, 'validate_%s' % self.start.report, None)
        if validate:
            validate()
        return 'model_%s' % self.start.report

    def open_report(self, action):
        return action, {'ids': [p.id for p in self.start.periods]}

    do_model_111 = open_report
    do_model_115 = open_report
    do_model_303 = open_report

    def validate_303(self):
        if len(set(p.fiscalyear for p in self.start.periods)) > 1:
            raise PrintError(
                gettext('account_es.msg_report_same_fiscalyear'))


class ESVATList(ModelSQL, ModelView):
    "Spanish VAT List"
    __name__ = 'account.reporting.vat_list_es'

    company_tax_identifier = fields.Many2One(
        'party.identifier', "Company Tax Identifier")
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier")
    party = fields.Many2One('party.party', "Party")
    province_code = fields.Function(fields.Char("Province Code"),
        'get_province_code', searcher='search_province_code')
    code = fields.Char("Code")
    amount = fields.Numeric(
        "Amount", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    first_period_amount = fields.Numeric(
        "First Period Amount", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    second_period_amount = fields.Numeric(
        "Second Period Amount", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    third_period_amount = fields.Numeric(
        "Third Period Amount", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    fourth_period_amount = fields.Numeric(
        "Fourth Period Amount", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', "Currency")
    currency_digits = fields.Function(
        fields.Integer("Currency Digits"), 'get_currency_digits')

    def get_currency_digits(self, name):
        return self.currency.digits

    @classmethod
    def get_province_code(cls, records, name):
        return {r.id: r.party.es_province_code or '' if r.party else ''
            for r in records}

    @classmethod
    def search_province_code(cls, name, clause):
        return [(('party.es_province_code',) + tuple(clause[1:]))]

    @classmethod
    def excluded_tax_codes(cls):
        return ['111', '115']

    @classmethod
    def table_query(cls):
        pool = Pool()
        Company = pool.get('company.company')
        Invoice = pool.get('account.invoice')
        InvoiceTax = pool.get('account.invoice.tax')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')
        Tax = pool.get('account.tax')
        TaxCode = pool.get('account.tax.code')
        TaxCodeLine = pool.get('account.tax.code.line')
        Date = pool.get('ir.date')
        context = Transaction().context
        company = Company.__table__()
        invoice = Invoice.__table__()
        cancel_invoice = Invoice.__table__()
        move = Move.__table__()
        cancel_move = Move.__table__()
        line = Line.__table__()
        tax_line = TaxLine.__table__()
        tax = Tax.__table__()
        tax_code = TaxCode.__table__()
        tax_code_line = TaxCodeLine.__table__()
        exclude_invoice_tax = InvoiceTax.__table__()

        amount = tax_line.amount
        month = Extract('MONTH', invoice.invoice_date)

        excluded_taxes = (tax_code_line
            .join(tax_code,
                condition=(tax_code.id == tax_code_line.code)
                ).select(
                    tax_code_line.tax, distinct=True,
                    where=tax_code.aeat_report.in_(cls.excluded_tax_codes())))

        where = ((invoice.company == context.get('company'))
            & (tax.es_vat_list_code != Null)
            & (Extract('year', invoice.invoice_date)
                == context.get('date', Date.today()).year)
            # Exclude base amount for es_reported_with taxes because it is
            # already included in the base of main tax
            & ((tax.es_reported_with == Null) | (tax_line.type == 'tax'))
            & ~Exists(cancel_invoice
                .join(cancel_move,
                    condition=cancel_invoice.cancel_move == cancel_move.id)
                .select(cancel_invoice.id, distinct=True,
                     where=((cancel_invoice.id == invoice.id)
                         & (~cancel_move.origin.like('account.invoice,%')))))
            # Use exists to exclude the full invoice when it has multiple taxes
            & ~Exists(exclude_invoice_tax.select(
                    exclude_invoice_tax.invoice,
                    where=((exclude_invoice_tax.invoice == invoice.id)
                        & (exclude_invoice_tax.tax.in_(excluded_taxes))))))
        return (tax_line
            .join(tax, condition=tax_line.tax == tax.id)
            .join(line, condition=tax_line.move_line == line.id)
            .join(move, condition=line.move == move.id)
            .join(invoice, condition=invoice.move == move.id)
            .join(company, condition=company.id == invoice.company)
            .select(
                Min(tax_line.id).as_('id'),
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
                cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
                invoice.tax_identifier.as_('company_tax_identifier'),
                invoice.party.as_('party'),
                invoice.party_tax_identifier.as_('party_tax_identifier'),
                tax.es_vat_list_code.as_('code'),
                Sum(amount).as_('amount'),
                Sum(amount, filter_=month <= Literal(3)).as_(
                    'first_period_amount'),
                Sum(amount, filter_=(
                        (month > Literal(3)) & (month <= Literal(6)))).as_(
                    'second_period_amount'),
                Sum(amount, filter_=(
                        (month > Literal(6)) & (month <= Literal(9)))).as_(
                    'third_period_amount'),
                Sum(amount, filter_=(
                        (month > Literal(9)) & (month <= Literal(12)))).as_(
                    'fourth_period_amount'),
                company.currency.as_('currency'),
                where=where,
                group_by=[
                    invoice.tax_identifier,
                    invoice.type,
                    invoice.party,
                    invoice.party_tax_identifier,
                    company.currency,
                    tax.es_vat_list_code,
                    ]))


class ESVATListContext(ModelView):
    "Spanish VAT List Context"
    __name__ = 'account.reporting.vat_list_es.context'

    company = fields.Many2One('company.company', "Company", required=True)
    date = fields.Date("Date", required=True,
        context={'date_format': '%Y'})

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()


class AEAT347(Report):
    __name__ = 'account.reporting.aeat347'

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Company = pool.get('company.company')
        t_context = Transaction().context

        context = super().get_context(records, header, data)

        context['year'] = str(t_context['date'].year)
        context['company'] = Company(t_context['company'])
        context['records_amount'] = sum(
            (r.amount for r in records), Decimal(0))

        context['justify'] = justify

        def format_decimal(n):
            if not isinstance(n, Decimal):
                n = Decimal(n)
            sign = 'N' if n < 0 else ' '
            return sign + ('{0:.2f}'.format(abs(n))).replace('.', '').rjust(
                15, '0')
        context['format_decimal'] = format_decimal
        context['format_integer'] = format_integer
        context['identifier_code'] = identifier_code
        context['country_code'] = country_code
        context['strip_accents'] = strip_accents

        return context


class ECOperationList(ECSalesList):
    "EC Operation List"
    __name__ = 'account.reporting.es_ec_operation_list'

    @classmethod
    def table_query(cls):
        pool = Pool()
        Company = pool.get('company.company')
        Invoice = pool.get('account.invoice')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')
        Period = pool.get('account.period')
        Tax = pool.get('account.tax')
        context = Transaction().context
        company = Company.__table__()
        invoice = Invoice.__table__()
        cancel_invoice = Invoice.__table__()
        move = Move.__table__()
        cancel_move = Move.__table__()
        line = Line.__table__()
        tax_line = TaxLine.__table__()
        period = Period.__table__()
        tax = Tax.__table__()

        sales = super().table_query()

        where = invoice.company == context.get('company')
        if context.get('start_date'):
            where &= (move.date >= context.get('start_date'))
        if context.get('end_date'):
            where &= (move.date <= context.get('end_date'))
        where &= ((tax.es_ec_purchases_list_code != Null)
            & (tax.es_ec_purchases_list_code != ''))
        where &= tax_line.type == 'base'
        where &= invoice.type == 'in'
        where &= ~Exists(cancel_invoice
            .join(cancel_move,
                condition=cancel_invoice.cancel_move == cancel_move.id)
            .select(cancel_invoice.id, distinct=True,
                 where=((cancel_invoice.id == invoice.id)
                     & (~cancel_move.origin.like('account.invoice,%')))))
        purchases = (tax_line
            .join(tax, condition=tax_line.tax == tax.id)
            .join(line, condition=tax_line.move_line == line.id)
            .join(move, condition=line.move == move.id)
            .join(period, condition=move.period == period.id)
            .join(invoice, condition=invoice.move == move.id)
            .join(company, condition=company.id == invoice.company)
            .select(
                Min(tax_line.id).as_('id'),
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
                cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
                invoice.tax_identifier.as_('company_tax_identifier'),
                invoice.party.as_('party'),
                invoice.party_tax_identifier.as_('party_tax_identifier'),
                tax.es_ec_purchases_list_code.as_('code'),
                Sum(tax_line.amount).as_('amount'),
                company.currency.as_('currency'),
                where=where,
                group_by=[
                    invoice.tax_identifier,
                    invoice.party,
                    invoice.party_tax_identifier,
                    tax.es_ec_purchases_list_code,
                    company.currency,
                    ]))
        return sales | purchases


class ECOperationListContext(ECSalesListContext):
    "EC Operation List Context"
    __name__ = 'account.reporting.es_ec_operation_list.context'

    start_date = fields.Date("Start Date",
        domain=[
            If(Eval('end_date'),
                ('start_date', '<=', Eval('end_date')),
                (),
                ),
            ],
        depends=['end_date'])
    end_date = fields.Date("End Date",
        domain=[
            If(Eval('start_date'),
                ('end_date', '>=', Eval('start_date')),
                (),
                ),
            ],
        depends=['start_date'])

    @classmethod
    def default_start_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today() - relativedelta(months=1, day=1)

    @classmethod
    def default_end_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today() - relativedelta(months=1, day=31)


class AEAT349(Report):
    __name__ = 'account.reporting.aeat349'

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Company = pool.get('company.company')
        t_context = Transaction().context

        context = super().get_context(records, header, data)

        context['company'] = Company(t_context['company'])
        context['records_amount'] = sum(
            (r.amount for r in records), Decimal(0))

        start_date = t_context.get('start_date')
        end_date = t_context.get('end_date')
        if start_date or end_date:
            date = start_date or end_date
            context['year'] = str(date.year)
        if start_date and end_date:
            start_month = start_date.month
            end_month = end_date.month
            if end_month - start_month > 0:
                context['period'] = str(end_month // 3) + 'T'
                context['period_number'] = str(20 + (end_month // 3))
            else:
                context['period'] = str(start_month).rjust(2, '0')
                context['period_number'] = str(start_month).rjust(2, '0')

        context['justify'] = justify
        context['format_integer'] = format_integer
        context['format_percentage'] = format_percentage
        context['records_amount'] = sum(
            (r.amount for r in records), Decimal(0))

        context['justify'] = justify
        context['identifier_code'] = identifier_code

        def format_decimal(n, digits=13):
            if not isinstance(n, Decimal):
                n = Decimal(n)
            return ('{0:.2f}'.format(abs(n))).replace('.', '').rjust(
                digits, '0')
        context['format_decimal'] = format_decimal

        return context


class ESVATBookContext(ModelView):
    "Spanish VAT Book Context"
    __name__ = 'account.reporting.vat_book_es.context'

    company = fields.Many2One('company.company', "Company", required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', "Fiscal Year",
        required=True,
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    start_period = fields.Many2One('account.period', "Start Period",
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date')),
            ], depends=['fiscalyear', 'end_period'])
    end_period = fields.Many2One('account.period', "End Period",
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date'))
            ],
        depends=['fiscalyear', 'start_period'])
    es_vat_book_type = fields.Selection([
            # Use same key as tax authority
            ('E', "Issued"),
            ('R', "Received"),
            ('S', "Investment Goods"),
            ],
        "Type", required=True)

    @classmethod
    def default_es_vat_book_type(cls):
        return 'E'

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_fiscalyear(cls):
        pool = Pool()
        Fiscalyear = pool.get('account.fiscalyear')
        return Fiscalyear.find(cls.default_company(), exception=False)


class ESVATBook(ModelSQL, ModelView):
    "Spanish VAT Book"
    __name__ = 'account.reporting.vat_book_es'

    invoice = fields.Many2One('account.invoice', "Invoice")
    invoice_date = fields.Date("Invoice Date")
    party = fields.Many2One('party.party', "Party")
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier")
    tax = fields.Many2One('account.tax', "Tax")
    base_amount = fields.Numeric("Base Amount",
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    tax_amount = fields.Numeric("Tax Amount",
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    surcharge_tax = fields.Many2One('account.tax', "Surcharge Tax")
    surcharge_tax_amount = fields.Numeric("Surcharge Tax Amount",
        digits=(16, Eval('currency_digits', 2)),
        states={
            'invisible': ~(Eval('surcharge_tax', None)),
            },
        depends=['currency_digits', 'surcharge_tax'])
    currency_digits = fields.Function(fields.Integer("Currency Digits"),
        'get_currency_digits')

    @classmethod
    def included_tax_groups(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        tax_groups = []
        vat_book_type = Transaction().context.get('es_vat_book_type')
        if vat_book_type == 'E':
            tax_groups.append(ModelData.get_id(
                    'account_es', 'tax_group_sale'))
            tax_groups.append(ModelData.get_id(
                    'account_es', 'tax_group_sale_service'))
        elif vat_book_type == 'R':
            tax_groups.append(ModelData.get_id(
                    'account_es', 'tax_group_purchase'))
            tax_groups.append(ModelData.get_id(
                    'account_es', 'tax_group_purchase_service'))
        elif vat_book_type == 'S':
            tax_groups.append(ModelData.get_id(
                    'account_es', 'tax_group_purchase_investment'))
        return tax_groups

    @classmethod
    def table_query(cls):
        pool = Pool()
        Company = pool.get('company.company')
        Invoice = pool.get('account.invoice')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')
        Period = pool.get('account.period')
        Tax = pool.get('account.tax')
        context = Transaction().context
        company = Company.__table__()
        invoice = Invoice.__table__()
        cancel_invoice = Invoice.__table__()
        move = Move.__table__()
        cancel_move = Move.__table__()
        line = Line.__table__()
        tax_line = TaxLine.__table__()
        period = Period.__table__()
        tax = Tax.__table__()

        where = ((invoice.company == context.get('company'))
            & (period.fiscalyear == context.get('fiscalyear'))
            & ~tax.es_exclude_from_vat_book)
        where &= ~Exists(cancel_invoice
            .join(cancel_move,
                condition=cancel_invoice.cancel_move == cancel_move.id)
            .select(cancel_invoice.id, distinct=True,
                 where=((cancel_invoice.id == invoice.id)
                     & (~cancel_move.origin.like('account.invoice,%')))))
        groups = cls.included_tax_groups()
        if groups:
            where &= tax.group.in_(groups)
        if context.get('start_period'):
            start_period = Period(context['start_period'])
            where &= (period.start_date >= start_period.start_date)
        if context.get('end_period'):
            end_period = Period(context['end_period'])
            where &= (period.end_date <= end_period.end_date)

        query = (tax_line
            .join(tax, condition=tax_line.tax == tax.id)
            .join(line, condition=tax_line.move_line == line.id)
            .join(move, condition=line.move == move.id)
            .join(period, condition=move.period == period.id)
            .join(invoice, condition=invoice.move == move.id)
            .join(company, condition=company.id == invoice.company)
            .select(
                Min(tax_line.id).as_('id'),
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
                cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
                invoice.id.as_('invoice'),
                invoice.invoice_date.as_('invoice_date'),
                invoice.party.as_('party'),
                invoice.party_tax_identifier.as_('party_tax_identifier'),
                Coalesce(tax.es_reported_with, tax.id).as_('tax'),
                Sum(tax_line.amount,
                    filter_=((tax_line.type == 'base')
                        & (tax.es_reported_with == Null))).as_('base_amount'),
                Coalesce(
                    Sum(tax_line.amount,
                        filter_=((tax_line.type == 'tax')
                            & (tax.es_reported_with == Null))),
                    0).as_('tax_amount'),
                Min(tax.id,
                    filter_=(tax.es_reported_with != Null)).as_(
                    'surcharge_tax'),
                Coalesce(Sum(tax_line.amount,
                        filter_=((tax_line.type == 'tax')
                            & (tax.es_reported_with != Null))), 0).as_(
                    'surcharge_tax_amount'),
                where=where,
                group_by=[
                    invoice.id,
                    invoice.party,
                    invoice.invoice_date,
                    invoice.party_tax_identifier,
                    Coalesce(tax.es_reported_with, tax.id),
                    ]))
        return query

    def get_currency_digits(self, name):
        return self.invoice.company.currency.digits


class VATBookReport(Report):
    __name__ = 'account.reporting.aeat.vat_book'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)

        context['format_decimal'] = cls.format_decimal
        context['get_period'] = cls.get_period
        return context

    @classmethod
    def render(cls, report, report_context):
        return cls.render_csv(report, report_context)

    @classmethod
    def convert(cls, report, data, **kwargs):
        output_format = report.extension or report.template_extension
        if not report.report_content and output_format == 'csv':
            return output_format, data
        return super().convert(report, data, **kwargs)

    @classmethod
    def get_period(cls, date):
        return str((date.month + 2) // 3) + 'T'

    @classmethod
    def format_decimal(cls, n):
        if not isinstance(n, Decimal):
            n = Decimal(n)
        sign = '-' if n < 0 else ''
        return sign + '{0:.2f}'.format(abs(n)).replace('.', ',')

    @classmethod
    def get_format_date(cls):
        pool = Pool()
        Lang = pool.get('ir.lang')
        es = Lang(code='es', date='%d/%m/%Y')
        return lambda value: es.strftime(value, '%d/%m/%Y')

    @classmethod
    def render_csv(cls, report, report_context):
        vat_book = StringIO()
        writer = csv.writer(
            vat_book, delimiter=';', doublequote=False, escapechar='\\',
            quoting=csv.QUOTE_NONE)
        for record in report_context['records']:
            writer.writerow(cls.get_row(record, report_context))
        value = vat_book.getvalue()
        if not isinstance(value, bytes):
            value = value.encode('utf-8')
        return value

    @classmethod
    def get_row(cls, record, report_context):
        context = Transaction().context
        format_date = cls.get_format_date()
        return [
            record.invoice_date.year,
            report_context['get_period'](record.invoice_date),
            context['es_vat_book_type'],
            '',
            record.invoice.es_vat_book_type,
            '',
            '',
            format_date(record.invoice_date),
            '',
            record.invoice.es_vat_book_serie,
            record.invoice.es_vat_book_number,
            (record.party_tax_identifier.es_vat_type()
                if record.party_tax_identifier else ''),
            (record.party_tax_identifier.es_code()
                if record.party_tax_identifier else ''),
            country_code(record),
            record.party.name[:40],
            '',
            cls.format_decimal(record.invoice.total_amount),
            cls.format_decimal(record.base_amount),
            cls.format_decimal(record.tax.rate * 100),
            cls.format_decimal(record.tax_amount),
            (cls.format_decimal(record.surcharge_tax.rate * 100)
                if record.surcharge_tax else ''),
            (cls.format_decimal(record.surcharge_tax_amount)
                if record.surcharge_tax else ''),
            '',
            '',
            '',
            '',
            '',
            '',
            ]

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unicodedata
from collections import defaultdict
from decimal import Decimal
from operator import attrgetter

from sql import Cast, Null, Literal
from sql.aggregate import Count, Max, Min, Sum
from sql.conditionals import Case
from sql.functions import Substring, Position, Extract
from sql.operators import Exists

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.model.modelsql import convert_from
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, StateReport, \
    Button
from trytond.modules.account_eu.account import ECSalesList, ECSalesListContext

from .exceptions import PrintError

__all__ = ['AEAT111', 'AEAT115', 'AEAT303', 'PrintAEATStart', 'PrintAEAT',
    'ESVATList', 'ESVATListContext', 'AEAT347', 'ECOperationList',
    'ECOperationListContext', 'AEAT349']


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
        return identifier.code[2:]
    return ''


def country_code(record):
    code = None
    if record.party_tax_identifier:
        code = record.party_tax_identifier.code[:2]
    if code is None or code == 'ES':
        return ''
    return code


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn')


class AEATReport(Report):

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Period = pool.get('account.period')
        context = super().get_context(records, data)

        periods = sorted(
            Period.browse(data['periods']), key=attrgetter('start_date'))

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

        with Transaction().set_context(periods=data['periods']):
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
    def get_context(cls, records, data):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')
        Tax = pool.get('account.tax')

        context = super().get_context(records, data)
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

            with Transaction().set_context(periods=data['periods']):
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
    def get_context(cls, records, data):
        context = super().get_context(records, data)
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
    def get_context(cls, records, data):
        context = super().get_context(records, data)
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
    def get_context(cls, records, data):
        pool = Pool()
        Period = pool.get('account.period')
        Account = pool.get('account.account')
        TaxCodeLine = pool.get('account.tax.code.line')
        transaction = Transaction()
        context = super().get_context(records, data)
        amounts = context['amounts']

        periods = Period.browse(data['periods'])
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
        amounts['67'] = amount_to_compensate
        amounts['69'] = (amounts['66'] + amounts['77'] - amounts['67']
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
        return action, {'periods': [p.id for p in self.start.periods]}

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
    def table_query(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceTax = pool.get('account.invoice.tax')
        Tax = pool.get('account.tax')
        Date = pool.get('ir.date')
        context = Transaction().context
        invoice = Invoice.__table__()
        cancel_invoice = Invoice.__table__()
        invoice_tax = InvoiceTax.__table__()
        tax = Tax.__table__()

        amount = invoice_tax.base + invoice_tax.amount
        month = Extract('MONTH', invoice.invoice_date)

        where = ((invoice.company == context.get('company'))
            & (invoice.state.in_(['posted', 'paid']))
            & (tax.es_vat_list_code != Null)
            & (Extract('year', invoice.invoice_date)
                == context.get('date', Date.today()).year)
            & ~Exists(cancel_invoice.select(
                    cancel_invoice.cancel_move, distinct=True,
                    where=(cancel_invoice.cancel_move == invoice.move))))
        return (invoice_tax
            .join(invoice,
                condition=invoice_tax.invoice == invoice.id)
            .join(tax, condition=invoice_tax.tax == tax.id)
            .select(
                Max(invoice_tax.id).as_('id'),
                Literal(0).as_('create_uid'),
                Min(invoice_tax.create_date).as_('create_date'),
                Literal(0).as_('write_uid'),
                Max(invoice_tax.write_date).as_('write_date'),
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
                invoice.currency.as_('currency'),
                where=where,
                group_by=[
                    invoice.tax_identifier,
                    invoice.type,
                    invoice.party,
                    invoice.party_tax_identifier,
                    invoice.currency,
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
    def get_context(cls, records, data):
        pool = Pool()
        Company = pool.get('company.company')
        t_context = Transaction().context

        context = super().get_context(records, data)

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
        Invoice = pool.get('account.invoice')
        InvoiceTax = pool.get('account.invoice.tax')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Tax = pool.get('account.tax')
        context = Transaction().context
        invoice = Invoice.__table__()
        invoice_tax = InvoiceTax.__table__()
        move = Move.__table__()
        period = Period.__table__()
        tax = Tax.__table__()

        sales = super().table_query()

        where = ((invoice.company == context.get('company'))
            & (period.fiscalyear == context.get('fiscalyear')))
        if context.get('period'):
            where &= (period.id == context.get('period'))
        where &= ((tax.es_ec_purchases_list_code != Null)
            & (tax.es_ec_purchases_list_code != ''))
        where &= invoice.type == 'in'
        purchases = (invoice_tax
            .join(invoice,
                condition=invoice_tax.invoice == invoice.id)
            .join(tax, condition=invoice_tax.tax == tax.id)
            .join(move, condition=invoice.move == move.id)
            .join(period, condition=move.period == period.id)
            .select(
                Max(invoice_tax.id).as_('id'),
                Literal(0).as_('create_uid'),
                Min(invoice_tax.create_date).as_('create_date'),
                Literal(0).as_('write_uid'),
                Max(invoice_tax.write_date).as_('write_date'),
                invoice.tax_identifier.as_('company_tax_identifier'),
                invoice.party.as_('party'),
                invoice.party_tax_identifier.as_('party_tax_identifier'),
                tax.es_ec_purchases_list_code.as_('code'),
                Sum(invoice_tax.base).as_('amount'),
                invoice.currency.as_('currency'),
                where=where,
                group_by=[
                    invoice.tax_identifier,
                    invoice.party,
                    invoice.party_tax_identifier,
                    tax.es_ec_purchases_list_code,
                    invoice.currency,
                    ]))
        return sales | purchases


class ECOperationListContext(ECSalesListContext):
    "EC Operation List Context"
    __name__ = 'account.reporting.es_ec_operation_list.context'


class AEAT349(Report):
    __name__ = 'account.reporting.aeat349'

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Period = pool.get('account.period')
        Fiscalyear = pool.get('account.fiscalyear')
        t_context = Transaction().context

        context = super().get_context(records, data)

        fiscalyear = Fiscalyear(t_context['fiscalyear'])
        context['year'] = str(fiscalyear.start_date.year)
        context['company'] = fiscalyear.company
        context['records_amount'] = sum(
            (r.amount for r in records), Decimal(0))

        period_id = t_context.get('period')
        if not period_id:
            # Yearly
            context['period'] = '0A'
            context['period_number'] = '99'
        else:
            period = Period(period_id)
            start_month = period.start_date.month
            end_month = period.end_date.month
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

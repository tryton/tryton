# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.aggregate import Min, Sum

from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.account.exceptions import FiscalYearNotFoundError
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction

VATEX_CODES = [
    ('VATEX-EU-79-C',
        "Exempt based on article 79, point c of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132',
        "Exempt based on article 132 of Council Directive 2006/112/EC"),
    ('VATEX-EU-132-1A',
        "Exempt based on article 132, section 1 (a) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1B',
        "Exempt based on article 132, section 1 (b) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1C',
        "Exempt based on article 132, section 1 (c) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1D',
        "Exempt based on article 132, section 1 (d) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1E',
        "Exempt based on article 132, section 1 (e) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1F',
        "Exempt based on article 132, section 1 (f) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1G',
        "Exempt based on article 132, section 1 (g) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1H',
        "Exempt based on article 132, section 1 (h) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1I',
        "Exempt based on article 132, section 1 (i) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1J',
        "Exempt based on article 132, section 1 (j) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1K',
        "Exempt based on article 132, section 1 (k) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1L',
        "Exempt based on article 132, section 1 (l) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1M',
        "Exempt based on article 132, section 1 (m) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1N',
        "Exempt based on article 132, section 1 (n) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1O',
        "Exempt based on article 132, section 1 (o) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1P',
        "Exempt based on article 132, section 1 (p) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-132-1Q',
        "Exempt based on article 132, section 1 (q) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143',
        "Exempt based on article 143 of Council Directive 2006/112/EC"),
    ('VATEX-EU-143-1A',
        "Exempt based on article 143, section 1 (a) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1B',
        "Exempt based on article 143, section 1 (b) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1C',
        "Exempt based on article 143, section 1 (c) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1D',
        "Exempt based on article 143, section 1 (d) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1E',
        "Exempt based on article 143, section 1 (e) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1F',
        "Exempt based on article 143, section 1 (f) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1FA',
        "Exempt based on article 143, section 1 (fa) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1G',
        "Exempt based on article 143, section 1 (g) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1H',
        "Exempt based on article 143, section 1 (h) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1I',
        "Exempt based on article 143, section 1 (i) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1J',
        "Exempt based on article 143, section 1 (j) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1K',
        "Exempt based on article 143, section 1 (k) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-143-1L',
        "Exempt based on article 143, section 1 (l) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-144',
        "Exempt based on article 144 of Council Directive 2006/112/EC"),
    ('VATEX-EU-146-1E',
        "Exempt based on article 146 section 1 (e) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-148',
        "Exempt based on article 148 of Council Directive 2006/112/EC"),
    ('VATEX-EU-148-A',
        "Exempt based on article 148, section (a) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-148-B',
        "Exempt based on article 148, section (b) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-148-C',
        "Exempt based on article 148, section (c) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-148-D',
        "Exempt based on article 148, section (d) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-148-E',
        "Exempt based on article 148, section (e) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-148-F',
        "Exempt based on article 148, section (f) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-148-G',
        "Exempt based on article 148, section (g) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-151',
        "Exempt based on article 151 of Council Directive 2006/112/EC"),
    ('VATEX-EU-151-1A',
        "Exempt based on article 151, section 1 (a) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-151-1AA',
        "Exempt based on article 151, section 1 (aa) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-151-1B',
        "Exempt based on article 151, section 1 (b) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-151-1C',
        "Exempt based on article 151, section 1 (c) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-151-1D',
        "Exempt based on article 151, section 1 (d) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-151-1E',
        "Exempt based on article 151, section 1 (e) of Council Directive "
        "2006/112/EC"),
    ('VATEX-EU-159',
        "Exempt based on article 159 of Council Directive 2006/112/EC"),
    ('VATEX-EU-309',
        "Exempt based on article 309 of Council Directive 2006/112/EC"),
    ('VATEX-EU-AE', "Reverse charge"),
    ('VATEX-EU-D',
        "Intra-Community acquisition from second hand means of transport"),
    ('VATEX-EU-F', "Intra-Community acquisition of second hand goods"),
    ('VATEX-EU-G', "Export outside the EU"),
    ('VATEX-EU-I', "Intra-Community acquisition of works of art"),
    ('VATEX-EU-IC', "Intra-Community supply"),
    ('VATEX-EU-O', "Not subject to VAT"),
    ('VATEX-EU-J',
        "Intra-Community acquisition of collectors items and antiques"),
    ]


class TaxTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    ec_sales_list_code = fields.Char("EC Sales List Code")
    vatex_code = fields.Selection(
        'get_vatex_codes', "Tax Exemption Code")

    def _get_tax_value(self, tax=None):
        value = super()._get_tax_value(tax=tax)
        if not tax or tax.ec_sales_list_code != self.ec_sales_list_code:
            value['ec_sales_list_code'] = self.ec_sales_list_code
        if not tax or tax.vatex_code != self.vatex_code:
            value['vatex_code'] = self.vatex_code
        return value

    @classmethod
    def get_vatex_codes(cls):
        pool = Pool()
        Tax = pool.get('account.tax')
        return Tax.fields_get(['vatex_code'])['vatex_code']['selection']


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    ec_sales_list_code = fields.Char("EC Sales List Code",
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            })
    vatex_code = fields.Selection(
        [(None, "")] + VATEX_CODES, "Tax Exemption Code", sort=False,
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            },
        help="The reason why the amount is exempted from VAT.")


class ECSalesList(ModelSQL, ModelView):
    __name__ = 'account.ec_sales_list'

    company_tax_identifier = fields.Many2One(
        'party.identifier', "Company Tax Identifier")
    party = fields.Many2One('party.party', "Party")
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier")
    code = fields.Char("Code")
    amount = Monetary(
        "Amount", currency='currency', digits='currency')
    currency = fields.Many2One('currency.currency', "Currency")

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
        move = Move.__table__()
        line = Line.__table__()
        tax_line = TaxLine.__table__()
        period = Period.__table__()
        tax = Tax.__table__()
        where = invoice.company == context.get('company')
        if context.get('fiscalyear'):
            where &= (period.fiscalyear == context.get('fiscalyear'))
        if context.get('period'):
            where &= (period.id == context.get('period'))
        if context.get('start_date'):
            where &= (move.date >= context.get('start_date'))
        if context.get('end_date'):
            where &= (move.date <= context.get('end_date'))
        where &= ((tax.ec_sales_list_code != Null)
            & (tax.ec_sales_list_code != ''))
        where &= tax_line.type == 'base'
        where &= invoice.type == 'out'
        return (tax_line
            .join(tax, condition=tax_line.tax == tax.id)
            .join(line, condition=tax_line.move_line == line.id)
            .join(move, condition=line.move == move.id)
            .join(period, condition=move.period == period.id)
            .join(invoice, condition=invoice.move == move.id)
            .join(company, condition=company.id == invoice.company)
            .select(
                Min(tax_line.id).as_('id'),
                invoice.tax_identifier.as_('company_tax_identifier'),
                invoice.party.as_('party'),
                invoice.party_tax_identifier.as_('party_tax_identifier'),
                tax.ec_sales_list_code.as_('code'),
                Sum(tax_line.amount).as_('amount'),
                company.currency.as_('currency'),
                where=where,
                group_by=[
                    invoice.tax_identifier,
                    invoice.party,
                    invoice.party_tax_identifier,
                    tax.ec_sales_list_code,
                    company.currency,
                    ]))


class ECSalesListContext(ModelView):
    __name__ = 'account.ec_sales_list.context'

    company = fields.Many2One('company.company', "Company", required=True)
    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    period = fields.Many2One(
        'account.period', "Period",
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear', -1)),
            ])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_fiscalyear(cls):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        context = Transaction().context
        if 'fiscalyear' not in context:
            try:
                fiscalyear = FiscalYear.find(
                    cls.default_company(), test_state=False)
            except FiscalYearNotFoundError:
                return None
            return fiscalyear.id
        return context['fiscalyear']

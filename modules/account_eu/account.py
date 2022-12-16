# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal, Null
from sql.aggregate import Max, Min, Sum

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction


class TaxTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    ec_sales_list_code = fields.Char("EC Sales List Code")

    def _get_tax_value(self, tax=None):
        value = super(TaxTemplate, self)._get_tax_value(tax=tax)
        if not tax or tax.ec_sales_list_code != self.ec_sales_list_code:
            value['ec_sales_list_code'] = self.ec_sales_list_code
        return value


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    ec_sales_list_code = fields.Char("EC Sales List Code",
        states={
            'readonly': (Bool(Eval('template', -1))
                & ~Eval('template_override', False)),
            },
        depends=['template', 'template_override'])


class ECSalesList(ModelSQL, ModelView):
    "EC Sales List"
    __name__ = 'account.ec_sales_list'

    company_tax_identifier = fields.Many2One(
        'party.identifier', "Company Tax Identifier")
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier")
    code = fields.Char("Code")
    amount = fields.Numeric(
        "Amount", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', "Currency")
    currency_digits = fields.Function(
        fields.Integer("Currency Digits"), 'get_currency_digits')

    def get_currency_digits(self, name):
        return self.currency.digits

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
        where = ((invoice.company == context.get('company'))
            & (period.fiscalyear == context.get('fiscalyear')))
        if context.get('period'):
            where &= (period.id == context.get('period'))
        where &= ((tax.ec_sales_list_code != Null)
            & (tax.ec_sales_list_code != ''))
        where &= invoice.type == 'out'
        return (invoice_tax
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
                invoice.party_tax_identifier.as_('party_tax_identifier'),
                tax.ec_sales_list_code.as_('code'),
                Sum(invoice_tax.base).as_('amount'),
                invoice.currency.as_('currency'),
                where=where,
                group_by=[
                    invoice.tax_identifier,
                    invoice.party_tax_identifier,
                    tax.ec_sales_list_code,
                    invoice.currency,
                    ]))


class ECSalesListContext(ModelView):
    "EC Sales List Context"
    __name__ = 'account.ec_sales_list.context'

    company = fields.Many2One('company.company', "Company", required=True)
    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True,
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    period = fields.Many2One(
        'account.period', "Period",
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ],
        depends=['fiscalyear'])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_fiscalyear(cls):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        context = Transaction().context
        return context.get(
            'fiscalyear',
            FiscalYear.find(context.get('company'), exception=False))

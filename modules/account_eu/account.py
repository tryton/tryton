# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal, Null
from sql.aggregate import Min, Sum
from sql.functions import CurrentTimestamp

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
    party = fields.Many2One('party.party', "Party")
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
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
                cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
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

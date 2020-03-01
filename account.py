# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal
from sql.aggregate import Max, Min, Sum
from sql.operators import Concat
from sql.functions import Position

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class AccountTemplate(metaclass=PoolMeta):
    __name__ = 'account.account.template'

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        cursor = Transaction().connection.cursor()
        model_data = ModelData.__table__()

        # Migration from 3.4: translation of the account chart
        cursor.execute(*model_data.select(model_data.id,
                where=((model_data.fs_id == 'be')
                    & (model_data.module == 'account_be'))))
        if cursor.fetchone():
            cursor.execute(*model_data.update(
                    columns=[model_data.fs_id],
                    values=[Concat(model_data.fs_id, '_fr')],
                    where=((Position('_fr', model_data.fs_id) == 0)
                        & (model_data.module == 'account_be'))))

        super(AccountTemplate, cls).__register__(module_name)


class BEVATCustomer(ModelSQL, ModelView):
    "Belgium VAT Customer"
    __name__ = 'account.be.vat_customer'

    company_tax_identifier = fields.Many2One(
        'party.identifier', "Company Tax Identifier")
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier")
    turnover = fields.Numeric(
        "Turnover", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    vat = fields.Numeric(
        "VAT", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', "Currency")
    currency_digits = fields.Function(
        fields.Integer("Currency Digits"), 'get_currency_digits')

    def get_currency_digits(self, name):
        return self.currency.digits

    @classmethod
    def tax_groups(cls):
        for group in ['group_tva_vente_biens', 'group_tva_vente_services',
                'tva_vente_biens_coco', 'tva_vente_services_coco']:
            for lang in ['fr', 'nl']:
                yield 'account_be', '%s_%s' % (group, lang)

    @classmethod
    def table_query(cls):
        pool = Pool()
        Identifier = pool.get('party.identifier')
        Invoice = pool.get('account.invoice')
        InvoiceTax = pool.get('account.invoice.tax')
        ModelData = pool.get('ir.model.data')
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Tax = pool.get('account.tax')
        context = Transaction().context
        company_identifier = Identifier.__table__()
        party_identifier = Identifier.__table__()
        invoice = Invoice.__table__()
        invoice_tax = InvoiceTax.__table__()
        move = Move.__table__()
        period = Period.__table__()
        tax = Tax.__table__()

        groups = []
        for module, fs_id in cls.tax_groups():
            try:
                groups.append(ModelData.get_id(module, fs_id))
            except KeyError:
                # table_query can be called before the XML is loaded
                continue

        where = ((invoice.company == context.get('company'))
            & (period.fiscalyear == context.get('fiscalyear')))
        where &= invoice.type == 'out'
        where &= (company_identifier.code.ilike('BE%')
            & (company_identifier.type == 'eu_vat'))
        where &= (party_identifier.code.ilike('BE%')
            & (party_identifier.type == 'eu_vat'))
        where &= tax.group.in_(groups)
        return (invoice_tax
            .join(invoice,
                condition=invoice_tax.invoice == invoice.id)
            .join(tax, condition=invoice_tax.tax == tax.id)
            .join(move, condition=invoice.move == move.id)
            .join(period, condition=move.period == period.id)
            .join(company_identifier,
                condition=invoice.tax_identifier == company_identifier.id)
            .join(party_identifier,
                condition=invoice.party_tax_identifier == party_identifier.id)
            .select(
                Max(invoice_tax.id).as_('id'),
                Literal(0).as_('create_uid'),
                Min(invoice_tax.create_date).as_('create_date'),
                Literal(0).as_('write_uid'),
                Max(invoice_tax.write_date).as_('write_date'),
                invoice.tax_identifier.as_('company_tax_identifier'),
                invoice.party_tax_identifier.as_('party_tax_identifier'),
                Sum(invoice_tax.base).as_('turnover'),
                Sum(invoice_tax.amount).as_('vat'),
                invoice.currency.as_('currency'),
                where=where,
                group_by=[
                    invoice.tax_identifier,
                    invoice.party_tax_identifier,
                    invoice.currency,
                    ]))


class BEVATCustomerContext(ModelView):
    "Belgium VAT Customer Context"
    __name__ = 'account.be.vat_customer.context'

    company = fields.Many2One('company.company', "Company", required=True)
    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True,
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])

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

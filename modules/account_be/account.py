# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.aggregate import Min, Sum

from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.account.exceptions import FiscalYearNotFoundError
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class CreateChart(metaclass=PoolMeta):
    __name__ = 'account.create_chart'

    def default_properties(self, fields):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        defaults = super().default_properties(fields)
        for lang in ['fr', 'nl']:
            try:
                template_id = ModelData.get_id('account_be.root_' + lang)
            except KeyError:
                continue
            if self.account.account_template.id == template_id:
                defaults['account_receivable'] = self.get_account(
                    'account_be.400_' + lang)
                defaults['account_payable'] = self.get_account(
                    'account_be.440_' + lang)
                break
        return defaults


class BEVATCustomer(ModelSQL, ModelView):
    __name__ = 'account.be.vat_customer'

    company_tax_identifier = fields.Many2One(
        'party.identifier', "Company Tax Identifier")
    party_tax_identifier = fields.Many2One(
        'party.identifier', "Party Tax Identifier")
    turnover = Monetary("Turnover", currency='currency', digits='currency')
    vat = Monetary("VAT", currency='currency', digits='currency')
    currency = fields.Many2One('currency.currency', "Currency")

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
        where &= ((company_identifier.code.ilike('BE%')
                & (company_identifier.type == 'eu_vat'))
            | (company_identifier.type == 'be_vat'))
        where &= ((party_identifier.code.ilike('BE%')
                & (party_identifier.type == 'eu_vat'))
            | (party_identifier.type == 'be_vat'))
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
                Min(invoice_tax.id).as_('id'),
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
    __name__ = 'account.be.vat_customer.context'

    company = fields.Many2One('company.company', "Company", required=True)
    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
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

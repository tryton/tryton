# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.modules.party.exceptions import EraseError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

supplier_currency = fields.Many2One(
    'currency.currency', "Supplier Currency",
    help="Default currency for purchases from this party.")


class Party(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party'
    customer_code = fields.MultiValue(fields.Char('Customer Code',
            help="The code the party as supplier has assigned to the company"
            " as customer."))
    customer_codes = fields.One2Many(
        'party.party.customer_code', 'party', "Customer Codes")
    supplier_lead_time = fields.MultiValue(fields.TimeDelta("Lead Time",
            help="The time from confirming the purchase order to receiving "
            "the goods from the party when used as a supplier.\n"
            "Used if no lead time is set on the product supplier."))
    supplier_lead_times = fields.One2Many(
        'party.party.supplier_lead_time', 'party', "Lead Times")
    supplier_currency = fields.MultiValue(supplier_currency)
    supplier_currencies = fields.One2Many(
        'party.party.supplier_currency', 'party', "Supplier Currencies")


class CustomerCode(ModelSQL, CompanyValueMixin):
    "Party Customer Code"
    __name__ = 'party.party.customer_code'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    customer_code = fields.Char('Customer Code')


class SupplierLeadTime(ModelSQL, CompanyValueMixin):
    "Supplier Lead Time"
    __name__ = 'party.party.supplier_lead_time'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    supplier_lead_time = fields.TimeDelta("Lead Time")


class PartySupplierCurrency(ModelSQL, ValueMixin):
    "Party Supplier Currency"
    __name__ = 'party.party.supplier_currency'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    supplier_currency = supplier_currency


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('purchase.product_supplier', 'party'),
            ('purchase.purchase', 'party'),
            ('purchase.purchase', 'invoice_party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        super(PartyErase, self).check_erase_company(party, company)

        purchases = Purchase.search([
                ('party', '=', party.id),
                ('company', '=', company.id),
                ('state', 'not in', ['done', 'cancelled']),
                ])
        if purchases:
            raise EraseError(
                gettext('purchase.msg_erase_party_pending_purchase',
                    party=party.rec_name,
                    company=company.rec_name))

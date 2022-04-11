# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.modules.party.exceptions import EraseError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

customer_currency = fields.Many2One(
    'currency.currency', "Customer Currency",
    help="Default currency for sales to this party.")


def get_sale_methods(field_name):
    @classmethod
    def func(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        return Sale.fields_get([field_name])[field_name]['selection'] + [
            (None, '')]
    return func


class Party(CompanyMultiValueMixin, metaclass=PoolMeta):
    __name__ = 'party.party'

    sale_invoice_method = fields.MultiValue(fields.Selection(
            'get_sale_invoice_method', "Invoice Method",
            help="The default sale invoice method for the customer.\n"
            "Leave empty to use the default value from the configuration."))
    sale_shipment_method = fields.MultiValue(fields.Selection(
            'get_sale_shipment_method', "Shipment Method",
            help="The default sale shipment method for the customer.\n"
            "Leave empty to use the default value from the configuration."))
    sale_methods = fields.One2Many(
        'party.party.sale_method', 'party', "Sale Methods")
    customer_currency = fields.MultiValue(customer_currency)
    customer_currencies = fields.One2Many(
        'party.party.customer_currency', 'party', "Customer Currencies")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'sale_invoice_method', 'sale_shipment_method'}:
            return pool.get('party.party.sale_method')
        return super().multivalue_model(field)

    get_sale_invoice_method = get_sale_methods('invoice_method')
    get_sale_shipment_method = get_sale_methods('shipment_method')

    @classmethod
    def copy(cls, parties, default=None):
        context = Transaction().context
        default = default.copy() if default else {}
        if context.get('_check_access'):
            fields = [
                'sale_methods', 'sale_invoice_method', 'sale_shipment_method']
            default_values = cls.default_get(fields, with_rec_name=False)
            for fname in fields:
                default.setdefault(fname, default_values.get(fname))
        return super().copy(parties, default=default)


class PartySaleMethod(ModelSQL, CompanyValueMixin):
    "Party Sale Method"
    __name__ = 'party.party.sale_method'

    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    sale_invoice_method = fields.Selection(
        'get_sale_invoice_method', "Sale Invoice Method")
    sale_shipment_method = fields.Selection(
        'get_sale_shipment_method', "Sale Shipment Method")

    get_sale_invoice_method = get_sale_methods('invoice_method')
    get_sale_shipment_method = get_sale_methods('shipment_method')


class PartyCustomerCurrency(ModelSQL, ValueMixin):
    "Party Customer Currency"
    __name__ = 'party.party.customer_currency'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    customer_currency = customer_currency


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('sale.sale', 'party'),
            ('sale.sale', 'invoice_party'),
            ('sale.sale', 'shipment_party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Sale = pool.get('sale.sale')
        super().check_erase_company(party, company)

        sales = Sale.search([
                ['OR',
                    ('party', '=', party.id),
                    ('shipment_party', '=', party.id),
                    ],
                ('company', '=', company.id),
                ('state', 'not in', ['done', 'cancelled']),
                ])
        if sales:
            raise EraseError(
                gettext('sale.msg_erase_party_pending_sale',
                    party=party.rec_name,
                    company=company.rec_name))

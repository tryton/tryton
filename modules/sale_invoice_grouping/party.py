# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    sale_invoice_grouping_method = fields.MultiValue(fields.Selection([
                (None, 'None'),
                ('standard', 'Standard'),
                ],
            'Sale Invoice Grouping Method'))
    sale_invoice_grouping_methods = fields.One2Many(
        'party.party.sale_invoice_grouping_method', 'party',
        "Sale Invoice Grouping Methods")

    @classmethod
    def default_sale_invoice_grouping_method(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        return Configuration(1).get_multivalue(
            'sale_invoice_grouping_method', **pattern)


class PartySaleInvoiceGroupingMethod(ModelSQL, ValueMixin):
    __name__ = 'party.party.sale_invoice_grouping_method'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE')
    sale_invoice_grouping_method = fields.Selection(
        'get_sale_invoice_grouping_methods', "Sale Invoice Grouping Method")

    @classmethod
    def get_sale_invoice_grouping_methods(cls):
        pool = Pool()
        Party = pool.get('party.party')
        field_name = 'sale_invoice_grouping_method'
        return Party.fields_get([field_name])[field_name]['selection']

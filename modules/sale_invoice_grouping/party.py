# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import PoolMeta, Pool
from trytond.tools.multivalue import migrate_property


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
    "Party Sale Invoice Grouping Method"
    __name__ = 'party.party.sale_invoice_grouping_method'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    sale_invoice_grouping_method = fields.Selection(
        'get_sale_invoice_grouping_methods', "Sale Invoice Grouping Method")

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(PartySaleInvoiceGroupingMethod, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('sale_invoice_grouping_method')
        value_names.append('sale_invoice_grouping_method')
        migrate_property(
            'party.party', field_names, cls, value_names,
            parent='party', fields=fields)

    @classmethod
    def get_sale_invoice_grouping_methods(cls):
        pool = Pool()
        Party = pool.get('party.party')
        field_name = 'sale_invoice_grouping_method'
        return Party.fields_get([field_name])[field_name]['selection']

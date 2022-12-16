# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import (ModelView, ModelSQL, ModelSingleton, ValueMixin,
    fields)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

purchase_invoice_method = fields.Selection(
    'get_purchase_invoice_method', "Invoice Method")


def get_purchase_methods(field_name):
    @classmethod
    def func(cls):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        return Purchase.fields_get([field_name])[field_name]['selection']
    return func


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Purchase Configuration'
    __name__ = 'purchase.configuration'
    purchase_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Purchase Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'purchase.purchase'),
                ]))
    purchase_invoice_method = fields.MultiValue(purchase_invoice_method)
    get_purchase_invoice_method = get_purchase_methods('invoice_method')
    purchase_process_after = fields.TimeDelta("Process Purchase after",
        help="The grace period during which confirmed purchase "
        "can still be reset to draft.\n"
        "Applied only if a worker queue is activated.")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'purchase_invoice_method':
            return pool.get('purchase.configuration.purchase_method')
        if field == 'purchase_sequence':
            return pool.get('purchase.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_purchase_sequence(cls, **pattern):
        return cls.multivalue_model(
            'purchase_sequence').default_purchase_sequence()

    @classmethod
    def default_purchase_invoice_method(cls, **pattern):
        return cls.multivalue_model(
            'purchase_invoice_method').default_purchase_invoice_method()


class ConfigurationSequence(ModelSQL, CompanyValueMixin):
    "Purchase Configuration Sequence"
    __name__ = 'purchase.configuration.sequence'
    purchase_sequence = fields.Many2One(
        'ir.sequence', "Purchase Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'purchase.purchase'),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ConfigurationSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('purchase_sequence')
        value_names.append('purchase_sequence')
        fields.append('company')
        migrate_property(
            'purchase.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_purchase_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('purchase', 'sequence_purchase')
        except KeyError:
            return None


class ConfigurationPurchaseMethod(ModelSQL, ValueMixin):
    "Purchase Configuration Purchase Method"
    __name__ = 'purchase.configuration.purchase_method'
    purchase_invoice_method = purchase_invoice_method
    get_purchase_invoice_method = get_purchase_methods('invoice_method')

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ConfigurationPurchaseMethod, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('purchase_invoice_method')
        value_names.append('purchase_invoice_method')
        migrate_property(
            'purchase.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_purchase_invoice_method(cls):
        return 'order'

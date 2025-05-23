# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelSingleton, ModelSQL, ModelView, ValueMixin, fields)
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.pool import Pool
from trytond.pyson import Eval, Id, TimeDelta

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
    __name__ = 'purchase.configuration'
    purchase_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Purchase Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('purchase', 'sequence_type_purchase')),
                ]))
    purchase_invoice_method = fields.MultiValue(purchase_invoice_method)
    get_purchase_invoice_method = get_purchase_methods('invoice_method')
    purchase_process_after = fields.TimeDelta(
        "Process Purchase after",
        domain=['OR',
            ('purchase_process_after', '=', None),
            ('purchase_process_after', '>=', TimeDelta()),
            ],
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
        return super().multivalue_model(field)

    @classmethod
    def default_purchase_sequence(cls, **pattern):
        return cls.multivalue_model(
            'purchase_sequence').default_purchase_sequence()

    @classmethod
    def default_purchase_invoice_method(cls, **pattern):
        return cls.multivalue_model(
            'purchase_invoice_method').default_purchase_invoice_method()


class ConfigurationSequence(ModelSQL, CompanyValueMixin):
    __name__ = 'purchase.configuration.sequence'
    purchase_sequence = fields.Many2One(
        'ir.sequence', "Purchase Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('purchase', 'sequence_type_purchase')),
            ])

    @classmethod
    def default_purchase_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('purchase', 'sequence_purchase')
        except KeyError:
            return None


class ConfigurationPurchaseMethod(ModelSQL, ValueMixin):
    __name__ = 'purchase.configuration.purchase_method'
    purchase_invoice_method = purchase_invoice_method
    get_purchase_invoice_method = get_purchase_methods('invoice_method')

    @classmethod
    def default_purchase_invoice_method(cls):
        return 'order'

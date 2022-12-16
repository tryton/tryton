# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool

__all__ = ['Configuration']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'sale.configuration'
    sale_price_list = fields.Function(fields.Many2One(
        'product.price_list', 'Sale Price List',
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ],
        states={
            'invisible': ~Eval('context', {}).get('company'),
            }),
        'get_sale_price_list', setter='set_sale_price_list')

    @classmethod
    def _get_sale_price_list_field(cls):
        pool = Pool()
        ModelField = pool.get('ir.model.field')
        field, = ModelField.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', 'sale_price_list'),
            ], limit=1)
        return field

    def get_sale_price_list(self, name):
        pool = Pool()
        Property = pool.get('ir.property')
        company_id = Transaction().context.get('company')
        sale_price_list_field = self._get_sale_price_list_field()
        properties = Property.search([
            ('field', '=', sale_price_list_field.id),
            ('res', '=', None),
            ('company', '=', company_id),
            ], limit=1)
        if properties:
            prop, = properties
            return prop.value.id

    @classmethod
    def set_sale_price_list(cls, configurations, name, value):
        pool = Pool()
        Property = pool.get('ir.property')
        company_id = Transaction().context.get('company')
        sale_price_list_field = cls._get_sale_price_list_field()
        properties = Property.search([
            ('field', '=', sale_price_list_field.id),
            ('res', '=', None),
            ('company', '=', company_id),
            ])
        Property.delete(properties)
        if value:
            Property.create([{
                        'field': sale_price_list_field.id,
                        'value': 'product.price_list,%s' % value,
                        'company': company_id,
                        }])

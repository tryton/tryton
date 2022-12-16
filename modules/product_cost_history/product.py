#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateAction
from trytond.pyson import PYSONEncoder
from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['ProductCostHistory', 'OpenProductCostHistory']


class ProductCostHistory(ModelSQL, ModelView):
    'History of Product Cost'
    __name__ = 'product.product.cost_history'
    _rec_name = 'date'
    template = fields.Many2One('product.template', 'Product')
    date = fields.DateTime('Date')
    cost_price = fields.Numeric('Cost Price')

    @classmethod
    def __setup__(cls):
        super(ProductCostHistory, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @staticmethod
    def table_query():
        pool = Pool()
        Property = pool.get('ir.property')
        Field = pool.get('ir.model.field')
        return ('SELECT '
                'MAX(h.__id) AS id, '
                'MAX(h.create_uid) AS create_uid, '
                'MAX(h.create_date) AS create_date, '
                'MAX(h.write_uid) AS write_uid, '
                'MAX(h.write_date) AS write_date, '
                'COALESCE(h.write_date, h.create_date) AS date, '
                'CAST(TRIM(\',\' FROM SUBSTRING(h.res FROM \',.*\')) AS '
                    'INTEGER) AS template, '
                'CAST(TRIM(\',\' FROM h.value) AS NUMERIC) AS cost_price '
            'FROM "' + Property._table + '__history" h '
                'JOIN "' + Field._table + '" f ON (f.id = h.field) '
            'WHERE f.name = \'cost_price\' '
                'AND h.res LIKE \'product.template,%%\' '
            'GROUP BY h.id, COALESCE(h.write_date, h.create_date), h.res, '
                'h.value',
            [])


class OpenProductCostHistory(Wizard):
    'Open Product Cost History'
    __name__ = 'product.product.cost_history.open'
    start_state = 'open'
    open = StateAction('product_cost_history.act_product_cost_history_form')

    def do_open(self, action):
        pool = Pool()
        Product = pool.get('product.product')

        active_id = Transaction().context.get('active_id')
        if not active_id or active_id < 0:
            action['pyson_domain'] = PYSONEncoder().encode([
                    ('template', '=', None),
                    ])
        else:
            product = Product(active_id)
            action['pyson_domain'] = PYSONEncoder().encode([
                    ('template', '=', product.template.id),
                    ])
        return action, {}

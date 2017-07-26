# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Column
from sql.aggregate import Max
from sql.conditionals import Coalesce

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateAction
from trytond.pyson import PYSONEncoder
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['ProductCostPrice', 'ProductCostHistory', 'OpenProductCostHistory']


class ProductCostPrice:
    __metaclass__ = PoolMeta
    __name__ = 'product.cost_price'
    _history = True


class ProductCostHistory(ModelSQL, ModelView):
    'History of Product Cost'
    __name__ = 'product.product.cost_history'
    template = fields.Many2One('product.template', 'Product')
    date = fields.DateTime('Date')
    cost_price = fields.Numeric('Cost Price')

    @classmethod
    def __setup__(cls):
        super(ProductCostHistory, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        ProductCostPrice = pool.get('product.cost_price')
        history = ProductCostPrice.__table_history__()
        return history.select(Max(Column(history, '__id')).as_('id'),
            Max(history.create_uid).as_('create_uid'),
            Max(history.create_date).as_('create_date'),
            Max(history.write_uid).as_('write_uid'),
            Max(history.write_date).as_('write_date'),
            Coalesce(history.write_date,
                history.create_date).as_('date'),
            history.template.as_('template'),
            history.cost_price.as_('cost_price'),
            group_by=(history.id,
                Coalesce(history.write_date, history.create_date),
                history.template, history.cost_price))

    def get_rec_name(self, name):
        return str(self.date)


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

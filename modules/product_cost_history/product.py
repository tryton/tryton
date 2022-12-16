# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Column, Literal, Window
from sql.aggregate import Max
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp, LastValue

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.product import round_price


def convert_from(table, tables):
    right, condition = tables[None]
    if table:
        table = table.join(right, condition=condition)
    else:
        table = right
    for k, sub_tables in tables.items():
        if k is None:
            continue
        table = convert_from(table, sub_tables)
    return table


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def get_multivalue(self, name, **pattern):
        context = Transaction().context
        if (name == 'cost_price'
                and context.get('_datetime')
                and self.type in ['goods', 'assets']):
            cost_price = self.get_cost_price_at(
                context['_datetime'].date(), **pattern)
            if cost_price is not None:
                return cost_price
        return super().get_multivalue(name, **pattern)

    def get_cost_price_at(self, date, **pattern):
        pool = Pool()
        CostHistory = pool.get('product.product.cost_history')
        company = pattern.get(
            'company', Transaction().context.get('company'))
        with Transaction().set_context(company=company):
            records = CostHistory.search([
                    ('date', '<=', date),
                    ('product', '=', self.id),
                    ], limit=1, order=[('date', 'DESC')])
        if records:
            record, = records
            return round_price(record.cost_price)


class CostPrice(metaclass=PoolMeta):
    __name__ = 'product.cost_price'
    _history = True


class ProductCostHistory(ModelSQL, ModelView):
    'History of Product Cost'
    __name__ = 'product.product.cost_history'
    product = fields.Many2One('product.product', "Product")
    date = fields.Date('Date')
    cost_price = fields.Numeric('Cost Price')

    @classmethod
    def __setup__(cls):
        super(ProductCostHistory, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        CostPrice = pool.get('product.cost_price')
        move = Move.__table__()
        product = Product.__table__()
        template = Template.__table__()
        history = CostPrice.__table_history__()
        database = Transaction().database

        tables, clause = Move.search_domain([
                ('state', '=', 'done'),
                Product()._domain_moves_cost(),
                # Incoming moves
                ('to_location.type', '=', 'storage'),
                ('from_location.type', '!=', 'storage'),
                ], tables={
                None: (move, None),
                })

        if database.has_window_functions():
            window = Window(
                [move.effective_date, move.product],
                order_by=[move.write_date.asc, move.id.asc])
            cost_price = LastValue(move.cost_price, window=window)
        else:
            cost_price = cls.cost_price.sql_cast(move.cost_price)

        move_history = convert_from(None, tables).select(
            (move.id * 2).as_('id'),
            move.effective_date.as_('date'),
            move.product.as_('product'),
            cost_price.as_('cost_price'),
            where=clause)
        query = move_history.select(
            Max(move_history.id).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            Literal(None).as_('write_uid'),
            Literal(None).as_('write_date'),
            move_history.date.as_('date'),
            move_history.product.as_('product'),
            Max(move_history.cost_price).as_('cost_price'),
            group_by=[move_history.date, move_history.product])

        price_datetime = Coalesce(history.write_date, history.create_date)
        price_date = cls.date.sql_cast(price_datetime)
        if database.has_window_functions():
            window = Window(
                [price_date, history.product],
                order_by=[price_datetime.asc])
            cost_price = LastValue(history.cost_price, window=window)
        else:
            cost_price = cls.cost_price.sql_cast(history.cost_price)

        price_history = (history
            .join(product, condition=history.product == product.id)
            .join(template, condition=product.template == template.id)
            .select(
                (Column(history, '__id') * 2 + 1).as_('id'),
                price_date.as_('date'),
                history.product.as_('product'),
                cost_price.as_('cost_price'),
                where=~template.type.in_(['goods', 'assets'])
                & cls._non_moves_clause(history)))

        query |= price_history.select(
            Max(price_history.id).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            Literal(None).as_('write_uid'),
            Literal(None).as_('write_date'),
            price_history.date.as_('date'),
            price_history.product.as_('product'),
            Max(price_history.cost_price).as_('cost_price'),
            group_by=[price_history.date, price_history.product])
        return query

    @classmethod
    def _non_moves_clause(cls, history_table):
        return history_table.company == Transaction().context.get('company')

    def get_rec_name(self, name):
        return str(self.date)

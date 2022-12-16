# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Column, Literal, Window
from sql.aggregate import Max
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp, LastValue

try:
    import pytz
except ImportError:
    pytz = None

from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


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
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context
        if (name == 'cost_price'
                and context.get('_datetime')
                and self.type in ['goods', 'assets']):
            datetime = context['_datetime']
            company = pattern.get(
                'company', Transaction().context.get('company'))
            if pytz and company:
                company = Company(company)
                if company.timezone:
                    timezone = pytz.timezone(company.timezone)
                    datetime = (
                        pytz.utc.localize(datetime, is_dst=None)
                        .astimezone(timezone))
            cost_price = self.get_cost_price_at(datetime.date(), **pattern)
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
        User = pool.get('res.user')
        move = Move.__table__()
        product = Product.__table__()
        template = Template.__table__()
        history = CostPrice.__table_history__()
        transaction = Transaction()
        database = transaction.database
        user = User(transaction.user)

        tables, clause = Move.search_domain([
                ('state', '=', 'done'),
                Product._domain_moves_cost(),
                ['OR',
                    Product._domain_in_moves_cost(),
                    Product._domain_out_moves_cost(),
                    ],
                ], tables={
                None: (move, None),
                })

        if database.has_window_functions():
            window = Window(
                [move.effective_date, move.product],
                frame='ROWS', start=None, end=None,
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

        if user.company:
            timezone = user.company.timezone
        else:
            timezone = None
        price_datetime = Coalesce(history.write_date, history.create_date)
        price_date = cls.date.sql_cast(price_datetime, timezone=timezone)
        if database.has_window_functions():
            window = Window(
                [price_date, history.product],
                frame='ROWS', start=None, end=None,
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
                & cls._non_moves_clause(history, user)))

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
    def _non_moves_clause(cls, history_table, user):
        company_id = user.company.id if user.company else None
        return history_table.company == company_id

    def get_rec_name(self, name):
        return str(self.date)

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from sql import Literal, Null
from sql.aggregate import Max
from sql.functions import Now
from sql.conditionals import Coalesce

from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder, Eval, Or
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice

from .move import StockMixin

__all__ = ['Template', 'Product',
    'ProductByLocationStart', 'ProductByLocation',
    'ProductQuantitiesByWarehouse', 'ProductQuantitiesByWarehouseStart',
    'OpenProductQuantitiesByWarehouse']
__metaclass__ = PoolMeta


class Template:
    __name__ = "product.template"
    quantity = fields.Function(fields.Float('Quantity'), 'sum_product')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
            'sum_product')
    cost_value = fields.Function(fields.Numeric('Cost Value'),
        'sum_product')

    def sum_product(self, name):
        if name not in ('quantity', 'forecast_quantity', 'cost_value'):
            raise Exception('Bad argument')
        sum_ = 0. if name != 'cost_value' else Decimal(0)
        for product in self.products:
            sum_ += getattr(product, name)
        return sum_

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._error_messages.update({
                'change_default_uom': ('You cannot change the default uom for '
                    'a product which is associated to stock moves.'),
                'change_type': ('You cannot change the type for a product '
                    'which is associated to stock moves.'),
                })
        cls.cost_price.states['required'] = Or(
            cls.cost_price.states.get('required', True),
            Eval('type').in_(['goods', 'assets']))
        cls.cost_price.depends.append('type')
        cls._modify_no_move = [
            ('default_uom', 'change_default_uom'),
            ('type', 'change_type'),
            ]

    @classmethod
    def check_no_move(cls, templates, error):
        Move = Pool().get('stock.move')
        for sub_templates in grouped_slice(templates):
            moves = Move.search([
                    ('product.template', 'in', [t.id for t in sub_templates]),
                    ],
                limit=1, order=[])
            if moves:
                cls.raise_user_error(error)

    @classmethod
    def write(cls, *args):
        if (Transaction().user != 0
                and Transaction().context.get('_check_access')):
            actions = iter(args)
            for templates, values in zip(actions, actions):
                for field, error in cls._modify_no_move:
                    if field in values:
                        cls.check_no_move(templates, error)
                        break
        super(Template, cls).write(*args)


class Product(object, StockMixin):
    __metaclass__ = PoolMeta
    __name__ = "product.product"
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity',
            searcher='search_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
            'get_quantity', searcher='search_quantity')
    cost_value = fields.Function(fields.Numeric('Cost Value'),
        'get_cost_value')

    @classmethod
    def get_quantity(cls, products, name):
        location_ids = Transaction().context.get('locations')
        return cls._get_quantity(products, name, location_ids, products)

    @classmethod
    def search_quantity(cls, name, domain=None):
        location_ids = Transaction().context.get('locations')
        return cls._search_quantity(name, location_ids, domain)

    @classmethod
    def get_cost_value(cls, products, name):
        cost_values = {}
        context = {}
        trans_context = Transaction().context
        if trans_context.get('stock_date_end'):
            # Use the last cost_price of the day
            context['_datetime'] = datetime.datetime.combine(
                trans_context['stock_date_end'], datetime.time.max)
        with Transaction().set_context(context):
            for product in products:
                # The date could be before the product creation
                if not isinstance(product.cost_price, Decimal):
                    cost_values[product.id] = None
                else:
                    cost_values[product.id] = (Decimal(str(product.quantity))
                        * product.cost_price)
        return cost_values

    @classmethod
    def products_by_location(cls, location_ids, product_ids=None,
            with_childs=False, grouping=('product',)):
        """
        Compute for each location and product the stock quantity in the default
        uom of the product.

        The context with keys:
            stock_skip_warehouse: if set, quantities on a warehouse are no more
                quantities of all child locations but quantities of the storage
                zone.

        Return a dictionary with location id and grouping as key
                and quantity as value.
        """
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        # Skip warehouse location in favor of their storage location
        # to compute quantities. Keep track of which ids to remove
        # and to add after the query.
        storage_to_remove = set()
        wh_to_add = {}
        if Transaction().context.get('stock_skip_warehouse'):
            location_ids = set(location_ids)
            for location in Location.browse(list(location_ids)):
                if location.type == 'warehouse':
                    location_ids.remove(location.id)
                    if location.storage_location.id not in location_ids:
                        storage_to_remove.add(location.storage_location.id)
                    location_ids.add(location.storage_location.id)
                    wh_to_add[location.id] = location.storage_location.id
            location_ids = list(location_ids)

        grouping_filter = (product_ids,) + tuple(None for k in grouping[1:])
        query = Move.compute_quantities_query(location_ids, with_childs,
            grouping=grouping, grouping_filter=grouping_filter)
        if query is None:
            return {}
        quantities = Move.compute_quantities(query, location_ids, with_childs,
            grouping=grouping, grouping_filter=grouping_filter)

        if wh_to_add:
            for wh, storage in wh_to_add.iteritems():
                for key in quantities:
                    if key[0] == storage:
                        quantities[(wh,) + key[1:]] = quantities[key]
                        if storage in storage_to_remove:
                            del quantities[key]
        return quantities


class ProductByLocationStart(ModelView):
    'Product by Location'
    __name__ = 'product.by_location.start'
    forecast_date = fields.Date(
        'At Date', help=('Allow to compute expected '
            'stock quantities for this date.\n'
            '* An empty value is an infinite date in the future.\n'
            '* A date in the past will provide historical values.'))

    @staticmethod
    def default_forecast_date():
        Date = Pool().get('ir.date')
        return Date.today()


class ProductByLocation(Wizard):
    'Product by Location'
    __name__ = 'product.by_location'
    start = StateView('product.by_location.start',
        'stock.product_by_location_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open', 'tryton-ok', default=True),
            ])
    open = StateAction('stock.act_location_quantity_tree')

    def do_open(self, action):
        pool = Pool()
        Product = pool.get('product.product')
        Lang = pool.get('ir.lang')

        context = {}
        product_id = Transaction().context['active_id']
        context['product'] = product_id
        if self.start.forecast_date:
            context['stock_date_end'] = self.start.forecast_date
        else:
            context['stock_date_end'] = datetime.date.max
        action['pyson_context'] = PYSONEncoder().encode(context)
        product = Product(product_id)

        for code in [Transaction().language, 'en_US']:
            langs = Lang.search([
                    ('code', '=', code),
                    ])
            if langs:
                break
        lang, = langs
        date = Lang.strftime(context['stock_date_end'],
            lang.code, lang.date)

        action['name'] += ' - %s (%s) @ %s' % (product.rec_name,
            product.default_uom.rec_name, date)
        return action, {}


class ProductQuantitiesByWarehouse(ModelSQL, ModelView):
    'Product Quantities By Warehouse'
    __name__ = 'stock.product_quantities_warehouse'
    date = fields.Date('Date')
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity')

    @classmethod
    def __setup__(cls):
        super(ProductQuantitiesByWarehouse, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @staticmethod
    def table_query():
        pool = Pool()
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')
        move = Move.__table__()

        product_id = Transaction().context.get('product')
        warehouse_id = Transaction().context.get('warehouse', -1)
        warehouse_query = Location.search([
                ('parent', 'child_of', [warehouse_id]),
                ], query=True, order=[])
        date_column = Coalesce(move.effective_date, move.planned_date
            ).as_('date')
        return move.select(
            Max(move.id).as_('id'),
            Literal(0).as_('create_uid'),
            Now().as_('create_date'),
            Literal(None).as_('write_uid'),
            Literal(None).as_('write_date'),
            date_column,
            where=(move.product == product_id)
            & (move.from_location.in_(warehouse_query)
                | move.to_location.in_(warehouse_query))
            & (Coalesce(move.effective_date, move.planned_date) != Null),
            group_by=(date_column, move.product))

    @classmethod
    def get_quantity(cls, lines, name):
        Product = Pool().get('product.product')

        product_id = Transaction().context.get('product')
        warehouse_id = Transaction().context.get('warehouse')

        dates = sorted(l.date for l in lines)
        quantities = {}
        date_start = None
        for date in dates:
            context = {
                'stock_date_start': date_start,
                'stock_date_end': date,
                'forecast': True,
                }
            with Transaction().set_context(**context):
                quantities[date] = Product.products_by_location(
                    [warehouse_id], [product_id],
                    with_childs=True).get((warehouse_id, product_id), 0)
            try:
                date_start = date + datetime.timedelta(1)
            except OverflowError:
                pass
        cumulate = 0
        for date in dates:
            cumulate += quantities[date]
            quantities[date] = cumulate

        return dict((l.id, quantities[l.date]) for l in lines)


class ProductQuantitiesByWarehouseStart(ModelView):
    'Product Quantities By Warehouse'
    __name__ = 'stock.product_quantities_warehouse.start'
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ])

    @staticmethod
    def default_warehouse():
        Location = Pool().get('stock.location')
        warehouses = Location.search([
                ('type', '=', 'warehouse'),
                ])
        if len(warehouses) == 1:
            return warehouses[0].id


class OpenProductQuantitiesByWarehouse(Wizard):
    'Product Quantities By Warehouse'
    __name__ = 'stock.product_quantities_warehouse'
    start = StateView('stock.product_quantities_warehouse.start',
        'stock.product_quantities_warehouse_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('stock.act_product_quantities_warehouse')

    def do_open_(self, action):
        Date = Pool().get('ir.date')
        action['pyson_context'] = PYSONEncoder().encode({
                'product': Transaction().context['active_id'],
                'warehouse': self.start.warehouse.id,
                })
        action['pyson_search_value'] = PYSONEncoder().encode([
                ('date', '>=', Date.today()),
                ])
        return action, {}

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import functools
from decimal import Decimal
from collections import defaultdict

from simpleeval import simple_eval

from sql import Literal, Null, Select
from sql.aggregate import Max
from sql.functions import CurrentTimestamp
from sql.conditionals import Coalesce

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.model.exceptions import AccessError
from trytond.wizard import (
    Wizard, StateTransition, StateAction, StateView, Button)
from trytond.pyson import Eval, If, Bool, PYSONEncoder
from trytond.tools import decistmt
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice

from trytond.modules.product import round_price

from .exceptions import ProductCostPriceError
from .move import StockMixin


def check_no_move(func):

    def find_moves(cls, records):
        pool = Pool()
        Move = pool.get('stock.move')
        if cls.__name__ == 'product.template':
            field = 'product.template'
        else:
            field = 'product'
        for sub_records in grouped_slice(records):
            moves = Move.search([
                    (field, 'in', list(map(int, sub_records))),
                    ],
                limit=1, order=[])
            if moves:
                return moves
        return False

    @functools.wraps(func)
    def decorator(cls, *args):
        pool = Pool()
        Template = pool.get('product.template')
        transaction = Transaction()
        if (transaction.user != 0
                and transaction.context.get('_check_access')):
            actions = iter(args)
            for records, values in zip(actions, actions):
                for field, msg in Template._modify_no_move:
                    if field in values:
                        if find_moves(cls, records):
                            raise AccessError(gettext(msg))
                        # No moves for those records
                        break
        func(cls, *args)
    return decorator


class Template(metaclass=PoolMeta):
    __name__ = "product.template"
    quantity = fields.Function(fields.Float('Quantity',
        help="The amount of stock in the location."),
        'sum_product')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity',
        help="The amount of stock expected to be in the location."),
        'sum_product')
    cost_value = fields.Function(fields.Numeric('Cost Value',
        help="The value of the stock in the location."),
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
        super().__setup__()
        cls._modify_no_move = [
            ('default_uom', 'stock.msg_product_change_default_uom'),
            ('type', 'stock.msg_product_change_type'),
            ('cost_price', 'stock.msg_product_change_cost_price'),
            ]

    @classmethod
    @check_no_move
    def write(cls, *args):
        super(Template, cls).write(*args)

    @classmethod
    def recompute_cost_price(cls, templates, start=None):
        pool = Pool()
        Product = pool.get('product.product')

        products = [p for t in templates for p in t.products]
        Product.recompute_cost_price(products, start=start)


class Product(StockMixin, object, metaclass=PoolMeta):
    __name__ = "product.product"
    quantity = fields.Function(fields.Float('Quantity',
        help="The amount of stock in the location."),
        'get_quantity', searcher='search_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity',
        help="The amount of stock expected to be in the location."),
        'get_quantity', searcher='search_quantity')
    cost_value = fields.Function(fields.Numeric('Cost Value',
        help="The value of the stock in the location."),
        'get_cost_value')

    @classmethod
    def get_quantity(cls, products, name):
        location_ids = Transaction().context.get('locations')
        product_ids = list(map(int, products))
        return cls._get_quantity(
            products, name, location_ids, grouping_filter=(product_ids,))

    @classmethod
    def search_quantity(cls, name, domain=None):
        location_ids = Transaction().context.get('locations')
        return cls._search_quantity(name, location_ids, domain)

    @classmethod
    def get_cost_value(cls, products, name):
        cost_values = {p.id: None for p in products}
        context = {}
        trans_context = Transaction().context
        if trans_context.get('stock_date_end'):
            # Use the last cost_price of the day
            context['_datetime'] = datetime.datetime.combine(
                trans_context['stock_date_end'], datetime.time.max)
            # The date could be before the product creation
            products = [p for p in products
                if p.create_date <= context['_datetime']]
        with Transaction().set_context(context):
            for product in cls.browse(products):
                # The product may not have a cost price
                if product.cost_price is not None:
                    cost_values[product.id] = (
                        Decimal(str(product.quantity)) * product.cost_price)
        return cost_values

    @classmethod
    @check_no_move
    def write(cls, *args):
        super(Product, cls).write(*args)

    @classmethod
    def products_by_location(cls, location_ids,
            with_childs=False, grouping=('product',), grouping_filter=None):
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

        query = Move.compute_quantities_query(location_ids, with_childs,
            grouping=grouping, grouping_filter=grouping_filter)
        if query is None:
            return {}
        quantities = Move.compute_quantities(query, location_ids, with_childs,
            grouping=grouping, grouping_filter=grouping_filter)

        if wh_to_add:
            for wh, storage in wh_to_add.items():
                for key in list(quantities.keys()):
                    if key[0] == storage:
                        quantities[(wh,) + key[1:]] = quantities[key]
                        if storage in storage_to_remove:
                            del quantities[key]
        return quantities

    @classmethod
    def recompute_cost_price_from_moves(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        products = set()
        for move in Move.search([
                    ('unit_price_updated', '=', True),
                    cls._domain_moves_cost(),
                    ],
                order=[('effective_date', 'ASC')]):
            if move.product not in products:
                cls.__queue__.recompute_cost_price(
                    [move.product], start=move.effective_date)
                products.add(move.product)

    @classmethod
    def recompute_cost_price(cls, products, start=None):
        pool = Pool()
        Move = pool.get('stock.move')
        costs = defaultdict(list)
        for product in products:
            if product.type == 'service':
                continue
            cost = getattr(
                product, 'recompute_cost_price_%s' %
                product.cost_price_method)(start)
            cost = round_price(cost)
            costs[cost].append(product)

        updated = []
        for sub_products in grouped_slice(products):
            domain = [
                ('unit_price_updated', '=', True),
                cls._domain_moves_cost(),
                ('product', 'in', [p.id for p in sub_products]),
                ]
            if start:
                domain.append(('effective_date', '>=', start))
            updated += Move.search(domain, order=[])
        if updated:
            Move.write(updated, {'unit_price_updated': False})

        if costs:
            cls.update_cost_price(costs)

    @classmethod
    def update_cost_price(cls, costs):
        "Update cost price of products from costs re-computation dictionary"
        to_write = []
        for cost, products in costs.items():
            to_write.append(products)
            to_write.append({'cost_price': cost})

        with Transaction().set_context(_check_access=False):
            cls.write(*to_write)

    def recompute_cost_price_fixed(self, start=None):
        return self.cost_price

    @classmethod
    def _domain_moves_cost(cls):
        "Returns the domain for moves to use in cost computation"
        context = Transaction().context
        return [
            ('company', '=', context.get('company')),
            ('state', '=', 'done'),
            ]

    def _get_storage_quantity(self, date=None):
        pool = Pool()
        Location = pool.get('stock.location')

        locations = Location.search([
            ('type', '=', 'storage'),
            ])
        if not date:
            date = datetime.date.today()
        location_ids = [l.id for l in locations]
        with Transaction().set_context(
                locations=location_ids,
                with_childs=False,
                stock_date_end=date):
            return self.__class__(self.id).quantity

    def recompute_cost_price_average(self, start=None):
        pool = Pool()
        Move = pool.get('stock.move')
        Currency = pool.get('currency.currency')
        Uom = pool.get('product.uom')
        Revision = pool.get('product.cost_price.revision')

        domain = [
            ('product', '=', self.id),
            self._domain_moves_cost(),
            ['OR',
                [
                    ('to_location.type', '=', 'storage'),
                    ('from_location.type', '!=', 'storage'),
                    ], [
                    ('from_location.type', '=', 'storage'),
                    ('to_location.type', '!=', 'storage'),
                    ],
                ],
            ]
        if start:
            domain.append(('effective_date', '>=', start))
        moves = Move.search(
                domain, order=[('effective_date', 'ASC'), ('id', 'ASC')])

        revisions = Revision.get_for_product(self)

        cost_price = Decimal(0)
        quantity = 0
        if start:
            domain.remove(('effective_date', '>=', start))
            domain.append(('effective_date', '<', start))
            domain.append(
                ('from_location.type', 'in', ['supplier', 'production']))
            prev_moves = Move.search(
                domain,
                order=[('effective_date', 'DESC'), ('id', 'DESC')],
                limit=1)
            if prev_moves:
                move, = prev_moves
                cost_price = move.cost_price
                quantity = self._get_storage_quantity(
                    date=start - datetime.timedelta(days=1))
                quantity = Decimal(str(quantity))

        current_moves = []
        current_cost_price = cost_price
        for move in moves:
            if (current_moves
                    and current_moves[-1].effective_date
                    != move.effective_date):
                Move.write([
                        m for m in current_moves
                        if m.cost_price != current_cost_price],
                    dict(cost_price=current_cost_price))
                current_moves.clear()
            current_moves.append(move)

            cost_price = Revision.apply_up_to(
                revisions, cost_price, move.effective_date)
            qty = Uom.compute_qty(move.uom, move.quantity, self.default_uom)
            qty = Decimal(str(qty))
            if move.from_location.type == 'storage':
                qty *= -1
            if (move.from_location.type in ['supplier', 'production']
                    or move.to_location.type == 'supplier'):
                with Transaction().set_context(date=move.effective_date):
                    unit_price = Currency.compute(
                        move.currency, move.unit_price,
                        move.company.currency, round=False)
                unit_price = Uom.compute_price(
                    move.uom, unit_price, self.default_uom)
                if quantity + qty > 0 and quantity >= 0:
                    cost_price = (
                        (cost_price * quantity) + (unit_price * qty)
                        ) / (quantity + qty)
                elif qty > 0:
                    cost_price = unit_price
                current_cost_price = round_price(cost_price)
            quantity += qty

        Move.write([
                m for m in current_moves
                if m.cost_price != current_cost_price],
            dict(cost_price=current_cost_price))

        for revision in revisions:
            cost_price = revision.get_cost_price(cost_price)
        return cost_price

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree/field[@name="quantity"]',
                'visual', If(Eval('quantity', 0) < 0, 'danger', '')),
            ('/tree/field[@name="forecast_quantity"]',
                'visual', If(Eval('forecast_quantity', 0) < 0, 'warning', '')),
            ]


class ProductByLocationContext(ModelView):
    'Product by Location'
    __name__ = 'product.by_location.context'
    forecast_date = fields.Date(
        'At Date',
        help="The date for which the stock quantity is calculated.\n"
        "* An empty value calculates as far ahead as possible.\n"
        "* A date in the past will provide historical values.")
    stock_date_end = fields.Function(fields.Date('At Date'),
        'on_change_with_stock_date_end')

    @staticmethod
    def default_forecast_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @fields.depends('forecast_date')
    def on_change_with_stock_date_end(self, name=None):
        if self.forecast_date is None:
            return datetime.date.max
        return self.forecast_date


class ProductQuantitiesByWarehouse(ModelSQL, ModelView):
    'Product Quantities By Warehouse'
    __name__ = 'stock.product_quantities_warehouse'

    class _Date(fields.Date):
        def get(self, ids, model, name, values=None):
            if values is None:
                values = {}
            result = {}
            for v in values:
                date = v[name]
                # SQLite does not convert to date
                if isinstance(date, str):
                    date = datetime.date(*map(int, date.split('-', 2)))
                result[v['id']] = date
            return result

    date = _Date('Date')
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity')

    del _Date

    @classmethod
    def __setup__(cls):
        super(ProductQuantitiesByWarehouse, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @staticmethod
    def table_query():
        pool = Pool()
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')
        move = from_ = Move.__table__()
        context = Transaction().context
        today = Date.today()

        if context.get('product_template') is not None:
            product = Product.__table__()
            from_ = move.join(product, condition=move.product == product.id)
            product_clause = (
                product.template == context['product_template'])
        else:
            product_clause = move.product == context.get('product', -1)

        warehouse_id = context.get('warehouse', -1)
        warehouse_query = Location.search([
                ('parent', 'child_of', [warehouse_id]),
                ], query=True, order=[])
        date_column = Coalesce(move.effective_date, move.planned_date)
        return (from_.select(
                Max(move.id).as_('id'),
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                Literal(None).as_('write_uid'),
                Literal(None).as_('write_date'),
                date_column.as_('date'),
                where=product_clause
                & (move.from_location.in_(warehouse_query)
                    | move.to_location.in_(warehouse_query))
                & (Coalesce(move.effective_date, move.planned_date) != Null)
                & (date_column != today),
                group_by=(date_column, move.product))
            | Select([
                    Literal(0).as_('id'),
                    Literal(0).as_('create_uid'),
                    CurrentTimestamp().as_('create_date'),
                    Literal(None).as_('write_uid'),
                    Literal(None).as_('write_date'),
                    Literal(today).as_('date'),
                    ]))

    @classmethod
    def get_quantity(cls, lines, name):
        Product = Pool().get('product.product')
        trans_context = Transaction().context

        def valid_context(name):
            return (trans_context.get(name) is not None
                and isinstance(trans_context[name], int))

        if not any(map(valid_context, ['product', 'product_template'])):
            return {l.id: None for l in lines}

        if trans_context.get('product') is not None:
            grouping = ('product',)
            grouping_filter = ([trans_context['product']],)
            key = trans_context['product']
        else:
            grouping = ('product.template',)
            grouping_filter = ([trans_context.get('product_template')],)
            key = trans_context['product_template']
        warehouse_id = trans_context.get('warehouse')

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
                    [warehouse_id],
                    grouping=grouping,
                    grouping_filter=grouping_filter,
                    with_childs=True).get((warehouse_id, key), 0)
            try:
                date_start = date + datetime.timedelta(1)
            except OverflowError:
                pass
        cumulate = 0
        for date in dates:
            cumulate += quantities[date]
            quantities[date] = cumulate

        return dict((l.id, quantities[l.date]) for l in lines)

    @classmethod
    def get_rec_name(cls, records, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Location = pool.get('stock.location')
        context = Transaction().context

        if context.get('product_template'):
            name = Template(context['product_template']).rec_name
        elif context.get('product'):
            name = Product(context['product']).rec_name
        else:
            name = ''
        if context.get('warehouse'):
            warehouse_name = Location(context['warehouse']).rec_name
        else:
            warehouse_name = '-'
        lang = Lang.get()
        names = {}
        for record in records:
            names[record.id] = '%s (%s) @ %s' % (
                name, warehouse_name, lang.strftime(record.date))
        return names


class ProductQuantitiesByWarehouseContext(ModelView):
    'Product Quantities By Warehouse'
    __name__ = 'stock.product_quantities_warehouse.context'
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ],
        help="The warehouse for which the quantities will be calculated.")
    stock_skip_warehouse = fields.Boolean(
        "Only storage zone",
        help="Check to use only the quantity of the storage zone.")

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @classmethod
    def default_stock_skip_warehouse(cls):
        return Transaction().context.get('stock_skip_warehouse')


class OpenProductQuantitiesByWarehouse(Wizard):
    "Open Product Quantities By Warehouse"
    __name__ = 'stock.product_quantities_warehouse.open'
    start_state = 'open_'
    open_ = StateAction('stock.act_move_form')

    def do_open_(self, action):
        pool = Pool()
        Date = pool.get('ir.date')
        ProductQuantitiesByWarehouse = pool.get(
            'stock.product_quantities_warehouse')
        context = Transaction().context
        today = Date.today()

        record = ProductQuantitiesByWarehouse(context['active_id'])
        warehouse_id = context.get('warehouse', -1)
        domain = [
            ['OR',
                [
                    ('from_location', 'child_of', [warehouse_id], 'parent'),
                    ('to_location', 'not child_of', [warehouse_id], 'parent'),
                    ],
                [
                    ('to_location', 'child_of', [warehouse_id], 'parent'),
                    ('from_location', 'not child_of',
                        [warehouse_id], 'parent'),
                    ],
                ],
            ['OR',
                ('effective_date', '=', record.date),
                [
                    ('effective_date', '=', None),
                    ('planned_date', '=', record.date),
                    ],
                ],
            ]
        if record.date < today:
            domain.append(('state', '=', 'done'))
        if context.get('product_template'):
            domain.append(
                ('product.template', '=', context['product_template']))
        else:
            domain.append(('product', '=', context.get('product', -1)))
        action['pyson_domain'] = PYSONEncoder().encode(domain)
        action['pyson_search_value'] = None
        action['name'] += ' (' + record.rec_name + ')'
        return action, {}


class RecomputeCostPrice(Wizard):
    'Recompute Cost Price'
    __name__ = 'product.recompute_cost_price'
    start = StateView(
        'product.recompute_cost_price.start',
        'stock.recompute_cost_price_start_view_form', [
            Button("Cancel", 'end'),
            Button("Recompute", 'recompute', default=True)])
    recompute = StateTransition()

    def default_start(self, fields):
        pool = Pool()
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        context = Transaction().context

        if context['active_model'] == 'product.product':
            products = Product.browse(context['active_ids'])
        elif context['active_model'] == 'product.template':
            templates = Template.browse(context['active_ids'])
            products = sum((t.products for t in templates), ())

        from_ = None
        for sub_products in grouped_slice(products):
            moves = Move.search([
                    ('unit_price_updated', '=', True),
                    Product._domain_moves_cost(),
                    ('product', 'in', [p.id for p in sub_products]),
                    ],
                order=[('effective_date', 'ASC')],
                limit=1)
            if moves:
                move, = moves
                from_ = min(from_ or datetime.date.max, move.effective_date)
        return {'from_': from_}

    def transition_recompute(self):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')

        context = Transaction().context

        if context['active_model'] == 'product.product':
            products = Product.browse(context['active_ids'])
            Product.recompute_cost_price(products, start=self.start.from_)
        elif context['active_model'] == 'product.template':
            templates = Template.browse(context['active_ids'])
            Template.recompute_cost_price(templates, start=self.start.from_)
        return 'end'


class RecomputeCostPriceStart(ModelView):
    "Recompute Cost Price"
    __name__ = 'product.recompute_cost_price.start'
    from_ = fields.Date("From")


class ModifyCostPrice(Wizard):
    "Modify Cost Price"
    __name__ = 'product.modify_cost_price'
    start = StateView(
        'product.modify_cost_price.start',
        'stock.product_modify_cost_price_start_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("OK", 'modify', default=True),
            ])
    modify = StateTransition()

    def transition_modify(self):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Revision = pool.get('product.cost_price.revision')
        Date = pool.get('ir.date')
        context = Transaction().context
        today = Date.today()
        revisions = []
        costs = defaultdict(list)
        if context['active_model'] == 'product.product':
            recompute_cost_price = Product.recompute_cost_price
            products = records = Product.browse(context['active_ids'])
            for product in products:
                revision = self.get_revision(Revision)
                revision.product = product
                revision.template = product.template
                revisions.append(revision)
                if ((
                            product.cost_price_method == 'fixed'
                            and revision.date == today)
                        or product.type == 'service'):
                    cost = revision.get_cost_price(product.cost_price)
                    costs[cost].append(product)
                    records.remove(product)
        elif context['active_model'] == 'product.template':
            recompute_cost_price = Template.recompute_cost_price
            templates = records = Template.browse(context['active_ids'])
            for template in templates:
                revision = self.get_revision(Revision)
                revision.template = template
                revisions.append(revision)
                if ((
                            template.cost_price_method == 'fixed'
                            and revision.date == today)
                        or template.type == 'service'):
                    for product in template.products:
                        cost = revision.get_cost_price(product.cost_price)
                        costs[cost].append(product)
                    records.remove(template)
        Revision.save(revisions)
        if costs:
            Product.update_cost_price(costs)
        if records:
            start = min((r.date for r in revisions), default=None)
            recompute_cost_price(records, start=start)
        return 'end'

    def get_revision(self, Revision):
        return Revision(
            company=Transaction().context.get('company'),
            date=self.start.date,
            cost_price=self.start.cost_price,
            )


class ModifyCostPriceStart(ModelView):
    "Modify Cost Price"
    __name__ = 'product.modify_cost_price.start'
    date = fields.Date("Date", required=True)
    cost_price = fields.Char(
        "New Cost Price", required=True,
        help="Python expression that will be evaluated with:\n"
        "- cost_price: the current cost price of the product")

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @classmethod
    def default_cost_price(cls):
        return 'cost_price'


class CostPriceRevision(ModelSQL, ModifyCostPriceStart):
    "Product Cost Price Revision"
    __name__ = 'product.cost_price.revision'
    template = fields.Many2One(
        'product.template', "Product",
        ondelete='CASCADE', select=True, required=True,
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ()),
            ],
        depends=['product'])
    product = fields.Many2One(
        'product.product', "Variant",
        ondelete='CASCADE', select=True,
        domain=[
            If(Bool(Eval('template')),
                ('template', '=', Eval('template')),
                ()),
            ],
        depends=['template'])
    company = fields.Many2One(
        'company.company', "Company", ondelete='CASCADE', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template

    @classmethod
    def validate(cls, revisions):
        super().validate(revisions)
        for revision in revisions:
            revision.check_cost_price()

    def check_cost_price(self):
        try:
            if not isinstance(self.get_cost_price(Decimal(0)), Decimal):
                raise ValueError
        except Exception as exception:
            raise ProductCostPriceError(
                gettext('stock.msg_invalid_cost_price',
                    cost_price=self.cost_price,
                    product=self.product.rec_name,
                    exception=exception)) from exception

    def get_cost_price(self, cost_price, **context):
        context.setdefault('names', {})['cost_price'] = cost_price
        context.setdefault('functions', {})['Decimal'] = Decimal
        return simple_eval(decistmt(self.cost_price), **context)

    @classmethod
    def _get_for_product_domain(cls):
        context = Transaction().context
        return [
            ('company', '=', context.get('company')),
            ]

    @classmethod
    def get_for_product(cls, product):
        revisions = cls.search([
                cls._get_for_product_domain(),
                ['OR',
                    ('product', '=', product.id),
                    [
                        ('template', '=', product.template.id),
                        ('product', '=', None),
                        ],
                    ],
                ],
            order=[('date', 'ASC'), ('id', 'ASC')])
        return revisions

    @classmethod
    def apply_up_to(cls, revisions, cost_price, date):
        """Apply revision to cost price up to date
        revisions list is modified"""
        try:
            while True:
                revision = revisions.pop(0)
                if revision.date <= date:
                    cost_price = revision.get_cost_price(cost_price)
                else:
                    revisions.insert(0, revision)
                    break
        except IndexError:
            pass
        return cost_price

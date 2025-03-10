# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import functools
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal

from simpleeval import InvalidExpression, simple_eval
from sql import Literal, Null, Select, Window, With
from sql.aggregate import Max, Sum
from sql.conditionals import Case, Coalesce
from sql.functions import CurrentTimestamp
from sql.operators import Concat

from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, fields
from trytond.model.exceptions import AccessError
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If, PYSONEncoder
from trytond.tools import decistmt, grouped_slice, reduce_ids
from trytond.tools import timezone as tz
from trytond.transaction import Transaction, without_check_access
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import ProductCostPriceError, ProductStockWarning
from .move import StockMixin
from .shipment import ShipmentAssignMixin


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
        if transaction.user and transaction.check_access:
            actions = iter(args)
            for records, values in zip(actions, actions):
                for field, msg in Template._modify_no_move:
                    if field in values:
                        if find_moves(cls, records):
                            raise AccessError(gettext(msg))
                        # No moves for those records
                        break

                if not values.get('template'):
                    continue
                template = Template(values['template'])
                for record in records:
                    for field, msg in Template._modify_no_move:
                        if isinstance(
                                getattr(Template, field), fields.Function):
                            continue
                        if getattr(record, field) != getattr(template, field):
                            if find_moves(cls, [record]):
                                raise AccessError(gettext(msg))
                            # No moves for this record
                            break
        func(cls, *args)
    return decorator


def check_no_stock_if_inactive(func):

    def get_product_locations(
            company, location_ids, sub_products, grouping=('product',)):
        pool = Pool()
        Product = pool.get('product.product')

        product2locations = defaultdict(list)
        product_ids = list(map(int, sub_products))
        with Transaction().set_context(company=company.id):
            quantities = Product.products_by_location(
                location_ids, with_childs=True,
                grouping=grouping, grouping_filter=(product_ids,))
        for key, quantity in quantities.items():
            location_id, product_id, = key
            if quantity:
                product2locations[product_id].append(location_id)
        return product2locations

    def raise_warning(cls, company, product2locations):
        pool = Pool()
        Location = pool.get('stock.location')
        Warning = pool.get('res.user.warning')

        for product_id, location_ids in product2locations.items():
            product = cls(product_id)
            locations = ','.join(
                l.rec_name for l in Location.browse(location_ids[:5]))
            if len(location_ids) > 5:
                locations += '...'
            warning_name = Warning.format(
                'deactivate_product_with_stock', [product])
            if Warning.check(warning_name):
                raise ProductStockWarning(warning_name,
                    gettext(
                        'stock.msg_product_location_quantity',
                        product=product.rec_name,
                        company=company.rec_name,
                        locations=locations),
                    gettext('stock.msg_product_location_quantity_description'))

    @functools.wraps(func)
    def decorator(cls, *args):
        pool = Pool()
        Company = pool.get('company.company')
        Location = pool.get('stock.location')

        if cls.__name__ == 'product.template':
            grouping = ('product.template',)
        else:
            grouping = ('product',)

        to_check = []
        actions = iter(args)
        for products, values in zip(actions, actions):
            if not values.get('active', True):
                to_check.extend(products)
        if to_check:
            with without_check_access():
                locations = Location.search([('type', '=', 'storage')])
                location_ids = list(map(int, locations))
                for company in Company.search([]):
                    for sub_products in grouped_slice(to_check):
                        product2locations = get_product_locations(
                            company, location_ids, sub_products, grouping)
                        raise_warning(cls, company, product2locations)
        return func(cls, *args)
    return decorator


class Template(metaclass=PoolMeta):
    __name__ = "product.template"
    quantity = fields.Function(
        fields.Float(
            "Quantity", digits='default_uom',
            help="The amount of stock in the location."),
        'sum_product')
    forecast_quantity = fields.Function(
        fields.Float(
            "Forecast Quantity", digits='default_uom',
            help="The amount of stock expected to be in the location."),
        'sum_product')
    cost_value = fields.Function(
        fields.Numeric(
            "Cost Value", digits=price_digits,
            help="The value of the stock in the location."),
        'sum_product')

    def sum_product(self, name):
        if name not in ('quantity', 'forecast_quantity', 'cost_value'):
            raise Exception('Bad argument')
        sum_ = 0. if name != 'cost_value' else Decimal(0)
        for product in self.products:
            sum_ += getattr(product, name) or 0
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
    @check_no_stock_if_inactive
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
    quantity = fields.Function(fields.Float(
            "Quantity", digits='default_uom',
            help="The amount of stock in the location."),
        'get_quantity', searcher='search_quantity')
    forecast_quantity = fields.Function(fields.Float(
            "Forecast Quantity", digits='default_uom',
            help="The amount of stock expected to be in the location."),
        'get_quantity', searcher='search_quantity')
    cost_value = fields.Function(fields.Numeric(
            "Cost Value", digits=price_digits,
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
        pool = Pool()
        Company = pool.get('company.company')
        cost_values = {p.id: None for p in products}
        context = {}
        trans_context = Transaction().context
        if trans_context.get('stock_date_end'):
            # Use the last cost_price of the day
            context['_datetime'] = datetime.datetime.combine(
                trans_context['stock_date_end'], datetime.time.max)
            company = trans_context.get('company')
            if company is not None and company >= 0:
                company = Company(company)
                if company.timezone:
                    timezone = tz.ZoneInfo(company.timezone)
                    try:
                        context['_datetime'] = (
                            context['_datetime']
                            .replace(tzinfo=timezone)
                            .astimezone(tz.UTC)
                            .replace(tzinfo=None))
                    except OverflowError:
                        pass
            # The date could be before the product creation
            products = [p for p in products
                if p.create_date <= context['_datetime']]
        with Transaction().set_context(context):
            for product, h_product in zip(products, cls.browse(products)):
                # The product may not have a cost price
                if h_product.cost_price is not None:
                    cost_values[product.id] = round_price(
                        Decimal(str(product.quantity)) * h_product.cost_price)
        return cost_values

    @classmethod
    @check_no_move
    @check_no_stock_if_inactive
    def write(cls, *args):
        super(Product, cls).write(*args)

    def can_be_deactivated(self):
        pool = Pool()
        Location = pool.get('stock.location')
        Company = pool.get('company.company')
        result = super().can_be_deactivated()
        locations = Location.search([('type', '=', 'storage')])
        location_ids = list(map(int, locations))
        for company in Company.search([]):
            with Transaction().set_context(
                    company=company.id,
                    locations=location_ids):
                product = self.__class__(self.id)
                if product.quantity:
                    result = False
        return result

    @classmethod
    def deactivate_replaced(cls, products=None):
        pool = Pool()
        Move = pool.get('stock.move')
        deactivated = super().deactivate_replaced(products=products)
        for sub_products in grouped_slice(deactivated):
            moves = Move.search([
                    ('product', 'in', list(map(int, sub_products))),
                    ('state', 'in', ['staging', 'draft']),
                    ])
            Move.delete(moves)
        return deactivated

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
    @without_check_access
    def update_cost_price(cls, costs):
        "Update cost price of products from costs re-computation dictionary"
        to_write = []
        for cost, products in costs.items():
            to_write.append(products)
            to_write.append({'cost_price': cost})
        cls.write(*to_write)

    def recompute_cost_price_fixed(self, start=None):
        return self.cost_price or Decimal(0)

    @classmethod
    def _domain_moves_cost(cls):
        "Returns the domain for moves to use in cost computation"
        context = Transaction().context
        return [
            ('company', '=', context.get('company')),
            ('state', '=', 'done'),
            ]

    @classmethod
    def _domain_in_moves_cost(cls):
        "Return the domain for incoming moves in cost computation"
        return [
            ('to_location.type', '=', 'storage'),
            ('from_location.type', '!=', 'storage'),
            ]

    @classmethod
    def _domain_out_moves_cost(cls):
        "Return the domain for outgoing moves in cost computation"
        return [
            ('from_location.type', '=', 'storage'),
            ('to_location.type', '!=', 'storage'),
            ]

    @classmethod
    def _domain_storage_quantity(cls):
        "Returns the domain for locations to use in cost computation"
        return [('type', '=', 'storage')]

    def _get_storage_quantity(self, date=None):
        pool = Pool()
        Location = pool.get('stock.location')

        locations = Location.search(self._domain_storage_quantity())
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
        Uom = pool.get('product.uom')
        Revision = pool.get('product.cost_price.revision')

        domain = [
            ('product', '=', self.id),
            self._domain_moves_cost(),
            ['OR',
                self._domain_in_moves_cost(),
                self._domain_out_moves_cost(),
                ]
            ]
        if start:
            domain.append(('effective_date', '>=', start))
        moves = Move.search(
                domain, order=[('effective_date', 'ASC'), ('id', 'ASC')])

        _in_moves = Move.search([
                ('product', '=', self.id),
                self._domain_moves_cost(),
                self._domain_in_moves_cost(),
                ], order=[])
        _in_moves = set(m.id for m in _in_moves)

        revisions = Revision.get_for_product(self)

        cost_price = Decimal(0)
        quantity = 0
        if start:
            domain.remove(('effective_date', '>=', start))
            domain.append(('effective_date', '<', start))
            domain.append(self._domain_in_moves_cost())
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

        def in_move(move):
            return move.id in _in_moves

        def out_move(move):
            return not in_move(move)

        def production_move(move):
            return (
                move.from_location.type == 'production'
                or move.to_location.type == 'production')

        current_moves = []
        current_cost_price = cost_price
        qty_production = 0
        for move in moves:
            if (current_moves
                    and current_moves[-1].effective_date
                    != move.effective_date):
                Move.write([
                        m for m in current_moves
                        if m.cost_price != current_cost_price],
                    dict(cost_price=current_cost_price))
                current_moves.clear()
                qty_production = 0
            current_moves.append(move)

            cost_price = Revision.apply_up_to(
                revisions, cost_price, move.effective_date)
            qty = Uom.compute_qty(move.unit, move.quantity, self.default_uom)
            qty = Decimal(str(qty))
            if out_move(move):
                qty *= -1
            if in_move(move):
                in_qty = qty
                if production_move(move) and qty_production < 0:
                    # Exclude quantity coming back from production
                    in_qty -= min(abs(qty_production), in_qty)
                unit_price = move.get_cost_price(product_cost_price=cost_price)
                if quantity + in_qty > 0 and quantity >= 0:
                    cost_price = (
                        (cost_price * quantity) + (unit_price * in_qty)
                        ) / (quantity + in_qty)
                elif in_qty > 0:
                    cost_price = unit_price
                current_cost_price = round_price(cost_price)
            quantity += qty
            if production_move(move):
                qty_production += qty

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

    company = fields.Many2One('company.company', "Company", required=True)
    forecast_date = fields.Date(
        'At Date',
        help="The date for which the stock quantity is calculated.\n"
        "* An empty value calculates as far ahead as possible.\n"
        "* A date in the past will provide historical values.")
    stock_date_end = fields.Function(fields.Date('At Date'),
        'on_change_with_stock_date_end')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @staticmethod
    def default_forecast_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @fields.depends('forecast_date')
    def on_change_with_stock_date_end(self, name=None):
        if self.forecast_date is None:
            return datetime.date.max
        return self.forecast_date


class OpenProductQuantitiesByWarehouse(Wizard):
    "Open Product Quantities By Warehouse"
    __name__ = 'stock.product_quantities_warehouse.open'
    start_state = 'open_'
    open_ = StateAction('stock.act_product_quantities_warehouse')

    def do_open_(self, action):
        encoder = PYSONEncoder()
        action['pyson_context'] = encoder.encode(self.get_context())
        action['pyson_search_value'] = encoder.encode(self.get_search_value())
        action['pyson_domain'] = encoder.encode(self.get_domain())
        action['name'] += '(' + self.record.rec_name + ')'
        return action, {}

    def get_context(self):
        context = {}
        if issubclass(self.model, ShipmentAssignMixin):
            context['product_template'] = None
            context['product'] = [
                m.product.id for m in self.record.assign_moves]
            warehouse = getattr(self.record, 'warehouse', None)
            if self.model == 'stock.shipment.internal':
                warehouse = self.record.from_location.warehouse
            if warehouse:
                context['warehouse'] = warehouse.id
        return context

    def get_search_value(self):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        value = [('date', '>=', today)]
        if (getattr(self.record, 'planned_date', None)
                and self.record.planned_date >= today):
            value.append(('date', '<=', self.record.planned_date))
        return value

    def get_domain(self):
        if issubclass(self.model, ShipmentAssignMixin):
            return [('product', 'in', [
                        str(m.product) for m in self.record.assign_moves])]
        return []


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
                    date = datetime.date.fromisoformat(date)
                result[v['id']] = date
            return result

    product = fields.Reference("Product", [
            ('product.product', "Variant"),
            ('product.template', "Product"),
            ])
    date = _Date('Date')
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity')
    company = fields.Many2One('company.company', "Company")

    del _Date

    @classmethod
    def __setup__(cls):
        super(ProductQuantitiesByWarehouse, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')
        move = from_ = Move.__table__()
        transaction = Transaction()
        context = transaction.context
        today = Date.today()

        if context.get('product_template') is not None:
            product_template = context['product_template']
            if isinstance(product_template, int):
                product_template = [product_template]
            product = Product.__table__()
            from_ = move.join(product, condition=move.product == product.id)
            if product_template:
                if len(product_template) > transaction.database.IN_MAX:
                    raise AccessError(gettext(
                            'stock.msg_product_quantities_max',
                            max=transaction.database.IN_MAX))
                product_clause = reduce_ids(product.template, product_template)
            else:
                product_clause = product.template == Null
            product_column = Concat('product.template,', product.template)
            products = [('product.template', i) for i in product_template]
        else:
            product = context.get('product')
            if product is None:
                product = []
            if isinstance(product, int):
                product = [product]
            if product:
                if len(product) > transaction.database.IN_MAX:
                    raise AccessError(gettext(
                            'stock.msg_product_quantities_max',
                            max=transaction.database.IN_MAX))
                product_clause = reduce_ids(move.product, product)
            else:
                product_clause = move.product == Null
            product_column = Concat('product.product,', move.product)
            products = [('product.product', i) for i in product]

        if 'warehouse' in context:
            warehouse = Location(context.get('warehouse'))
            if context.get('stock_skip_warehouse'):
                location_id = warehouse.storage_location.id
            else:
                location_id = warehouse.id
        else:
            location_id = -1
        warehouse = With('id', query=Location.search([
                    ('parent', 'child_of', [location_id]),
                    ], query=True, order=[]))
        date_column = Coalesce(move.effective_date, move.planned_date)
        query = (from_.select(
                Max(move.id * 3).as_('id'),
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                Literal(None).as_('write_uid'),
                Literal(None).as_('write_date'),
                product_column.as_('product'),
                date_column.as_('date'),
                move.company.as_('company'),
                where=product_clause
                & (
                    (move.from_location.in_(
                            warehouse.select(warehouse.id))
                        & ~move.to_location.in_(
                            warehouse.select(warehouse.id)))
                    | (~move.from_location.in_(
                            warehouse.select(warehouse.id))
                        & move.to_location.in_(
                            warehouse.select(warehouse.id))))
                & ((date_column < today) & (move.state == 'done')
                    | (date_column > today)),
                group_by=(date_column, product_column, move.company),
                with_=warehouse))
        for model, id_ in products:
            gap = ['product.template', 'product.product'].index(model) + 1
            query |= Select([
                    Literal(id_ * 3 + gap).as_('id'),
                    Literal(0).as_('create_uid'),
                    CurrentTimestamp().as_('create_date'),
                    Literal(None).as_('write_uid'),
                    Literal(None).as_('write_date'),
                    Literal('%s,%s' % (model, id_)).as_('product'),
                    Literal(today).as_('date'),
                    Literal(context.get('company', -1)).as_('company'),
                    ])
        return query

    @classmethod
    def parse_view(cls, tree, type, *args, **kwargs):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        context = Transaction().context
        if kwargs.get('view_depends') is None:
            view_depends = []
        else:
            view_depends = kwargs['view_depends'].copy()
        kwargs['view_depends'] = view_depends
        if type == 'graph':
            encoder = PYSONEncoder()
            if context.get('product_template') is not None:
                product_template = context['product_template']
                if isinstance(product_template, int):
                    product_template = [product_template]
                records = Template.browse(product_template)
            elif context.get('product'):
                product = context['product']
                if product is None:
                    product = -1
                if isinstance(product, int):
                    product = [product]
                records = Product.browse(product)
            else:
                records = []
            if len(records) > 1:
                quantity_node, = tree.xpath('//y/field[@name="quantity"]')
                parent = quantity_node.getparent()
                parent.remove(quantity_node)
                for record in records:
                    node = deepcopy(quantity_node)
                    node.set('key', str(record.id))
                    node.set('string', record.rec_name)
                    node.set('domain', encoder.encode(
                            Eval('product') == str(record)))
                    node.set('fill', '0')
                    parent.append(node)
                graph, = tree.xpath('/graph')
                graph.set('legend', '1')
            view_depends.append('product')
        return super().parse_view(tree, type, *args, **kwargs)

    @classmethod
    def get_quantity(cls, lines, name):
        Product = Pool().get('product.product')
        trans_context = Transaction().context

        if trans_context.get('product_template') is not None:
            grouping = ('product.template',)
            product_template = trans_context['product_template']
            if isinstance(product_template, int):
                product_template = [product_template]
            grouping_filter = (product_template,)
        else:
            grouping = ('product',)
            product = trans_context.get('product', -1)
            if product is None:
                product = -1
            if isinstance(product, int):
                product = [product]
            grouping_filter = (product,)
        warehouse_id = trans_context.get('warehouse')

        def cast_date(date):
            if isinstance(date, str):
                date = datetime.date.fromisoformat(date)
            return date

        dates = sorted({cast_date(l.date) for l in lines})
        quantities = {}
        keys = set()
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
                    with_childs=True)
                keys.update(quantities[date])
            try:
                date_start = date + datetime.timedelta(1)
            except OverflowError:
                pass
        cumulate = defaultdict(lambda: 0)
        for date in dates:
            for key in keys:
                cumulate[key] += quantities[date][key]
                quantities[date][key] = cumulate[key]

        return {
            l.id: quantities[cast_date(l.date)].get(
                (warehouse_id, int(l.product)), 0)
            for l in lines}

    def get_rec_name(self, name):
        return self.product.rec_name if self.product else ''


class ProductQuantitiesByWarehouseContext(ModelView):
    'Product Quantities By Warehouse'
    __name__ = 'stock.product_quantities_warehouse.context'

    company = fields.Many2One('company.company', "Company", required=True)
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ],
        help="The warehouse for which the quantities will be calculated.")
    stock_skip_warehouse = fields.Boolean(
        "Only storage zone",
        help="Check to use only the quantity of the storage zone.")

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @classmethod
    def default_stock_skip_warehouse(cls):
        return Transaction().context.get('stock_skip_warehouse')


class OpenProductQuantitiesByWarehouseMove(Wizard):
    "Open Product Quantities By Warehouse Moves"
    __name__ = 'stock.product_quantities_warehouse.move.open'
    start_state = 'open_'
    open_ = StateAction('stock.act_product_quantities_warehouse_move')

    def do_open_(self, action):
        encoder = PYSONEncoder()
        action['pyson_context'] = '{}'
        action['pyson_search_value'] = encoder.encode(
            [('date', '>=', self.record.date)])
        action['pyson_domain'] = encoder.encode(
            [('product', '=', str(self.record.product))])
        action['name'] += ' (' + self.record.rec_name + ')'
        return action, {}


class ProductQuantitiesByWarehouseMove(ModelSQL, ModelView):
    "Product Quantities By Warehouse Moves"
    __name__ = 'stock.product_quantities_warehouse.move'

    product = fields.Reference("Product", [
            ('product.product', "Variant"),
            ('product.template', "Product"),
            ])
    date = fields.Date("Date")
    move = fields.Many2One('stock.move', "Move")
    origin = fields.Reference("Origin", selection='get_origin')
    document = fields.Function(
        fields.Reference("Document", selection='get_documents'),
        'get_document')
    quantity = fields.Float("Quantity")
    cumulative_quantity_start = fields.Function(
        fields.Float("Cumulative Quantity Start"), 'get_cumulative_quantity')
    cumulative_quantity_delta = fields.Float("Cumulative Quantity Delta")
    cumulative_quantity_end = fields.Function(
        fields.Float("Cumulative Quantity End"), 'get_cumulative_quantity')
    company = fields.Many2One('company.company', "Company")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        move = from_ = Move.__table__()
        transaction = Transaction()
        context = transaction.context
        database = transaction.database
        today = Date.today()

        if context.get('product_template') is not None:
            product_template = context['product_template']
            if isinstance(product_template, int):
                product_template = [product_template]
            product = Product.__table__()
            from_ = move.join(product, condition=move.product == product.id)
            if product_template:
                if len(product_template) > transaction.database.IN_MAX:
                    raise AccessError(gettext(
                            'stock.msg_product_quantities_max',
                            max=transaction.database.IN_MAX))
                product_clause = reduce_ids(product.template, product_template)
            else:
                product_clause = product.template == Null
            product_column = Concat('product.template,', product.template)
        else:
            product = context.get('product', -1)
            if product is None:
                product = -1
            if isinstance(product, int):
                product = [product]
            if product:
                if len(product) > transaction.database.IN_MAX:
                    raise AccessError(gettext(
                            'stock.msg_product_quantities_max',
                            max=transaction.database.IN_MAX))
                product_clause = reduce_ids(move.product, product)
            else:
                product_clause = move.product == Null
            product_column = Concat('product.product,', move.product)

        if 'warehouse' in context:
            warehouse = Location(context.get('warehouse'))
            if context.get('stock_skip_warehouse'):
                location_id = warehouse.storage_location.id
            else:
                location_id = warehouse.id
        else:
            location_id = -1
        warehouse = With('id', query=Location.search([
                    ('parent', 'child_of', [location_id]),
                    ], query=True, order=[]))
        date_column = Coalesce(
            move.effective_date,
            Case((move.state == 'assigned', today), else_=Null),
            move.planned_date)
        quantity = Case(
            (move.to_location.in_(warehouse.select(warehouse.id)),
                move.internal_quantity),
            else_=-move.internal_quantity)
        if database.has_window_functions():
            cumulative_quantity_delta = Sum(
                quantity,
                window=Window(
                    [product_column, date_column], order_by=[move.id.asc]))
        else:
            cumulative_quantity_delta = Literal(0)
        return (from_.select(
                move.id.as_('id'),
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                Literal(None).as_('write_uid'),
                Literal(None).as_('write_date'),
                product_column.as_('product'),
                date_column.as_('date'),
                move.id.as_('move'),
                move.origin.as_('origin'),
                quantity.as_('quantity'),
                cumulative_quantity_delta.as_('cumulative_quantity_delta'),
                move.company.as_('company'),
                where=product_clause
                & (
                    (move.from_location.in_(
                            warehouse.select(warehouse.id))
                        & ~move.to_location.in_(
                            warehouse.select(warehouse.id)))
                    | (~move.from_location.in_(
                            warehouse.select(warehouse.id))
                        & move.to_location.in_(
                            warehouse.select(warehouse.id))))
                & ((date_column < today) & (move.state == 'done')
                    | (date_column >= today) & (move.state != 'cancelled')),
                with_=warehouse))

    @classmethod
    def get_origin(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return Move.get_origin()

    @classmethod
    def _get_document_models(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        return [m for m, _ in Move.get_shipment() if m]

    @classmethod
    def get_documents(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = cls._get_document_models()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    def get_document(self, name):
        if self.move and self.move.shipment:
            return str(self.move.shipment)

    @classmethod
    def get_cumulative_quantity(cls, records, names):
        pool = Pool()
        Product = pool.get('product.product')
        transaction = Transaction()
        database = transaction.database
        trans_context = transaction.context

        if trans_context.get('product_template') is not None:
            grouping = ('product.template',)
            product_template = trans_context['product_template']
            if isinstance(product_template, int):
                product_template = [product_template]
            grouping_filter = (product_template,)
        else:
            grouping = ('product',)
            product = trans_context.get('product', -1)
            if product is None:
                product = -1
            if isinstance(product, int):
                product = [product]
            grouping_filter = (product,)
        warehouse_id = trans_context.get('warehouse')

        def cast_date(date):
            if isinstance(date, str):
                date = datetime.date.fromisoformat(date)
            return date

        dates = sorted({cast_date(r.date) for r in records})
        quantities = {}
        keys = set()
        date_start = None
        for date in dates:
            try:
                context = {
                    'stock_date_start': date_start,
                    'stock_date_end': date - datetime.timedelta(days=1),
                    'forecast': True,
                    }
            except OverflowError:
                pass
            with Transaction().set_context(**context):
                quantities[date] = Product.products_by_location(
                    [warehouse_id],
                    grouping=grouping,
                    grouping_filter=grouping_filter,
                    with_childs=True)
                keys.update(quantities[date])
            date_start = date
        cumulate = defaultdict(lambda: 0)
        for date in dates:
            for key in keys:
                cumulate[key] += quantities[date][key]
                quantities[date][key] = cumulate[key]

        result = {}
        if database.has_window_functions():
            if 'cumulative_quantity_start' in names:
                result['cumulative_quantity_start'] = {
                    r.id: (
                        quantities[cast_date(r.date)].get(
                            (warehouse_id, int(r.product)), 0)
                        + r.cumulative_quantity_delta
                        - r.quantity)
                    for r in records}
            if 'cumulative_quantity_end' in names:
                result['cumulative_quantity_end'] = {
                    r.id: (
                        quantities[cast_date(r.date)].get(
                            (warehouse_id, int(r.product)), 0)
                        + r.cumulative_quantity_delta)
                    for r in records}
        else:
            values = {
                r.id: quantities[cast_date(r.date)].get(
                    (warehouse_id, int(r.product)), 0)
                for r in records}
            for name in names:
                result[name] = values
        return result

    def get_rec_name(self, name):
        return self.move.rec_name


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

        if self.model.__name__ == 'product.product':
            products = self.records
        elif self.model.__name__ == 'product.template':
            templates = self.records
            products = sum((t.products for t in templates), ())
        else:
            products = []

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
        self.model.recompute_cost_price(self.records, start=self.start.from_)
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
        Revision = pool.get('product.cost_price.revision')
        Date = pool.get('ir.date')
        today = Date.today()
        revisions = []
        costs = defaultdict(list)
        if self.model.__name__ == 'product.product':
            records = list(self.records)
            for product in list(records):
                revision = self.get_revision(Revision)
                revision.product = product
                revision.template = product.template
                revisions.append(revision)
                if ((
                            product.cost_price_method == 'fixed'
                            and revision.date == today)
                        or product.type == 'service'):
                    cost = round_price(
                        revision.get_cost_price(product.cost_price))
                    costs[cost].append(product)
                    records.remove(product)
        elif self.model.__name__ == 'product.template':
            records = list(self.records)
            for template in list(records):
                revision = self.get_revision(Revision)
                revision.template = template
                revisions.append(revision)
                if ((
                            template.cost_price_method == 'fixed'
                            and revision.date == today)
                        or template.type == 'service'):
                    for product in template.products:
                        cost = round_price(
                            revision.get_cost_price(product.cost_price))
                        costs[cost].append(product)
                    records.remove(template)
        Revision.save(revisions)
        if costs:
            Product.update_cost_price(costs)
        if records:
            start = min((r.date for r in revisions), default=None)
            self.model.recompute_cost_price(records, start=start)
        return 'end'

    def get_revision(self, Revision):
        return Revision(
            template=None,
            product=None,
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
        ondelete='CASCADE', required=True,
        domain=[
            If(Bool(Eval('product')),
                ('products', '=', Eval('product')),
                ()),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    product = fields.Many2One(
        'product.product', "Variant",
        ondelete='CASCADE',
        domain=[
            If(Bool(Eval('template')),
                ('template', '=', Eval('template')),
                ()),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    company = fields.Many2One(
        'company.company', "Company", ondelete='CASCADE', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(
                t,
                (t.product, Index.Range()),
                (t.template, Index.Range()),
                (t.company, Index.Range())))
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template

    @classmethod
    def validate_fields(cls, revisions, field_names):
        super().validate_fields(revisions, field_names)
        cls.check_cost_price(revisions, field_names)

    @classmethod
    def check_cost_price(cls, revisions, field_names):
        if field_names and 'cost_price' not in field_names:
            return
        for revision in revisions:
            revision.get_cost_price(Decimal(0))

    def get_cost_price(self, cost_price, **context):
        context.setdefault('names', {})['cost_price'] = cost_price
        context.setdefault('functions', {})['Decimal'] = Decimal
        try:
            amount = simple_eval(decistmt(self.cost_price), **context)
        except (InvalidExpression, SyntaxError) as exception:
            product = self.product or self.template
            raise ProductCostPriceError(
                gettext('stock.msg_invalid_cost_price',
                    cost_price=self.cost_price,
                    product=product.rec_name if product else '',
                    exception=exception)) from exception
        if not isinstance(amount, Decimal):
            raise ProductCostPriceError(
                gettext('stock.msg_invalid_cost_price_not_number',
                    value=amount,
                    cost_price=self.cost_price,
                    product=product.rec_name))
        return amount

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

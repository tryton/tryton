#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from operator import itemgetter
from sql import Literal, Union, Column
from sql.aggregate import Max, Sum
from sql.functions import Now
from sql.conditionals import Coalesce

from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder, Eval, Or
from trytond.transaction import Transaction
from trytond.tools import safe_eval, reduce_ids
from trytond.pool import Pool, PoolMeta

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
                })
        cls.cost_price.states['required'] = Or(
            cls.cost_price.states.get('required', True),
            Eval('type').in_(['goods', 'assets']))
        cls.cost_price.depends.append('type')

    @classmethod
    def write(cls, templates, vals):
        Move = Pool().get('stock.move')
        cursor = Transaction().cursor
        if not vals.get("default_uom"):
            super(Template, cls).write(templates, vals)
            return

        for i in range(0, len(templates), cursor.IN_MAX):
            sub_ids = [t.id for t in templates[i:i + cursor.IN_MAX]]
            templates_to_check = cls.search([
                    ('id', 'in', sub_ids),
                    ('default_uom', '!=', vals['default_uom']),
                    ])

            if templates_to_check:
                if Move.search([
                            ('product.template', 'in',
                                [t.id for t in templates_to_check]),
                            ], limit=1):
                    cls.raise_user_error('change_default_uom')

        super(Template, cls).write(templates, vals)


class Product:
    __name__ = "product.product"
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity',
            searcher='search_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
            'get_quantity', searcher='search_quantity')
    cost_value = fields.Function(fields.Numeric('Cost Value'),
        'get_cost_value')

    @classmethod
    def get_quantity(cls, products, name):
        Date = Pool().get('ir.date')

        quantities = dict((p.id, 0.0) for p in products)
        if not Transaction().context.get('locations'):
            return quantities

        context = {}
        if (name == 'quantity'
                and Transaction().context.get('stock_date_end')
                and Transaction().context.get('stock_date_end') >
                Date.today()):
            context['stock_date_end'] = Date.today()

        if name == 'forecast_quantity':
            context['forecast'] = True
            if not Transaction().context.get('stock_date_end'):
                context['stock_date_end'] = datetime.date.max
        with Transaction().set_context(context):
            pbl = cls.products_by_location(
                location_ids=Transaction().context['locations'],
                product_ids=quantities.keys(), with_childs=True)

        for location in Transaction().context['locations']:
            for product in products:
                quantities[product.id] += pbl.get((location, product.id), 0.0)
        return quantities

    @staticmethod
    def _search_quantity_eval_domain(line, domain):
        field, operator, operand = domain
        value = line.get(field)
        if value is None:
            return False
        if operator not in ("=", ">=", "<=", ">", "<", "!="):
            return False
        if operator == "=":
            operator = "=="
        return (safe_eval(str(value) + operator + str(operand)))

    @classmethod
    def search_quantity(cls, name, domain=None):
        Date = Pool().get('ir.date')

        if not (Transaction().context.get('locations') and domain):
            return []

        context = {}
        if (name == 'quantity'
                and Transaction().context.get('stock_date_end')
                and Transaction().context.get('stock_date_end') >
                Date.today()):
            context['stock_date_end'] = Date.today()

        if name == 'forecast_quantity':
            context['forecast'] = True
            if not Transaction().context.get('stock_date_end'):
                context['stock_date_end'] = datetime.date.max

        with Transaction().set_context(context):
            pbl = cls.products_by_location(
                    location_ids=Transaction().context['locations'],
                    with_childs=True).iteritems()

        processed_lines = []
        for (location, product), quantity in pbl:
            processed_lines.append({
                    'location': location,  # XXX useful ?
                    'product': product,
                    name: quantity,
                    })

        res = [line['product'] for line in processed_lines
            if cls._search_quantity_eval_domain(line, domain)]
        return [('id', 'in', res)]

    @classmethod
    def get_cost_value(cls, products, name):
        cost_values = {}
        context = {}
        trans_context = Transaction().context
        if 'stock_date_end' in context:
            context['_datetime'] = trans_context['stock_date_end']
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
                stock_date_end: if set the date of the stock computation.
                stock_date_start: if set return the delta of the stock
                    between the two dates, (ignored if stock_date_end is
                    missing).
                stock_assign: if set compute also the assigned moves as done.
                forecast: if set compute the forecast quantity.
                stock_destinations: A list of location ids. If set, restrict
                    the computation to moves from and to those locations.
                stock_skip_warehouse: if set, quantities on a warehouse are no
                    more quantities of all child locations but quantities of
                    the storage zone.
        If product_ids is None all products are used.
        If with_childs, it computes also for child locations.
        grouping defines how stock moves are grouped.

        Return a dictionary with location id and grouping as key
                and quantity as value.
        """
        pool = Pool()
        Uom = pool.get('product.uom')
        Rule = pool.get('ir.rule')
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        Period = pool.get('stock.period')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')

        move = Move.__table__()
        product = Product.__table__()
        template = Template.__table__()

        today = Date.today()

        if not location_ids:
            return {}
        cursor = Transaction().cursor
        context = Transaction().context.copy()

        for field in grouping:
            if field not in Move._fields:
                raise ValueError('"%s" has no field "%s"' % (Move, field))
        assert 'product' in grouping

        # Skip warehouse location in favor of their storage location
        # to compute quantities. Keep track of which ids to remove
        # and to add after the query.
        location_ids = set(location_ids)
        storage_to_remove = set()
        wh_to_add = {}
        for location in Location.browse(list(location_ids)):
            if (location.type == 'warehouse'
                    and Transaction().context.get('stock_skip_warehouse')):
                location_ids.remove(location.id)
                if location.storage_location.id not in location_ids:
                    storage_to_remove.add(location.storage_location.id)
                location_ids.add(location.storage_location.id)
                wh_to_add[location.id] = location.storage_location.id
        location_ids = list(location_ids)

        move_rule_query = Rule.domain_get('stock.move')
        if move_rule_query is None:
            move_rule_query = Literal(True)

        PeriodCache = Period.get_cache(grouping)
        period = None
        if PeriodCache:
            period_cache = PeriodCache.__table__()

        if not context.get('stock_date_end'):
            context['stock_date_end'] = datetime.date.max

        # date end in the past or today: filter on state done
        if (context['stock_date_end'] < today
                or (context['stock_date_end'] == today
                    and not context.get('forecast'))):
            state_date_clause = (
                move.state.in_(['done',
                        context.get('stock_assign') and 'assigned' or 'done'])
                & (
                    (
                        (move.effective_date == None)
                        & (move.planned_date <= context['stock_date_end'])
                        )
                    | (move.effective_date <= context['stock_date_end'])
                    )
                )
        # future date end: filter move on state done and date
        # before today, or on all state and date between today and
        # date_end.
        else:
            state_date_clause = (
                (move.state.in_(['done',
                            context.get('stock_assign') and 'assigned'
                            or 'done'])
                    & (
                        (
                            (move.effective_date == None)
                            & (move.planned_date <= today)
                            )
                        | (move.effective_date <= today)
                        )
                    )
                | (move.state.in_(['done', 'assigned', 'draft'])
                    & (
                        (
                            (move.effective_date == None)
                            & (Coalesce(move.planned_date, datetime.date.max)
                                <= context['stock_date_end'])
                            & (Coalesce(move.planned_date, datetime.date.max)
                                >= today)
                            )
                        | (
                            (move.effective_date <= context['stock_date_end'])
                            & (move.effective_date >= today)
                            )
                        )
                    )
                )

        if context.get('stock_date_start'):
            if context['stock_date_start'] > today:
                state_date_clause &= (
                    move.state.in_(['done', 'assigned', 'draft'])
                    & (
                        (
                            (move.effective_date == None)
                            & (
                                (move.planned_date >=
                                    context['stock_date_start'])
                                | (move.planned_date == None)
                                )
                            )
                        | (move.effective_date >= context['stock_date_start'])
                        )
                    )
            else:
                state_date_clause &= (
                    (
                        move.state.in_(['done', 'assigned', 'draft'])
                        & (
                            (
                                (move.effective_date == None)
                                & (
                                    (move.planned_date >= today)
                                    | (move.planned_date == None)
                                    )
                                )
                            | (move.effective_date >= today)
                            )
                        )
                    | (
                        move.state.in_(['done',
                                context.get('stock_assign') and 'assigned'
                                or 'done'])
                        & (
                            (
                                (move.effective_date == None)
                                & (
                                    (
                                        (move.planned_date >=
                                            context['stock_date_start'])
                                        & (move.planned_date < today)
                                        )
                                    | (move.planned_date == None)
                                    )
                                )
                            | (
                                (move.effective_date >=
                                    context['stock_date_start'])
                                & (move.effective_date < today)
                                )
                            )
                        )
                    )
        elif PeriodCache:
            with Transaction().set_user(0, set_context=True):
                periods = Period.search([
                        ('date', '<', context['stock_date_end']),
                        ('state', '=', 'closed'),
                        ], order=[('date', 'DESC')], limit=1)
            if periods:
                period, = periods
                state_date_clause &= (
                    Coalesce(move.effective_date, move.planned_date,
                        datetime.date.max) > period.date)

        if with_childs:
            location_query = Location.search([
                    ('parent', 'child_of', location_ids),
                    ], query=True, order=[])
        else:
            location_query = location_ids[:]

        from_ = move
        if PeriodCache:
            from_period = period_cache
        if product_ids:
            where = reduce_ids(move.product, product_ids)
            if PeriodCache:
                where_period = reduce_ids(period_cache.product, product_ids)
        else:
            where = where_period = template.active == True
            from_ = from_.join(product, condition=move.product == product.id)
            from_ = from_.join(template,
                condition=product.template == template.id)
            if PeriodCache:
                from_period = from_period.join(product,
                    condition=period_cache.product == product.id)
                from_period = from_period.join(template,
                    condition=product.template == template.id)

        if context.get('stock_destinations'):
            destinations = context.get('stock_destinations')
            dest_clause_from = move.from_location.in_(destinations)
            dest_clause_to = move.to_location.in_(destinations)

            if PeriodCache:
                dest_clause_period = period_cache.location.in_(destinations)

        else:
            dest_clause_from = dest_clause_to = dest_clause_period = \
                Literal(True)

        # The main select clause is a union between three similar subqueries.
        # One that sums incoming moves towards locations, one that sums
        # outgoing moves and one for the period cache.  UNION ALL is used
        # because we already know that there will be no duplicates.
        move_keys = [Column(move, key).as_(key) for key in grouping]
        query = from_.select(move.to_location.as_('location'),
            Sum(move.internal_quantity).as_('quantity'),
            *move_keys,
            where=state_date_clause
            & where
            & move.to_location.in_(location_query)
            & move.id.in_(move_rule_query)
            & dest_clause_from,
            group_by=[move.to_location] + move_keys)
        query = Union(query, from_.select(move.from_location.as_('location'),
                (-Sum(move.internal_quantity)).as_('quantity'),
                *move_keys,
                where=state_date_clause
                & where
                & move.from_location.in_(location_query)
                & move.id.in_(move_rule_query)
                & dest_clause_to,
                group_by=[move.from_location] + move_keys),
            all_=True)
        if PeriodCache:
            period_keys = [Column(period_cache, key).as_(key)
                for key in grouping]
            query = Union(query, from_period.select(
                    period_cache.location.as_('location'),
                    period_cache.internal_quantity.as_('quantity'),
                    *period_keys,
                    where=(period_cache.period
                        == (period.id if period else None))
                    & where_period
                    & period_cache.location.in_(location_query)
                    & dest_clause_period),
                all_=True)
        query_keys = [Column(query, key).as_(key) for key in grouping]
        columns = ([query.location.as_('location')]
            + query_keys
            + [Sum(query.quantity).as_('quantity')])
        query = query.select(*columns,
            group_by=[query.location] + query_keys)
        cursor.execute(*query)
        raw_lines = cursor.fetchall()

        product_getter = itemgetter(grouping.index('product') + 1)
        res_product_ids = set()
        res = {}
        keys = set()
        for line in raw_lines:
            location = line[0]
            key = tuple(line[1:-1])
            quantity = line[-1]
            res[(location,) + key] = quantity
            res_product_ids.add(product_getter(line))
            keys.add(key)

        # Propagate quantities on from child locations to their parents
        if with_childs:
            # Fetch all child locations
            locations = Location.search([
                    ('parent', 'child_of', location_ids),
                    ])
            # Generate a set of locations without childs and a dict
            # giving the parent of each location.
            leafs = set([l.id for l in locations])
            parent = {}
            for location in locations:
                if not location.parent:
                    continue
                if location.parent.id in leafs:
                    leafs.remove(location.parent.id)
                parent[location.id] = location.parent.id
            locations = set((l.id for l in locations))
            while leafs:
                for l in leafs:
                    locations.remove(l)
                    if l not in parent:
                        continue
                    for key in keys:
                        parent_key = (parent[l],) + key
                        res.setdefault(parent_key, 0)
                        res[parent_key] += res.get((l,) + key, 0)
                next_leafs = set(locations)
                for l in locations:
                    if l not in parent:
                        continue
                    if parent[l] in next_leafs and parent[l] in locations:
                        next_leafs.remove(parent[l])
                leafs = next_leafs

            # clean result
            for key in res.keys():
                location = key[0]
                if location not in location_ids:
                    del res[key]

        # Round quantities
        default_uom = dict((p.id, p.default_uom) for p in
            cls.browse(list(res_product_ids)))
        for key, quantity in res.iteritems():
            location = key[0]
            product = product_getter(key)
            uom = default_uom[product]
            res[key] = Uom.round(quantity, uom.rounding)

        if wh_to_add:
            for wh, storage in wh_to_add.iteritems():
                for product in product_ids:
                    if (storage, product) in res:
                        res[(wh, product)] = res[(storage, product)]
                        if storage in storage_to_remove:
                            del res[(storage, product)]

        return res


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
            & (Coalesce(move.effective_date, move.planned_date) != None),
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
    warehouse = fields.Many2One('stock.location', 'Warehouse', domain=[
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

#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
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
                    with_childs=True, skip_zero=False).iteritems()

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
            with_childs=False, skip_zero=True):
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
        If skip_zero it lists also items with zero quantity

        Return a dictionary with (location id, product id) as key
                and quantity as value.
        """
        pool = Pool()
        Uom = pool.get('product.uom')
        Rule = pool.get('ir.rule')
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        Period = pool.get('stock.period')

        today = Date.today()

        if not location_ids:
            return {}
        cursor = Transaction().cursor
        context = Transaction().context.copy()
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

        move_rule_query, move_rule_val = Rule.domain_get('stock.move')

        period_clause, period_vals = 'period = %s', [0]

        if not context.get('stock_date_end'):
            context['stock_date_end'] = datetime.date.max

        # date end in the past or today: filter on state done
        if (context['stock_date_end'] < today
                or (context['stock_date_end'] == today
                    and not context.get('forecast'))):
            state_date_clause = (
                '('
                    '(state in (%s, %s)) '
                'AND '
                    '('
                        '('
                            '(effective_date IS NULL) '
                        'AND '
                            '(planned_date <= %s) '
                        ') '
                    'OR '
                        '(effective_date <= %s)'
                    ')'
                ')')
            state_date_vals = ["done",
                    context.get('stock_assign') and 'assigned' or 'done',
                    context['stock_date_end'],
                    context['stock_date_end'],
                    ]
        # future date end: filter move on state done and date
        # before today, or on all state and date between today and
        # date_end.
        else:
            state_date_clause = (
                '('
                    '('
                        '(state in (%s, %s)) '
                    'AND '
                        '('
                            '('
                                '(effective_date IS NULL) '
                            'AND '
                                '(planned_date <= %s) '
                            ') '
                        'OR '
                            '(effective_date <= %s)'
                        ')'
                    ')'
                'OR '
                    '('
                        '(state in (%s, %s, %s)) '
                    'AND '
                        '('
                            '('
                                '(effective_date IS NULL) '
                            'AND '
                                '(planned_date <= %s) '
                            'AND '
                                '(planned_date >= %s)'
                            ')'
                        'OR '
                            '('
                                '(effective_date <= %s) '
                            'AND '
                                '(effective_date >= %s)'
                            ')'
                        ')'
                    ')'
                ')')

            state_date_vals = [
                'done', context.get('stock_assign') and 'assigned' or 'done',
                today, today,
                'done', 'assigned', 'draft',
                context['stock_date_end'], today,
                context['stock_date_end'], today,
                ]

        if context.get('stock_date_start'):
            if context['stock_date_start'] > today:
                state_date_clause += ('AND '
                    '('
                        '(state in (%s, %s, %s)) '
                    'AND '
                        '('
                            '('
                                '(effective_date IS NULL) '
                            'AND '
                                '('
                                    '(planned_date >= %s) '
                                'OR '
                                    '(planned_date IS NULL)'
                                ')'
                            ') '
                        'OR '
                            '(effective_date >= %s)'
                        ')'
                    ')')
                state_date_vals.extend(['done', 'assigned', 'draft',
                     context['stock_date_start'], context['stock_date_start']])
            else:
                state_date_clause += ('AND '
                    '('
                        '('
                            '(state in (%s, %s, %s)) '
                        'AND '
                            '('
                                '('
                                    '(effective_date IS NULL) '
                                'AND '
                                    '('
                                        '(planned_date >= %s) '
                                    'OR '
                                        '(planned_date IS NULL)'
                                    ') '
                                ')'
                            'OR '
                                '(effective_date >= %s)'
                            ')'
                        ') '
                    'OR '
                        '('
                            '(state in (%s, %s)) '
                        'AND '
                            '('
                                '('
                                    '(effective_date IS NULL) '
                                'AND '
                                    '('
                                        '('
                                            '(planned_date >= %s) '
                                        'AND '
                                            '(planned_date < %s)'
                                        ') '
                                    'OR '
                                        '(planned_date IS NULL)'
                                    ')'
                                ') '
                            'OR '
                                '('
                                    '(effective_date >= %s) '
                                'AND '
                                    '(effective_date < %s)'
                                ')'
                            ')'
                        ')'
                    ')')

                state_date_vals.extend(['done', 'assigned', 'draft',
                    today, today,
                    'done',
                    context.get('stock_assign') and 'assigned' or 'done',
                    context['stock_date_start'], today,
                    context['stock_date_start'], today,
                    ])
        else:
            periods = Period.search([
                    ('date', '<', context['stock_date_end']),
                    ], order=[('date', 'DESC')], limit=1)
            if periods:
                period, = periods
                state_date_clause += (' AND '
                    '(COALESCE(effective_date, planned_date) > %s)')
                state_date_vals.append(period.date)
                period_vals[0] = period.id

        if with_childs:
            query, args = Location.search([
                    ('parent', 'child_of', location_ids),
                    ], query_string=True, order=[])
            where_clause = " IN (" + query + ") "
            where_vals = args
        else:
            where_clause = " IN (" + \
                ",".join(('%s',) * len(location_ids)) + ") "
            where_vals = location_ids[:]

        if move_rule_query:
            move_rule_query = " AND " + move_rule_query + " "

        product_template_join = ""
        product_template_join_period = ""
        if product_ids:
            red_clause, red_vals = reduce_ids('product', product_ids)
            where_clause += "AND " + red_clause
            where_vals += red_vals
        else:
            where_clause += "AND product_template.active = %s"
            where_vals.append(True)
            product_template_join = (
                "JOIN product_product "
                    "ON (stock_move.product = product_product.id) "
                "JOIN product_template "
                    "ON (product_product.template = "
                        "product_template.id) ")
            product_template_join_period = (
                "JOIN product_product "
                    "ON (stock_period_cache.product = product_product.id) "
                "JOIN product_template "
                    "ON (product_product.template = product_template.id) ")

        if context.get('stock_destinations'):
            destinations = context.get('stock_destinations')
            dest_clause_from = " AND from_location in ("
            dest_clause_from += ",".join(('%s',) * len(destinations))
            dest_clause_from += ") "
            dest_clause_to = " AND to_location in ("
            dest_clause_to += ",".join(('%s',) * len(destinations))
            dest_clause_to += ") "
            dest_vals = destinations

            dest_clause_period = (' AND location IN ('
                + ','.join(('%s',) * len(destinations)) + ') ')

        else:
            dest_clause_from = dest_clause_to = dest_clause_period = ""
            dest_vals = []

        # The main select clause is a union between three similar subqueries.
        # One that sums incoming moves towards locations, one that sums
        # outgoing moves and one for the period cache.  UNION ALL is used
        # because we already know that there will be no duplicates.
        select_clause = (
                "SELECT location, product, sum(quantity) AS quantity "
                "FROM ( "
                    "SELECT to_location AS location, product, "
                        "SUM(internal_quantity) AS quantity "
                    "FROM stock_move " + product_template_join + " "
                    "WHERE (%s) "
                        "AND to_location %s "
                    "GROUP BY to_location, product "
                    "UNION ALL "
                    "SELECT from_location AS location, product, "
                        "-SUM(internal_quantity) AS quantity "
                    "FROM stock_move " + product_template_join + " "
                    "WHERE (%s) "
                        "AND from_location %s "
                    "GROUP BY from_location, product, uom "
                    "UNION ALL "
                    "SELECT location, product, internal_quantity AS quantity "
                    "FROM stock_period_cache "
                        + product_template_join_period + " "
                    "WHERE (%s) "
                        "AND location %s "
                ") AS T GROUP BY T.location, T.product")

        cursor.execute(select_clause % (
            state_date_clause,
            where_clause + move_rule_query + dest_clause_from,
            state_date_clause,
            where_clause + move_rule_query + dest_clause_to,
            period_clause, where_clause + dest_clause_period),
            state_date_vals + where_vals + move_rule_val + dest_vals +
            state_date_vals + where_vals + move_rule_val + dest_vals +
            period_vals + where_vals + dest_vals)
        raw_lines = cursor.fetchall()

        res_product_ids = set(product for _, product, _ in raw_lines)
        res = dict(((location, product), quantity)
                for location, product, quantity in raw_lines)

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
                    for product in res_product_ids:
                        res.setdefault((parent[l], product), 0)
                        res[(parent[l], product)] += res.get((l, product), 0)
                next_leafs = set(locations)
                for l in locations:
                    if l not in parent:
                        continue
                    if parent[l] in next_leafs and parent[l] in locations:
                        next_leafs.remove(parent[l])
                leafs = next_leafs

            # clean result
            for location, product in res.keys():
                if location not in location_ids:
                    del res[(location, product)]

        # Round quantities
        default_uom = dict((p.id, p.default_uom) for p in
            cls.browse(list(res_product_ids)))
        for key, quantity in res.iteritems():
            location, product = key
            uom = default_uom[product]
            res[key] = Uom.round(quantity, uom.rounding)

        # Complete result with missing products if asked
        if not skip_zero:
            # Search for all products, even if not linked with moves
            if product_ids:
                all_product_ids = product_ids
            else:
                all_product_ids = cls.search([])
            keys = ((l, p) for l in location_ids for p in all_product_ids)
            for location_id, product_id in keys:
                if (location_id, product_id) not in res:
                    res[(location_id, product_id)] = 0.0

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

        product_id = Transaction().context.get('product')
        warehouse_id = Transaction().context.get('warehouse', -1)
        warehouse_clause, warehouse_params = Location.search([
                ('parent', 'child_of', [warehouse_id]),
                ], query_string=True, order=[])
        return ('SELECT MAX(id) AS id, '
                '0 AS create_uid, '
                'NOW() AS create_date, '
                'NULL AS write_uid, '
                'NULL AS write_date, '
                'COALESCE(effective_date, planned_date) AS date '
            'FROM "' + Move._table + '" '
            'WHERE product = %s '
                'AND (from_location IN (' + warehouse_clause + ') '
                    'OR to_location IN (' + warehouse_clause + ')) '
                'AND COALESCE(effective_date, planned_date) IS NOT NULL '
            'GROUP BY date, product', [product_id] + 2 * warehouse_params)

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
                    [warehouse_id], [product_id], with_childs=True,
                    skip_zero=False)[(warehouse_id, product_id)]
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

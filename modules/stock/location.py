# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import operator
from decimal import Decimal

from sql import Column

from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, MatchMixin, Model, ModelSQL, ModelView, fields,
    sequence_ordered, tree)
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool
from trytond.pyson import Eval, If, TimeDelta
from trytond.tools import grouped_slice
from trytond.transaction import (
    Transaction, inactive_records, without_check_access)

from .exceptions import LocationValidationError


class WarehouseWasteLocation(ModelSQL):
    "Warehouse Waste Location"
    __name__ = 'stock.location.waste'

    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True, ondelete='CASCADE',
        domain=[('type', '=', 'warehouse')])
    location = fields.Many2One(
        'stock.location', "Waste Location", required=True, ondelete='CASCADE',
        domain=[('type', '=', 'lost_found')])


class Location(DeactivableMixin, tree(), ModelSQL, ModelView):
    "Stock Location"
    __name__ = 'stock.location'
    _default_warehouse_cache = Cache('stock.location.default_warehouse',
        context=False)

    name = fields.Char("Name", size=None, required=True, translate=True)
    code = fields.Char(
        "Code",
        help="The internal identifier used for the location.")
    address = fields.Many2One(
        'party.address', "Address",
        states={
            'invisible': Eval('type') != 'warehouse',
            })
    type = fields.Selection([
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('lost_found', 'Lost and Found'),
        ('warehouse', 'Warehouse'),
        ('storage', 'Storage'),
        ('production', 'Production'),
        ('drop', 'Drop'),
        ('view', 'View'),
        ], "Type")
    type_string = type.translated('type')
    parent = fields.Many2One(
        "stock.location", "Parent", ondelete='CASCADE',
        left="left", right="right",
        help="Used to add structure above the location.")
    left = fields.Integer('Left', required=True)
    right = fields.Integer('Right', required=True)
    childs = fields.One2Many("stock.location", "parent", "Children",
        help="Used to add structure below the location.")
    flat_childs = fields.Boolean(
        "Flat Children",
        help="Check to enforce a single level of children with no "
        "grandchildren.")
    warehouse = fields.Function(fields.Many2One('stock.location', 'Warehouse'),
        'get_warehouse')
    input_location = fields.Many2One(
        "stock.location", "Input", states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
            },
        domain=[
            ['OR',
                ('type', '=', 'storage'),
                ('id', '=', Eval('storage_location', -1)),
                ],
            ['OR',
                ('parent', 'child_of', [Eval('id', -1)]),
                ('parent', '=', None),
                ],
            ],
        help="Where incoming stock is received.")
    output_location = fields.Many2One(
        "stock.location", "Output", states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
        },
        domain=[
            ['OR',
                ('type', '=', 'storage'),
                ('id', '=', Eval('storage_location', -1)),
                ],
            ['OR',
                ('parent', 'child_of', [Eval('id', -1)]),
                ('parent', '=', None)]],
        help="Where outgoing stock is sent from.")
    storage_location = fields.Many2One(
        "stock.location", "Storage", states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
        },
        domain=[
            ('type', 'in', ['storage', 'view']),
            ['OR',
                ('parent', 'child_of', [Eval('id', -1)]),
                ('parent', '=', None)]],
        help="The top level location where stock is stored.")
    picking_location = fields.Many2One(
        'stock.location', 'Picking', states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('storage_location', -1)]),
            ],
        help="Where stock is picked from.\n"
        "Leave empty to use the storage location.")
    lost_found_location = fields.Many2One(
        'stock.location', "Lost and Found",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'lost_found'),
            ],
        help="Used, by inventories, when correcting stock levels "
        "in the warehouse.")
    waste_locations = fields.Many2Many(
        'stock.location.waste', 'warehouse', 'location', "Waste Locations",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'lost_found'),
            ],
        help="The locations used for waste products from the warehouse.")
    waste_warehouses = fields.Many2Many(
        'stock.location.waste', 'location', 'warehouse', "Waste Warehouses",
        states={
            'invisible': Eval('type') != 'lost_found',
            },
        domain=[
            ('type', '=', 'warehouse'),
            ],
        help="The warehouses that use the location for waste products.")

    allow_pickup = fields.Boolean(
        "Allow Pickup",
        states={
            'invisible': (
                (Eval('type') != 'warehouse')
                & ~Eval('address')),
            })

    quantity = fields.Function(
        fields.Float(
            "Quantity", digits='quantity_uom',
            help="The amount of stock in the location."),
        'get_quantity', searcher='search_quantity')
    forecast_quantity = fields.Function(
        fields.Float(
            "Forecast Quantity", digits='quantity_uom',
            help="The amount of stock expected to be in the location."),
        'get_quantity', searcher='search_quantity')
    quantity_uom = fields.Function(fields.Many2One(
            'product.uom', "Quantity UoM",
            help="The Unit of Measure for the quantities."),
        'get_quantity_uom')
    cost_value = fields.Function(fields.Numeric(
            "Cost Value", digits=price_digits,
            help="The value of the stock in the location."),
        'get_cost_value')

    @classmethod
    def __setup__(cls):
        cls.code.search_unaccented = False
        super(Location, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.code, Index.Similarity())),
                Index(
                    t,
                    (t.left, Index.Range(cardinality='high')),
                    (t.right, Index.Range(cardinality='high'))),
                })
        cls._order.insert(0, ('name', 'ASC'))

        parent_domain = [
            ['OR',
                ('parent.flat_childs', '=', False),
                ('parent', '=', None),
                ]
            ]
        childs_domain = [
            If(Eval('flat_childs', False),
                ('childs', '=', None),
                ()),
            ]
        childs_mapping = cls._childs_domain()
        for type_, allowed_parents in cls._parent_domain().items():
            parent_domain.append(If(Eval('type') == type_,
                    ('type', 'in', allowed_parents), ()))
            childs_domain.append(If(Eval('type') == type_,
                    ('type', 'in', childs_mapping[type_]), ()))
        cls.parent.domain = parent_domain
        cls.childs.domain = childs_domain

    @classmethod
    def _parent_domain(cls):
        '''Returns a dict with location types as keys and a list of allowed
        parent location types as values'''
        return {
            'customer': ['customer'],
            'supplier': ['supplier'],
            'production': ['production'],
            'lost_found': ['lost_found'],
            'view': ['warehouse', 'view', 'storage'],
            'storage': ['warehouse', 'view', 'storage'],
            'warehouse': ['view'],
            }

    @classmethod
    def _childs_domain(cls):
        childs_domain = {}
        for type_, allowed_parents in cls._parent_domain().items():
            for parent in allowed_parents:
                childs_domain.setdefault(parent, [])
                childs_domain[parent].append(type_)
        return childs_domain

    @classmethod
    def validate_fields(cls, locations, field_names):
        super().validate_fields(locations, field_names)
        inactives = []
        for location in locations:
            location.check_type_for_moves(field_names)
            if 'active' in field_names and not location.active:
                inactives.append(location)
        cls.check_inactive(inactives)

    def check_type_for_moves(self, field_names=None):
        """ Check locations with moves have types compatible with moves. """
        pool = Pool()
        Move = pool.get('stock.move')
        if field_names and 'type' not in field_names:
            return
        invalid_move_types = ['warehouse', 'view']
        if self.type in invalid_move_types:
            moves = Move.search([
                    ['OR',
                        ('to_location', '=', self.id),
                        ('from_location', '=', self.id),
                        ],
                    ('state', 'not in', ['staging', 'draft']),
                    ],
                order=[], limit=1)
            if moves:
                raise LocationValidationError(
                    gettext('stock.msg_location_invalid_type_for_moves',
                        location=self.rec_name,
                        type=self.type_string))

    @classmethod
    def check_inactive(cls, locations):
        "Check inactive location are empty"
        assert all(not l.active for l in locations)
        empty = cls.get_empty_locations(locations)
        non_empty = set(locations) - set(empty)
        if non_empty:
            raise LocationValidationError(
                gettext('stock.msg_location_inactive_not_empty',
                    location=next(iter(non_empty)).rec_name))

    @classmethod
    def get_empty_locations(cls, locations=None):
        pool = Pool()
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        if locations is None:
            locations = cls.search([])
        if not locations:
            return []
        location_ids = list(map(int, locations))
        with without_check_access(), inactive_records():
            query = Move.compute_quantities_query(
                location_ids, with_childs=True)
            quantities = Move.compute_quantities(
                query, location_ids, with_childs=True)
            empty = set(location_ids)
            product_ids = [q[1] for q in quantities.keys()]
            consumables = {
                p.id for p in Product.browse(product_ids) if p.consumable}
            for (location_id, product), quantity in quantities.items():
                if quantity and product not in consumables:
                    empty.discard(location_id)
            for sub_ids in grouped_slice(list(empty)):
                sub_ids = list(sub_ids)
                moves = Move.search([
                        ('state', 'not in', ['done', 'cancelled']),
                        ['OR',
                            ('from_location', 'in', sub_ids),
                            ('to_location', 'in', sub_ids),
                            ],
                        ])
                for move in moves:
                    for location in [move.from_location, move.to_location]:
                        empty.discard(location.id)
        return cls.browse(empty)

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0

    @classmethod
    def default_flat_childs(cls):
        return False

    @staticmethod
    def default_type():
        return 'storage'

    @classmethod
    def check_xml_record(cls, records, values):
        pass

    def get_warehouse(self, name):
        # Order by descending left to get the first one in the tree
        with inactive_records():
            locations = self.search([
                    ('parent', 'parent_of', [self.id]),
                    ('type', '=', 'warehouse'),
                    ], order=[('left', 'DESC')])
        if locations:
            return locations[0].id

    @classmethod
    def get_default_warehouse(cls):
        warehouse = Transaction().context.get('warehouse')
        if warehouse:
            return warehouse

        warehouse = cls._default_warehouse_cache.get(None, -1)
        if warehouse == -1:
            warehouses = cls.search([
                    ('type', '=', 'warehouse'),
                    ], limit=2)
            if len(warehouses) == 1:
                warehouse = warehouses[0].id
            else:
                warehouse = None
            cls._default_warehouse_cache.set(None, warehouse)
        return warehouse

    @property
    def lost_found_used(self):
        if self.warehouse:
            return self.warehouse.lost_found_location

    def get_rec_name(self, name):
        if self.code:
            return f'[{self.code}] {self.name}'
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            (cls._rec_name,) + tuple(clause[1:]),
            ('code',) + tuple(clause[1:]),
            ]

    @classmethod
    def _get_quantity_grouping(cls):
        context = Transaction().context
        grouping, grouping_filter, key = (), (), []
        if context.get('product') is not None:
            grouping = ('product',)
            grouping_filter = ([context['product']],)
            key = (context['product'],)
        elif context.get('product_template') is not None:
            grouping = ('product.template',)
            grouping_filter = ([context['product_template']],)
            key = (context['product_template'],)
        return grouping, grouping_filter, key

    @classmethod
    def get_quantity(cls, locations, name):
        pool = Pool()
        Product = pool.get('product.product')
        Date_ = pool.get('ir.date')
        trans_context = Transaction().context

        def valid_context(name):
            return (trans_context.get(name) is not None
                and isinstance(trans_context[name], int))

        context = {}
        if (name == 'quantity'
                and ((trans_context.get('stock_date_end') or datetime.date.max)
                    > Date_.today())):
            context['stock_date_end'] = Date_.today()

        if name == 'forecast_quantity':
            context['forecast'] = True
            if not trans_context.get('stock_date_end'):
                context['stock_date_end'] = datetime.date.max

        grouping, grouping_filter, key = cls._get_quantity_grouping()
        if not grouping:
            return {loc.id: None for loc in locations}

        pbl = {}
        for sub_locations in grouped_slice(locations):
            location_ids = [l.id for l in sub_locations]
            with Transaction().set_context(context):
                pbl.update(Product.products_by_location(
                        location_ids,
                        grouping=grouping,
                        grouping_filter=grouping_filter,
                        with_childs=trans_context.get('with_childs', True)))

        return dict((loc.id, pbl.get((loc.id,) + key, 0)) for loc in locations)

    @classmethod
    def search_quantity(cls, name, domain):
        _, operator_, operand = domain
        operator_ = {
            '=': operator.eq,
            '>=': operator.ge,
            '>': operator.gt,
            '<=': operator.le,
            '<': operator.lt,
            '!=': operator.ne,
            'in': lambda v, l: v in l,
            'not in': lambda v, l: v not in l,
            }.get(operator_, lambda v, l: False)

        ids = []
        for location in cls.search([]):
            if operator_(getattr(location, name), operand):
                ids.append(location.id)
        return [('id', 'in', ids)]

    @classmethod
    def get_quantity_uom(cls, locations, name):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        context = Transaction().context
        value = None
        uom = None
        if context.get('product') is not None:
            product = Product(context['product'])
            uom = product.default_uom
        elif context.get('product_template') is not None:
            template = Template(context['product_template'])
            uom = template.default_uom
        if uom:
            value = uom.id
        return {l.id: value for l in locations}

    @classmethod
    def get_cost_value(cls, locations, name):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        trans_context = Transaction().context
        cost_values = {l.id: None for l in locations}

        def valid_context(name):
            return (trans_context.get(name) is not None
                and isinstance(trans_context[name], int))

        if not any(map(valid_context, ['product', 'product_template'])):
            return cost_values

        def get_record():
            if trans_context.get('product') is not None:
                return Product(trans_context['product'])
            else:
                return Template(trans_context['product_template'])

        context = {}
        if trans_context.get('stock_date_end') is not None:
            # Use the last cost_price of the day
            context['_datetime'] = datetime.datetime.combine(
                trans_context['stock_date_end'], datetime.time.max)
            # The date could be before the product creation
            record = get_record()
            if record.create_date > context['_datetime']:
                return cost_values
        with Transaction().set_context(context):
            cost_price = get_record().cost_price
        # The template may have more than one product
        if cost_price is not None:
            for location in locations:
                cost_values[location.id] = round_price(
                    Decimal(str(location.quantity)) * cost_price)
        return cost_values

    @classmethod
    def _set_warehouse_parent(cls, locations):
        '''
        Set the parent of child location of warehouse if not set
        '''
        to_update = set()
        to_save = []
        for location in locations:
            if location.type == 'warehouse':
                if not location.input_location.parent:
                    to_update.add(location.input_location)
                if not location.output_location.parent:
                    to_update.add(location.output_location)
                if not location.storage_location.parent:
                    to_update.add(location.storage_location)
                if to_update:
                    for child_location in to_update:
                        child_location.parent = location
                        to_save.append(child_location)
                    to_update.clear()
        cls.save(to_save)

    @classmethod
    def create(cls, vlist):
        locations = super(Location, cls).create(vlist)
        cls._set_warehouse_parent(locations)
        cls._default_warehouse_cache.clear()
        return locations

    @classmethod
    def write(cls, *args):
        super(Location, cls).write(*args)
        locations = sum(args[::2], [])
        cls._set_warehouse_parent(locations)
        cls._default_warehouse_cache.clear()

        ids = [l.id for l in locations]
        warehouses = cls.search([
                ('type', '=', 'warehouse'),
                ['OR',
                    ('storage_location', 'in', ids),
                    ('input_location', 'in', ids),
                    ('output_location', 'in', ids),
                    ]])

        fields = ('storage_location', 'input_location', 'output_location')
        wh2childs = {}
        for warehouse in warehouses:
            in_out_sto = (getattr(warehouse, f).id for f in fields)
            for location in locations:
                if location.id not in in_out_sto:
                    continue
                childs = wh2childs.setdefault(warehouse.id, cls.search([
                            ('parent', 'child_of', warehouse.id),
                            ]))
                if location not in childs:
                    raise LocationValidationError(
                        gettext('stock.msg_location_child_of_warehouse',
                            location=location.rec_name,
                            warehouse=warehouse.rec_name))

    @classmethod
    def delete(cls, locations):
        # Delete also required children as CASCADING is done separately
        extra_locations = []
        for location in locations:
            extra_locations.extend(filter(None, [
                        location.input_location,
                        location.output_location,
                        location.storage_location,
                        ]))
        super().delete(locations + extra_locations)
        cls._default_warehouse_cache.clear()

    @classmethod
    def copy(cls, locations, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        res = []
        for location in locations:
            if location.type == 'warehouse':

                wh_default = default.copy()
                wh_default['type'] = 'view'
                wh_default['input_location'] = None
                wh_default['output_location'] = None
                wh_default['storage_location'] = None
                wh_default['childs'] = None

                new_location, = super(Location, cls).copy([location],
                    default=wh_default)

                with Transaction().set_context(
                        cp_warehouse_locations={
                            'input_location': location.input_location.id,
                            'output_location': location.output_location.id,
                            'storage_location': location.storage_location.id,
                            },
                        cp_warehouse_id=new_location.id):
                    cls.copy(location.childs,
                        default={'parent': new_location.id})
                cls.write([new_location], {
                        'type': 'warehouse',
                        })
            else:
                new_location, = super(Location, cls).copy([location],
                    default=default)
                warehouse_locations = Transaction().context.get(
                    'cp_warehouse_locations') or {}
                if location.id in warehouse_locations.values():
                    cp_warehouse = cls(
                        Transaction().context['cp_warehouse_id'])
                    for field, loc_id in warehouse_locations.items():
                        if loc_id == location.id:
                            cls.write([cp_warehouse], {
                                    field: new_location.id,
                                    })

            res.append(new_location)
        return res

    @classmethod
    def view_attributes(cls):
        storage_types = Eval('type').in_(['storage', 'warehouse', 'view'])
        return super().view_attributes() + [
            ('/tree/field[@name="quantity"]',
                'visual', If(
                    storage_types & (Eval('quantity', 0) < 0), 'danger', ''),
                ['type']),
            ('/tree/field[@name="forecast_quantity"]',
                'visual', If(
                    storage_types & (Eval('forecast_quantity', 0) < 0),
                    'warning', ''),
                ['type']),
            ]


class ProductsByLocationsContext(ModelView):
    'Products by Locations'
    __name__ = 'stock.products_by_locations.context'

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
        Date_ = Pool().get('ir.date')
        return Date_.today()

    @fields.depends('forecast_date')
    def on_change_with_stock_date_end(self, name=None):
        if self.forecast_date is None:
            return datetime.date.max
        return self.forecast_date


class ProductsByLocations(DeactivableMixin, ModelSQL, ModelView):
    "Products by Locations"
    __name__ = 'stock.products_by_locations'

    product = fields.Many2One('product.product', "Product")
    quantity = fields.Function(
        fields.Float("Quantity", digits='default_uom'),
        'get_product', searcher='search_product')
    forecast_quantity = fields.Function(
        fields.Float("Forecast Quantity", digits='default_uom'),
        'get_product', searcher='search_product')
    default_uom = fields.Function(
        fields.Many2One(
            'product.uom', "Default UoM",
            help="The default Unit of Measure."),
        'get_product', searcher='search_product')
    cost_value = fields.Function(
        fields.Numeric("Cost Value"), 'get_product')
    consumable = fields.Function(
        fields.Boolean("Consumable"), 'get_product',
        searcher='search_product')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Product = pool.get('product.product')
        product = Product.__table__()
        columns = []
        for fname, field in cls._fields.items():
            if not hasattr(field, 'set'):
                if (isinstance(field, fields.Many2One)
                        and field.get_target() == Product):
                    column = Column(product, 'id')
                else:
                    column = Column(product, fname)
                columns.append(column.as_(fname))
        return product.select(*columns)

    def get_rec_name(self, name):
        return self.product.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name',) + tuple(clause[1:])]

    def get_product(self, name):
        value = getattr(self.product, name)
        if isinstance(value, Model):
            value = value.id
        return value

    @classmethod
    def search_product(cls, name, clause):
        nested = clause[0][len(name):]
        return [('product.' + name + nested, *clause[1:])]


class LocationLeadTime(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Location Lead Time'
    __name__ = 'stock.location.lead_time'

    warehouse_from = fields.Many2One('stock.location', 'Warehouse From',
        ondelete='CASCADE',
        domain=[
            ('type', '=', 'warehouse'),
            ('id', '!=', Eval('warehouse_to', -1)),
            ])
    warehouse_to = fields.Many2One('stock.location', 'Warehouse To',
        ondelete='CASCADE',
        domain=[
            ('type', '=', 'warehouse'),
            ('id', '!=', Eval('warehouse_from', -1)),
            ])
    lead_time = fields.TimeDelta(
        "Lead Time",
        domain=['OR',
            ('lead_time', '=', None),
            ('lead_time', '>=', TimeDelta()),
            ],
        help="The time it takes to move stock between the warehouses.")

    @classmethod
    def get_lead_time(cls, pattern):
        for record in cls.search([]):
            if record.match(pattern):
                return record.lead_time

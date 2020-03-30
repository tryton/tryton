# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import operator
from decimal import Decimal

from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, MatchMixin, ValueMixin, DeactivableMixin, fields,
    sequence_ordered, tree)
from trytond import backend
from trytond.cache import Cache
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice
from trytond.tools.multivalue import migrate_property

from .exceptions import LocationValidationError


class Location(DeactivableMixin, tree(), ModelSQL, ModelView):
    "Stock Location"
    __name__ = 'stock.location'
    _default_warehouse_cache = Cache('stock.location.default_warehouse',
        context=False)

    name = fields.Char("Name", size=None, required=True, translate=True)
    code = fields.Char(
        "Code", size=None, select=True,
        help="The internal identifier used for the location.")
    address = fields.Many2One(
        'party.address', "Address",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        depends=['type'])
    type = fields.Selection([
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('lost_found', 'Lost and Found'),
        ('warehouse', 'Warehouse'),
        ('storage', 'Storage'),
        ('production', 'Production'),
        ('drop', 'Drop'),
        ('view', 'View'),
        ], "Location type")
    type_string = type.translated('type')
    parent = fields.Many2One("stock.location", "Parent", select=True,
        left="left", right="right",
        states={
            'invisible': Eval('type') == 'warehouse',
            },
        depends=['type'],
        help="Used to add structure above the location.")
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
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
            ('type', '=', 'storage'),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', None),
                ],
            ],
        depends=['type', 'id'],
        help="Where incoming stock is received.")
    output_location = fields.Many2One(
        "stock.location", "Output", states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
        },
        domain=[
            ('type', '=', 'storage'),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', None)]],
        depends=['type', 'id'],
        help="Where outgoing stock is sent from.")
    storage_location = fields.Many2One(
        "stock.location", "Storage", states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
        },
        domain=[
            ('type', 'in', ['storage', 'view']),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', None)]],
        depends=['type', 'id'],
        help="The top level location where stock is stored.")
    picking_location = fields.Many2One(
        'stock.location', 'Picking', states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('storage_location', -1)]),
            ],
        depends=['type', 'storage_location'],
        help="Where stock is picked from.\n"
        "Leave empty to use the storage location.")
    lost_found_location = fields.Many2One(
        'stock.location', "Lost and Found",
        states={
            'invisible': Eval('type') != 'warehouse',
            'readonly': ~Eval('active'),
            },
        domain=[
            ('type', '=', 'lost_found'),
            ],
        depends=['type', 'active'],
        help="Used, by inventories, when correcting stock levels "
        "in the warehouse.")
    quantity = fields.Function(
        fields.Float('Quantity',
        help="The amount of stock in the location."),
        'get_quantity', searcher='search_quantity')
    forecast_quantity = fields.Function(
        fields.Float('Forecast Quantity',
        help="The amount of stock expected to be in the location."),
        'get_quantity', searcher='search_quantity')
    cost_value = fields.Function(fields.Numeric('Cost Value',
        help="The value of the stock in the location."),
        'get_cost_value')

    @classmethod
    def __setup__(cls):
        super(Location, cls).__setup__()
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
        cls.childs.depends.extend(['flat_childs', 'type'])

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
            'warehouse': [''],
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
    def __register__(cls, module_name):
        super(Location, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)
        table.index_action(['left', 'right'], 'add')

    @classmethod
    def validate(cls, locations):
        super(Location, cls).validate(locations)
        inactives = []
        for location in locations:
            location.check_type_for_moves()
            if not location.active:
                inactives.append(location)
        cls.check_inactive(inactives)

    def check_type_for_moves(self):
        """ Check locations with moves have types compatible with moves. """
        invalid_move_types = ['warehouse', 'view']
        Move = Pool().get('stock.move')
        if self.type in invalid_move_types:
            # Use root to compute for all companies
            with Transaction().set_user(0):
                moves = Move.search([
                        ['OR',
                            ('to_location', '=', self.id),
                            ('from_location', '=', self.id),
                            ],
                        ('state', 'not in', ['staging', 'draft']),
                        ])
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
        if locations is None:
            locations = cls.search([])
        if not locations:
            return []
        location_ids = list(map(int, locations))
        # Use root to compute for all companies
        # and ensures inactive locations are in the query
        with Transaction().set_user(0), \
                Transaction().set_context(active_test=False):
            query = Move.compute_quantities_query(
                location_ids, with_childs=True)
            quantities = Move.compute_quantities(
                query, location_ids, with_childs=True)
            empty = set(location_ids)
            for (location_id, product), quantity in quantities.items():
                if quantity:
                    empty.discard(location_id)
            for sub_ids in grouped_slice(list(empty)):
                sub_ids = list(sub_ids)
                moves = Move.search([
                        ('state', 'not in', ['done', 'cancel']),
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
        return True

    def get_warehouse(self, name):
        # Order by descending left to get the first one in the tree
        with Transaction().set_context(active_test=False):
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
    def get_quantity(cls, locations, name):
        pool = Pool()
        Product = pool.get('product.product')
        Date_ = pool.get('ir.date')
        trans_context = Transaction().context

        def valid_context(name):
            return (trans_context.get(name) is not None
                and isinstance(trans_context[name], int))

        if not any(map(valid_context, ['product', 'product_template'])):
            return {l.id: None for l in locations}

        context = {}
        if (name == 'quantity'
                and (trans_context.get('stock_date_end', datetime.date.max)
                    > Date_.today())):
            context['stock_date_end'] = Date_.today()

        if name == 'forecast_quantity':
            context['forecast'] = True
            if not trans_context.get('stock_date_end'):
                context['stock_date_end'] = datetime.date.max

        if trans_context.get('product') is not None:
            grouping = ('product',)
            grouping_filter = ([trans_context['product']],)
            key = trans_context['product']
        else:
            grouping = ('product.template',)
            grouping_filter = ([trans_context['product_template']],)
            key = trans_context['product_template']
        pbl = {}
        for sub_locations in grouped_slice(locations):
            location_ids = [l.id for l in sub_locations]
            with Transaction().set_context(context):
                pbl.update(Product.products_by_location(
                        location_ids,
                        grouping=grouping,
                        grouping_filter=grouping_filter,
                        with_childs=trans_context.get('with_childs', True)))

        return dict((loc.id, pbl.get((loc.id, key), 0)) for loc in locations)

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
        if 'stock_date_end' in trans_context:
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
                cost_values[location.id] = (
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
    def delete(cls, *args):
        super().delete(*args)
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


supplier_location = fields.Many2One(
    'stock.location', "Supplier Location", domain=[('type', '=', 'supplier')],
    help="The default source location for stock received from the party.")
customer_location = fields.Many2One(
    'stock.location', "Customer Location", domain=[('type', '=', 'customer')],
    help="The default destination location for stock sent to the party.")


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    supplier_location = fields.MultiValue(supplier_location)
    customer_location = fields.MultiValue(customer_location)
    locations = fields.One2Many(
        'party.party.location', 'party', "Locations")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'supplier_location', 'customer_location'}:
            return pool.get('party.party.location')
        return super(Party, cls).multivalue_model(field)

    @classmethod
    def default_supplier_location(cls, **pattern):
        return cls.multivalue_model(
            'supplier_location').default_supplier_location()

    @classmethod
    def default_customer_location(cls, **pattern):
        return cls.multivalue_model(
            'customer_location').default_customer_location()


class PartyLocation(ModelSQL, ValueMixin):
    "Party Location"
    __name__ = 'party.party.location'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    supplier_location = supplier_location
    customer_location = customer_location

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(PartyLocation, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(['supplier_location', 'customer_location'])
        value_names.extend(['supplier_location', 'customer_location'])
        migrate_property(
            'party.party', field_names, cls, value_names,
            parent='party', fields=fields)

    @classmethod
    def default_supplier_location(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock', 'location_supplier')
        except KeyError:
            return None

    @classmethod
    def default_customer_location(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock', 'location_customer')
        except KeyError:
            return None


class ProductsByLocationsContext(ModelView):
    'Products by Locations'
    __name__ = 'stock.products_by_locations.context'
    forecast_date = fields.Date(
        'At Date',
        help="The date for which the stock quantity is calculated.\n"
        "* An empty value calculates as far ahead as possible.\n"
        "* A date in the past will provide historical values.")
    stock_date_end = fields.Function(fields.Date('At Date'),
        'on_change_with_stock_date_end')

    @staticmethod
    def default_forecast_date():
        Date_ = Pool().get('ir.date')
        return Date_.today()

    @fields.depends('forecast_date')
    def on_change_with_stock_date_end(self, name=None):
        if self.forecast_date is None:
            return datetime.date.max
        return self.forecast_date


class LocationLeadTime(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Location Lead Time'
    __name__ = 'stock.location.lead_time'

    warehouse_from = fields.Many2One('stock.location', 'Warehouse From',
        ondelete='CASCADE',
        domain=[
            ('type', '=', 'warehouse'),
            ])
    warehouse_to = fields.Many2One('stock.location', 'Warehouse To',
        ondelete='CASCADE',
        domain=[
            ('type', '=', 'warehouse'),
            ])
    lead_time = fields.TimeDelta('Lead Time',
        help="The time it takes to move stock between the warehouses.")

    @classmethod
    def get_lead_time(cls, pattern):
        for record in cls.search([]):
            if record.match(pattern):
                return record.lead_time

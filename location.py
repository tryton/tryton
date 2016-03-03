# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond import backend
from trytond.pyson import Eval, PYSONEncoder, Date, If
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice

__all__ = ['Location', 'Party', 'ProductsByLocationsStart',
    'ProductsByLocations']

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']


class Location(ModelSQL, ModelView):
    "Stock Location"
    __name__ = 'stock.location'
    name = fields.Char("Name", size=None, required=True, states=STATES,
        depends=DEPENDS, translate=True)
    code = fields.Char("Code", size=None, states=STATES, depends=DEPENDS,
        select=True)
    active = fields.Boolean('Active', select=True)
    address = fields.Many2One("party.address", "Address",
        states={
            'invisible': Eval('type') != 'warehouse',
            'readonly': ~Eval('active'),
            },
        depends=['type', 'active'])
    type = fields.Selection([
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('lost_found', 'Lost and Found'),
        ('warehouse', 'Warehouse'),
        ('storage', 'Storage'),
        ('production', 'Production'),
        ('drop', 'Drop'),
        ('view', 'View'),
        ], 'Location type', states=STATES, depends=DEPENDS)
    parent = fields.Many2One("stock.location", "Parent", select=True,
        left="left", right="right",
        states={
            'invisible': Eval('type') == 'warehouse',
            },
        depends=['type'])
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    childs = fields.One2Many("stock.location", "parent", "Children")
    warehouse = fields.Function(fields.Many2One('stock.location', 'Warehouse'),
        'get_warehouse')
    input_location = fields.Many2One(
        "stock.location", "Input", states={
            'invisible': Eval('type') != 'warehouse',
            'readonly': ~Eval('active'),
            'required': Eval('type') == 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', None),
                ],
            ],
        depends=['type', 'active', 'id'])
    output_location = fields.Many2One(
        "stock.location", "Output", states={
            'invisible': Eval('type') != 'warehouse',
            'readonly': ~Eval('active'),
            'required': Eval('type') == 'warehouse',
        },
        domain=[
            ('type', '=', 'storage'),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', None)]],
        depends=['type', 'active', 'id'])
    storage_location = fields.Many2One(
        "stock.location", "Storage", states={
            'invisible': Eval('type') != 'warehouse',
            'readonly': ~Eval('active'),
            'required': Eval('type') == 'warehouse',
        },
        domain=[
            ('type', 'in', ['storage', 'view']),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', None)]],
        depends=['type', 'active', 'id'])
    picking_location = fields.Many2One(
        'stock.location', 'Picking', states={
            'invisible': Eval('type') != 'warehouse',
            'readonly': ~Eval('active'),
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('storage_location', -1)]),
            ],
        depends=['type', 'active', 'storage_location'],
        help='If empty the Storage is used')
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
            'get_quantity')
    cost_value = fields.Function(fields.Numeric('Cost Value'),
        'get_cost_value')

    @classmethod
    def __setup__(cls):
        super(Location, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))
        cls._error_messages.update({
                'invalid_type_for_moves': ('Location "%s" with existing moves '
                    'cannot be changed to a type that does not support moves.'
                    ),
                'child_of_warehouse': ('Location "%(location)s" must be a '
                    'child of warehouse "%(warehouse)s".'),
                })

        parent_domain = []
        childs_domain = []
        childs_mapping = cls._childs_domain()
        for type_, allowed_parents in cls._parent_domain().iteritems():
            parent_domain.append(If(Eval('type') == type_,
                    ('type', 'in', allowed_parents), ()))
            childs_domain.append(If(Eval('type') == type_,
                    ('type', 'in', childs_mapping[type_]), ()))
        cls.parent.domain = parent_domain
        cls.childs.domain = childs_domain
        cls.childs.depends.append('type')

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
        for type_, allowed_parents in cls._parent_domain().iteritems():
            for parent in allowed_parents:
                childs_domain.setdefault(parent, [])
                childs_domain[parent].append(type_)
        return childs_domain

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        super(Location, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        table.index_action(['left', 'right'], 'add')

    @classmethod
    def validate(cls, locations):
        super(Location, cls).validate(locations)
        cls.check_recursion(locations)
        for location in locations:
            location.check_type_for_moves()

    def check_type_for_moves(self):
        """ Check locations with moves have types compatible with moves. """
        invalid_move_types = ['warehouse', 'view']
        Move = Pool().get('stock.move')
        if (self.type in invalid_move_types
                and Move.search([
                        ['OR',
                            ('to_location', '=', self.id),
                            ('from_location', '=', self.id),
                            ],
                        ('state', 'not in', ['staging', 'draft']),
                        ])):
            self.raise_user_error('invalid_type_for_moves', (self.rec_name,))

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0

    @staticmethod
    def default_type():
        return 'storage'

    @classmethod
    def check_xml_record(self, records, values):
        return True

    def get_warehouse(self, name):
        # Order by descending left to get the first one in the tree
        locations = self.search([
                ('parent', 'parent_of', [self.id]),
                ('type', '=', 'warehouse'),
                ], order=[('left', 'DESC')])
        if locations:
            return locations[0].id

    @classmethod
    def search_rec_name(cls, name, clause):
        locations = cls.search([
                ('code', '=', clause[2]),
                ], order=[])
        if locations:
            return [('id', 'in', [l.id for l in locations])]
        return [(cls._rec_name,) + tuple(clause[1:])]

    @classmethod
    def get_quantity(cls, locations, name):
        pool = Pool()
        Product = pool.get('product.product')
        Date_ = pool.get('ir.date')

        if (not Transaction().context.get('product')) \
                or not (isinstance(Transaction().context['product'],
                    (int, long))):
            return dict([(l.id, 0) for l in locations])

        with Transaction().set_context(active_test=False):
            if not Product.search([
                        ('id', '=', Transaction().context['product']),
                        ]):
                return dict([(l.id, 0) for l in locations])

        context = {}
        if (name == 'quantity'
                and Transaction().context.get('stock_date_end') >
                Date_.today()):
            context['stock_date_end'] = Date_.today()

        if name == 'forecast_quantity':
            context['forecast'] = True
            if not Transaction().context.get('stock_date_end'):
                context['stock_date_end'] = datetime.date.max

        product_id = Transaction().context['product']
        pbl = {}
        for sub_locations in grouped_slice(locations):
            location_ids = [l.id for l in sub_locations]
            with Transaction().set_context(context):
                pbl.update(Product.products_by_location(
                        location_ids=location_ids, product_ids=[product_id],
                        with_childs=True))

        return dict((loc.id, pbl.get((loc.id, product_id), 0))
            for loc in locations)

    @classmethod
    def get_cost_value(cls, locations, name):
        Product = Pool().get('product.product')
        trans_context = Transaction().context
        product_id = trans_context.get('product')
        if not product_id:
            return dict((l.id, None) for l in locations)
        cost_values, context = {}, {}
        if 'stock_date_end' in trans_context:
            # Use the last cost_price of the day
            context['_datetime'] = datetime.datetime.combine(
                trans_context['stock_date_end'], datetime.time.max)
        with Transaction().set_context(context):
            product = Product(product_id)
            for location in locations:
                # The date could be before the product creation
                if not isinstance(product.cost_price, Decimal):
                    cost_values[location.id] = None
                else:
                    cost_values[location.id] = (Decimal(str(location.quantity))
                        * product.cost_price)
        return cost_values

    @classmethod
    def _set_warehouse_parent(cls, locations):
        '''
        Set the parent of child location of warehouse if not set
        '''
        to_update = set()
        for location in locations:
            if location.type == 'warehouse':
                if not location.input_location.parent:
                    to_update.add(location.input_location)
                if not location.output_location.parent:
                    to_update.add(location.output_location)
                if not location.storage_location.parent:
                    to_update.add(location.storage_location)
                if to_update:
                    cls.write(list(to_update), {
                        'parent': location.id,
                        })
                    to_update.clear()

    @classmethod
    def create(cls, vlist):
        locations = super(Location, cls).create(vlist)
        cls._set_warehouse_parent(locations)
        return locations

    @classmethod
    def write(cls, *args):
        super(Location, cls).write(*args)
        locations = sum(args[::2], [])
        cls._set_warehouse_parent(locations)

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
                    cls.raise_user_error('child_of_warehouse', {
                            'location': location.rec_name,
                            'warehouse': warehouse.rec_name,
                            })

    @classmethod
    def copy(cls, locations, default=None):
        if default is None:
            default = {}

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
                    for field, loc_id in warehouse_locations.iteritems():
                        if loc_id == location.id:
                            cls.write([cp_warehouse], {
                                    field: new_location.id,
                                    })

            res.append(new_location)
        return res


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'
    supplier_location = fields.Property(fields.Many2One('stock.location',
        'Supplier Location', domain=[('type', '=', 'supplier')],
        help='The default source location when receiving products from the '
        'party.'))
    customer_location = fields.Property(fields.Many2One('stock.location',
        'Customer Location', domain=[('type', '=', 'customer')],
        help='The default destination location when sending products to the '
        'party.'))


class ProductsByLocationsStart(ModelView):
    'Products by Locations'
    __name__ = 'stock.products_by_locations.start'
    forecast_date = fields.Date(
        'At Date', help=('Allow to compute expected '
            'stock quantities for this date.\n'
            '* An empty value is an infinite date in the future.\n'
            '* A date in the past will provide historical values.'))

    @staticmethod
    def default_forecast_date():
        Date_ = Pool().get('ir.date')
        return Date_.today()


class ProductsByLocations(Wizard):
    'Products by Locations'
    __name__ = 'stock.products_by_locations'
    start = StateView('stock.products_by_locations.start',
        'stock.products_by_locations_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open', 'tryton-ok', True),
            ])
    open = StateAction('stock.act_products_by_locations')

    def do_open(self, action):
        pool = Pool()
        Location = pool.get('stock.location')
        Lang = pool.get('ir.lang')

        context = {}
        context['locations'] = Transaction().context.get('active_ids')
        date = self.start.forecast_date or datetime.date.max
        context['stock_date_end'] = Date(date.year, date.month, date.day)
        action['pyson_context'] = PYSONEncoder().encode(context)

        locations = Location.browse(context['locations'])

        for code in [Transaction().language, 'en_US']:
            langs = Lang.search([
                    ('code', '=', code),
                    ])
            if langs:
                break
        lang = langs[0]
        date = Lang.strftime(date, lang.code, lang.date)

        action['name'] += ' - (%s) @ %s' % (
            ','.join(l.name for l in locations), date)
        return action, {}

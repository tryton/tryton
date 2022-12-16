#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from trytond.pyson import Not, Bool, Eval, Equal, PYSONEncoder, Date
from trytond.transaction import Transaction
from trytond.pool import Pool

STATES = {
    'readonly': Not(Bool(Eval('active'))),
}
DEPENDS = ['active']


class Location(ModelSQL, ModelView):
    "Stock Location"
    _name = 'stock.location'
    _description = __doc__
    name = fields.Char("Name", size=None, required=True, states=STATES,
        depends=DEPENDS, translate=True)
    code = fields.Char("Code", size=None, states=STATES, depends=DEPENDS,
        select=1)
    active = fields.Boolean('Active', select=1)
    address = fields.Many2One("party.address", "Address",
        states={
            'invisible': Not(Equal(Eval('type'), 'warehouse')),
            'readonly': Not(Bool(Eval('active'))),
            },
        depends=['type', 'active'])
    type = fields.Selection([
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('lost_found', 'Lost and Found'),
        ('warehouse', 'Warehouse'),
        ('storage', 'Storage'),
        ('production', 'Production'),
        ('view', 'View'),
        ], 'Location type', states=STATES, depends=DEPENDS)
    parent = fields.Many2One("stock.location", "Parent", select=1,
            left="left", right="right")
    left = fields.Integer('Left', required=True, select=1)
    right = fields.Integer('Right', required=True, select=1)
    childs = fields.One2Many("stock.location", "parent", "Children")
    input_location = fields.Many2One(
        "stock.location", "Input", states={
            'invisible': Not(Equal(Eval('type'), 'warehouse')),
            'readonly': Not(Bool(Eval('active'))),
            'required': Equal(Eval('type'), 'warehouse'),
            },
        domain=[
            ('type','=','storage'),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', False),
                ],
            ],
        depends=['type', 'active', 'id'])
    output_location = fields.Many2One(
        "stock.location", "Output", states={
            'invisible': Not(Equal(Eval('type'), 'warehouse')),
            'readonly': Not(Bool(Eval('active'))),
            'required': Equal(Eval('type'), 'warehouse'),
        },
        domain=[('type','=','storage'),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', False)]],
        depends=['type', 'active', 'id'])
    storage_location = fields.Many2One(
        "stock.location", "Storage", states={
            'invisible': Not(Equal(Eval('type'), 'warehouse')),
            'readonly': Not(Bool(Eval('active'))),
            'required': Equal(Eval('type'), 'warehouse'),
        },
        domain=[('type','=','storage'),
            ['OR',
                ('parent', 'child_of', [Eval('id')]),
                ('parent', '=', False)]],
        depends=['type', 'active', 'id'])
    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
            'get_quantity')

    def __init__(self):
        super(Location, self).__init__()
        self._order.insert(0, ('name', 'ASC'))
        self._constraints += [
            ('check_recursion', 'recursive_locations'),
            ('check_type_for_moves', 'invalid_type_for_moves'),
        ]
        self._error_messages.update({
            'recursive_locations': 'You can not create recursive locations!',
            'invalid_type_for_moves': 'A location with existing moves ' \
                'cannot be changed to a type that does not support moves.',
            'child_of_warehouse': 'Location "%s" must be a child of warehouse "%s"!',
        })

    def init(self, module_name):
        super(Location, self).init(module_name)
        cursor = Transaction().cursor

        table = TableHandler(cursor, self, module_name)
        table.index_action(['left', 'right'], 'add')

    def check_type_for_moves(self, ids):
        """ Check locations with moves have types compatible with moves. """
        invalid_move_types = ['warehouse', 'view']
        move_obj = Pool().get('stock.move')
        for location in self.browse(ids):
            if location.type in invalid_move_types and \
                move_obj.search(['OR',
                    ('to_location', '=', location.id),
                    ('from_location', '=', location.id),
                    ]):
                return False
        return True

    def default_active(self):
        return True

    def default_left(self):
        return 0

    def default_right(self):
        return 0

    def default_type(self):
        return 'storage'

    def check_xml_record(self, ids, values):
        return True

    def search_rec_name(self, name, clause):
        ids = self.search([
            ('code', '=', clause[2]),
            ], order=[])
        if ids:
            return [('id', 'in', ids)]
        return [(self._rec_name,) + tuple(clause[1:])]

    def get_quantity(self, ids, name):
        product_obj = Pool().get('product.product')
        date_obj = Pool().get('ir.date')

        if (not Transaction().context.get('product')) \
                or not (isinstance(Transaction().context['product'],
                    (int, long))):
            return dict([(i, 0) for i in ids])

        with Transaction().set_context(active_test=False):
            if not product_obj.search([
                ('id', '=', Transaction().context['product']),
                ]):
                return dict([(i, 0) for i in ids])

        context = {}
        if (name == 'quantity'
                and Transaction().context.get('stock_date_end') >
                date_obj.today()):
            context['stock_date_end'] = date_obj.today()

        if name == 'forecast_quantity':
            context['forecast'] = True
            if not Transaction().context.get('stock_date_end'):
                context['stock_date_end'] = datetime.date.max

        with Transaction().set_context(context):
            pbl = product_obj.products_by_location(location_ids=ids,
                    product_ids=[Transaction().context['product']],
                    with_childs=True, skip_zero=False).iteritems()

        return dict([(loc,qty) for (loc,prod), qty in pbl])

    def view_header_get(self, value, view_type='form'):
        product_obj = Pool().get('product.product')
        value = super(Location, self).view_header_get(value,
                view_type=view_type)
        if (Transaction().context.get('product')
                and isinstance(Transaction().context['product'], (int, long))):
            with Transaction().set_context(active_test=False):
                product_ids = product_obj.search([
                    ('id', '=', Transaction().context['product']),
                    ], limit=1)
            if product_ids:
                product = product_obj.browse(product_ids[0])
                return value + ': ' + product.rec_name + \
                        ' (' + product.default_uom.rec_name + ')'
        return value

    def _set_warehouse_parent(self, locations):
        '''
        Set the parent of child location of warehouse if not set

        :param locations: a BrowseRecordList of locations
        :return: a list with updated location ids
        '''
        location_ids = set()
        for location in locations:
            if location.type == 'warehouse':
                if not location.input_location.parent:
                    location_ids.add(location.input_location.id)
                if not location.output_location.parent:
                    location_ids.add(location.output_location.id)
                if not location.storage_location.parent:
                    location_ids.add(location.storage_location.id)
                if location_ids:
                    self.write(list(location_ids), {
                        'parent': location.id,
                        })
                    location_ids.clear()

    def create(self, vals):
        res = super(Location, self).create(vals)
        locations = self.browse([res])
        self._set_warehouse_parent(locations)
        return res

    def write(self, ids, vals):
        res = super(Location, self).write(ids, vals)
        if isinstance(ids, (int, long)):
            ids = [ids]
        locations = self.browse(ids)
        self._set_warehouse_parent(locations)

        check_wh = self.search([
            ('type', '=', 'warehouse'),
            ['OR',
                ('storage_location', 'in', ids),
                ('input_location', 'in', ids),
                ('output_location', 'in', ids),
            ]])

        warehouses = self.browse(check_wh)
        fields = ('storage_location', 'input_location', 'output_location')
        wh2childs = {}
        for warehouse in warehouses:
            in_out_sto = (warehouse[f].id for f in fields)
            for location in locations:
                if location.id not in in_out_sto:
                    continue
                childs = wh2childs.setdefault(warehouse.id, self.search([
                    ('parent', 'child_of', warehouse.id),
                    ]))
                if location.id not in childs:
                    self.raise_user_error('child_of_warehouse',
                        (location.name, warehouse.name))

        return res

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        default['left'] = 0
        default['right'] = 0

        res = []
        locations = self.browse(ids)
        for location in locations:
            if location.type == 'warehouse':

                wh_default = default.copy()
                wh_default['type'] = 'view'
                wh_default['input_location'] = False
                wh_default['output_location'] = False
                wh_default['storage_location'] = False
                wh_default['childs'] = False

                new_id = super(Location, self).copy(location.id,
                        default=wh_default)

                with Transaction().set_context(
                        cp_warehouse_locations={
                            'input_location': location.input_location.id,
                            'output_location': location.output_location.id,
                            'storage_location': location.storage_location.id,
                            },
                        cp_warehouse_id=new_id):
                    self.copy([c.id for c in location.childs],
                            default={'parent': new_id})
                self.write(new_id, {
                    'type': 'warehouse',
                    })
            else:
                new_id = super(Location, self).copy(location.id,
                        default=default)
                warehouse_locations = Transaction().context.get(
                        'cp_warehouse_locations') or {}
                if location.id in warehouse_locations.values():
                    for field, loc_id in warehouse_locations.iteritems():
                        if loc_id == location.id:
                            self.write(Transaction().context['cp_warehouse_id'],
                                    {field: new_id})

            res.append(new_id)

        return int_id and res[0] or res

Location()


class Party(ModelSQL, ModelView):
    _name = 'party.party'
    supplier_location = fields.Property(fields.Many2One('stock.location',
        'Supplier Location', domain=[('type', '=', 'supplier')],
        help='The default source location when receiving products from the '
        'party.'))
    customer_location = fields.Property(fields.Many2One('stock.location',
        'Customer Location', domain=[('type', '=', 'customer')],
        help='The default destination location when sending products to the '
        'party.'))

Party()


class ChooseStockDateInit(ModelView):
    _name = 'stock.location_stock_date.init'
    _description = "Compute stock quantities"
    forecast_date = fields.Date(
        'At Date', help='Allow to compute expected '\
            'stock quantities for this date.\n'\
            '* An empty value is an infinite date in the future.\n'\
            '* A date in the past will provide historical values.')

    def default_forecast_date(self):
        date_obj = Pool().get('ir.date')
        return date_obj.today()

ChooseStockDateInit()


class OpenProduct(Wizard):
    'Open Products'
    _name = 'stock.product.open'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'stock.location_stock_date.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_product',
                'state': 'end',
            },
        },
    }

    def _action_open_product(self, data):
        model_data_obj = Pool().get('ir.model.data')
        act_window_obj = Pool().get('ir.action.act_window')
        act_window_id = model_data_obj.get_id('stock',
                'act_product_by_location')
        res = act_window_obj.read(act_window_id)

        context = {}
        context['locations'] = data['ids']
        if data['form']['forecast_date']:
            date = data['form']['forecast_date']
        else:
            date = datetime.date.max
        context['stock_date_end'] = Date(date.year, date.month, date.day)
        res['pyson_context'] = PYSONEncoder().encode(context)

        return res

OpenProduct()

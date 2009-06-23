#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
"Wharehouse"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.backend import TableHandler
import datetime

STATES = {
    'readonly': "not active",
}


class Location(ModelSQL, ModelView):
    "Stock Location"
    _name = 'stock.location'
    _description = __doc__
    name = fields.Char("Name", size=None, required=True, states=STATES,
            translate=True)
    code = fields.Char("Code", size=None, states=STATES, select=1)
    active = fields.Boolean('Active', select=1)
    address = fields.Many2One("party.address", "Address",
            states={
                'invisible': "type != 'warehouse'",
                'readonly': "not active",
            })
    type = fields.Selection([
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('lost_found', 'Lost and Found'),
        ('warehouse', 'Warehouse'),
        ('storage', 'Storage'),
        ('production', 'Production'),
        ('view', 'View'),
        ], 'Location type', states=STATES)
    parent = fields.Many2One("stock.location", "Parent", select=1,
            left="left", right="right")
    left = fields.Integer('Left', required=True, select=1)
    right = fields.Integer('Right', required=True, select=1)
    childs = fields.One2Many("stock.location", "parent", "Children")
    input_location = fields.Many2One(
        "stock.location", "Input", states={
            'invisible': "type != 'warehouse'",
            'readonly': "not active",
            'required': "type == 'warehouse'",
        },
        domain=["('type','=','storage')",
            ['OR',
                "('parent', 'child_of', [active_id])",
                "('parent', '=', False)"]])
    output_location = fields.Many2One(
        "stock.location", "Output", states={
            'invisible': "type != 'warehouse'",
            'readonly': "not active",
            'required': "type == 'warehouse'",
        },
        domain=["('type','=','storage')",
            ['OR',
                "('parent', 'child_of', [active_id])",
                "('parent', '=', False)"]])
    storage_location = fields.Many2One(
        "stock.location", "Storage", states={
            'invisible': "type != 'warehouse'",
            'readonly': "not active",
            'required': "type == 'warehouse'",
        },
        domain=["('type','=','storage')",
            ['OR',
                "('parent', 'child_of', [active_id])",
                "('parent', '=', False)"]])
    quantity = fields.Function('get_quantity', type='float', string='Quantity')
    forecast_quantity = fields.Function('get_quantity', type='float',
                                        string='Forecast Quantity')

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

    def init(self, cursor, module_name):
        super(Location, self).init(cursor, module_name)

        table = TableHandler(cursor, self, module_name)
        table.index_action(['left', 'right'], 'add')

    def check_type_for_moves(self, cursor, user, ids):
        """ Check locations with moves have types compatible with moves. """
        invalid_move_types = ['warehouse', 'view']
        move_obj = self.pool.get('stock.move')
        for location in self.browse(cursor, user, ids):
            if location.type in invalid_move_types and \
                move_obj.search(cursor, user, ['OR',
                    ('to_location', '=', location.id),
                    ('from_location', '=', location.id)]):
                return False
        return True

    def default_active(self, cursor, user, context=None):
        return True

    def default_left(self, cursor, user, context=None):
        return 0

    def default_right(self, cursor, user, context=None):
        return 0

    def default_type(self, cursor, user, context=None):
        return 'storage'

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            ids = self.search(cursor, user, [('code', '=', args[i][2])],
                    context=context)
            if ids:
                args2.append(('id', 'in', ids))
            else:
                args2.append((self._rec_name, args[i][1], args[i][2]))
            i += 1
        return args2

    def get_quantity(self, cursor, user, ids, name, arg, context=None):
        product_obj = self.pool.get('product.product')
        date_obj = self.pool.get('ir.date')

        if not context:
            context = {}

        if (not context.get('product')) \
                or not (isinstance(context['product'], (int, long))):
            return dict([(i, 0) for i in ids])

        ctx = context.copy()
        ctx['active_test'] = False
        if not product_obj.search(cursor, user, [
            ('id', '=', context['product']),
            ], context=ctx):
            return dict([(i, 0) for i in ids])

        if name == 'quantity' and \
                context.get('stock_date_end') > \
                date_obj.today(cursor, user, context=context):

            context = context.copy()
            context['stock_date_end'] = date_obj.today(
                cursor, user, context=context)

        if name == 'forecast_quantity':
            context = context.copy()
            context['forecast'] = True
            if not context.get('stock_date_end'):
                context['stock_date_end'] = datetime.date.max

        pbl = product_obj.products_by_location(cursor, user, location_ids=ids,
            product_ids=[context['product']], with_childs=True, skip_zero=False,
            context=context).iteritems()

        return dict([(loc,qty) for (loc,prod), qty in pbl])

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        product_obj = self.pool.get('product.product')
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['active_test'] = False
        if context.get('product') \
                and isinstance(context['product'], (int, long)) \
                and product_obj.search(cursor, user, [
                    ('id', '=', context['product']),
                    ], context=ctx):
            product = product_obj.browse(cursor, user, context['product'],
                    context=context)
            return value + ': ' + product.rec_name + \
                    ' (' + product.default_uom.rec_name + ')'
        return value

    def _set_warehouse_parent(self, cursor, user, locations, context=None):
        '''
        Set the parent of child location of warehouse if not set

        :param cursor: the database cursor
        :param user: the user id
        :param locations: a BrowseRecordList of locations
        :param context: the context
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
        location_ids = list(location_ids)
        if location_ids:
            self.write(cursor, user, location_ids, {
                'parent': location.id,
                }, context=context)

    def create(self, cursor, user, vals, context=None):
        res = super(Location, self).create(cursor, user, vals, context=context)
        locations = self.browse(cursor, user, [res], context=context)
        self._set_warehouse_parent(cursor, user, locations, context=context)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Location, self).write(cursor, user, ids, vals,
                context=context)
        if isinstance(ids, (int, long)):
            ids = [ids]
        locations = self.browse(cursor, user, ids, context=context)
        self._set_warehouse_parent(cursor, user, locations, context=context)

        check_wh = self.search(
            cursor, user,
            [('type', '=', 'warehouse'),
             ['OR',
              ('storage_location', 'in', ids),
              ('input_location', 'in', ids),
              ('output_location', 'in', ids)
              ]],
            context=context)

        warehouses = self.browse(cursor, user, check_wh, context=context)
        fields = ('storage_location', 'input_location', 'output_location')
        wh2childs = {}
        for warehouse in warehouses:
            in_out_sto = (warehouse[f].id for f in fields)
            for location in locations:
                if location.id not in in_out_sto:
                    continue
                childs = wh2childs.setdefault(
                    warehouse.id,
                    self.search(
                        cursor, user, [('parent', 'child_of', warehouse.id)],
                        context=context))
                if location.id not in childs:
                    self.raise_user_error(
                        cursor, 'child_of_warehouse',
                        (location.name, warehouse.name), context=context)

        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        default['left'] = 0
        default['right'] = 0

        res = []
        locations = self.browse(cursor, user, ids, context=context)
        for location in locations:
            if location.type == 'warehouse':

                wh_default = default.copy()
                wh_default['type'] = 'view'
                wh_default['input_location'] = False
                wh_default['output_location'] = False
                wh_default['storage_location'] = False
                wh_default['childs'] = False

                new_id = super(Location, self).copy(
                    cursor, user, location.id, default=wh_default,
                    context=context)

                child_context = context and context.copy() or {}
                child_context['cp_warehouse_locations'] = {
                    'input_location': location.input_location.id,
                    'output_location': location.output_location.id,
                    'storage_location': location.storage_location.id}
                child_context['cp_warehouse_id'] = new_id

                self.copy(
                    cursor, user, [c.id for c in location.childs],
                    default={'parent':new_id}, context=child_context)
                self.write(
                    cursor, user, new_id, {'type': 'warehouse'}, context=context)
            else:
                new_id = super(Location, self).copy(
                    cursor, user, location.id, default=default, context=context)
                warehouse_locations = context.get('cp_warehouse_locations', {})
                if location.id in warehouse_locations.values():
                    for field, loc_id in warehouse_locations.iteritems():
                        if loc_id == location.id:
                            self.write(
                                cursor, user, context['cp_warehouse_id'],
                                {field: new_id}, context=context)

            res.append(new_id)

        return int_id and res[0] or res

Location()


class Party(ModelSQL, ModelView):
    _name = 'party.party'
    supplier_location = fields.Property(type='many2one',
            relation='stock.location', string='Supplier Location',
            domain=[('type', '=', 'supplier')],
            help='The default source location ' \
                    'when receiving products from the party.')
    customer_location = fields.Property(type='many2one',
            relation='stock.location', string='Customer Location',
            domain=[('type', '=', 'customer')],
            help='The default destination location ' \
                    'when sending products to the party.')

Party()


class ChooseStockDateInit(ModelView):
    _name = 'stock.location_stock_date.init'
    _description = "Compute stock quantities"
    forecast_date = fields.Date(
        'At Date', help='Allow to compute expected '\
            'stock quantities for this date.\n'\
            '* An empty value is an infinite date in the future.\n'\
            '* A date in the past will provide historical values.')

    def default_forecast_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

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

    def _action_open_product(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_product_by_location'),
            ('module', '=', 'stock'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)

        if context == None: context = {}
        context['locations'] = data['ids']
        if data['form']['forecast_date']:
            context['stock_date_end'] = data['form']['forecast_date']
        else:
            context['stock_date_end'] = datetime.date.max
        res['context'] = str(context)

        return res

OpenProduct()

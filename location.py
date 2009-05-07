#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
"Wharehouse"
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import datetime

STATES = {
    'readonly': "not active",
}


class Location(OSV):
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
        ], 'Location type', states=STATES)
    parent = fields.Many2One("stock.location", "Parent", select=1,
            left="left", right="right")
    left = fields.Integer('Left', required=True)
    right = fields.Integer('Right', required=True)
    childs = fields.One2Many("stock.location", "parent", "Childs")
    input_location = fields.Many2One(
        "stock.location", "Input", states={
            'invisible': "type != 'warehouse'",
            'readonly': "not active",
            'required': "type == 'warehouse'",
        },
        domain="[('type','=','storage'), ['OR', " \
                "('parent', 'child_of', [active_id]), " \
                "('parent', '=', False)]]")
    output_location = fields.Many2One(
        "stock.location", "Output", states={
            'invisible': "type != 'warehouse'",
            'readonly': "not active",
            'required': "type == 'warehouse'",
        },
        domain="[('type','=','storage'), ['OR', " \
                "('parent', 'child_of', [active_id]), " \
                "('parent', '=', False)]]")
    storage_location = fields.Many2One(
        "stock.location", "Storage", states={
            'invisible': "type != 'warehouse'",
            'readonly': "not active",
            'required': "type == 'warehouse'",
        },
        domain="[('type','=','storage'), ['OR', " \
                "('parent', 'child_of', [active_id]), " \
                "('parent', '=', False)]]")
    quantity = fields.Function('get_quantity', type='float', string='Quantity')
    forecast_quantity = fields.Function('get_quantity', type='float',
                                        string='Forecast Quantity')

    def __init__(self):
        super(Location, self).__init__()
        self._order.insert(0, ('name', 'ASC'))
        self._constraints += [
            ('check_recursion', 'recursive_locations'),
        ]
        self._error_messages.update({
            'recursive_locations': 'You can not create recursive locations!',
        })

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

    def name_search(self, cursor, user, name,  args=None, operator='ilike',
                    context=None, limit=None):
        if not args:
            args=[]
        ids = self.search(
            cursor, user, [('code', '=', name)] + args, limit=limit,
            context=context)
        if not ids:
            ids = self.search(
                cursor, user, [('name', operator, name)] + args, limit=limit,
                context=context)
        result = self.name_get(cursor, user, ids, context)
        return result

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
        uom_obj = self.pool.get('product.uom')
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['active_test'] = False
        if context.get('product') \
                and isinstance(context['product'], (int, long)) \
                and product_obj.search(cursor, user, [
                    ('id', '=', context['product']),
                    ], context=ctx):
            product_name = product_obj.name_get(cursor, user, context['product'],
                    context=context)[0][1]
            product = product_obj.browse(cursor, user, context['product'],
                    context=context)
            uom_name = uom_obj.name_get(cursor, user, product.default_uom.id,
                    context=context)[0][1]
            return value + ': ' + product_name + ' (' + uom_name + ')'
        return False

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
        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default['left'] = 0
        default['right'] = 0
        return super(Location, self).copy(cursor, user, ids, default=default,
                context=context)

Location()


class Party(OSV):
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


class ChooseStockDateInit(WizardOSV):
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

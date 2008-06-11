"Wharehouse"
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV

STATES = {
    'readonly': "not active",
}
STATES_WH = {
    'invisible': "type != 'warehouse'",
    'readonly': "not active",
}


class Location(OSV):
    "Stock Location"
    _name = 'stock.location'
    _description = __doc__
    name = fields.Char("Name", size=None, required=True, states=STATES)
    code = fields.Char("Code", size=None, states=STATES, select=1)
    active = fields.Boolean('Active', select=1)
    address = fields.Many2One("relationship.address", "Address",
            states=STATES_WH)
    type = fields.Selection([
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('lost_found', 'Lost and Found'),
        ('warehouse', 'Warehouse'),
        ('storage', 'Storage'),
        ('production', 'Production'),
        ], 'Location type', states=STATES)
    parent = fields.Many2One("stock.location", "Parent", select=1)
    childs = fields.One2Many("stock.location", "parent", "Childs")
    input_location = fields.Many2One(
        "stock.location", "Input", states=STATES_WH,
        domain="[('type','=','storage'), ('parent', 'child_of', [active_id])]")
    output_location = fields.Many2One(
        "stock.location", "Output", states=STATES_WH,
        domain="[('type','=','storage'), ('parent', 'child_of', [active_id])]")
    storage_location = fields.Many2One(
        "stock.location", "Storage", states=STATES_WH,
        domain="[('type','=','storage'), ('parent', 'child_of', [active_id])]")
    quantity = fields.Function('get_quantity', type='float', string='Quantity')
    forecast_quantity = fields.Function('get_quantity', type='float',
                                        string='Forecast Quantity')

    def __init__(self):
        super(Location, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return True

    def default_type(self, cursor, user, context=None):
        return 'storage'

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

    def _tree_qty(self, qty_by_ltn, childs, ids, to_compute):
        res = 0
        for h in ids:
            if (not childs.get(h)) or (not to_compute[h]):
                res += qty_by_ltn.setdefault(h, 0)
            else:
                sub_qty = self._tree_qty(qty_by_ltn, childs, childs[h], to_compute)
                qty_by_ltn.setdefault(h, 0)
                qty_by_ltn[h] += sub_qty
                res += qty_by_ltn[h]
                to_compute[h] = False
        return res

    def get_quantity(self, cursor, user, ids, name, arg, context=None):
        if (not context) or (not context.get('product')):
            return dict([(i,0) for i in ids])
        product_obj = self.pool.get('product.product')
        all_ids = self.search(cursor, user, [('parent', 'child_of', ids)])
        if name == 'forecast_quantity':
            pbl = product_obj.products_by_location(
                cursor, user, location_ids=all_ids,
                product_ids=[context['product']], forecast=True, context=context)
        else:
            pbl = product_obj.products_by_location(
                cursor, user, location_ids=all_ids,
                product_ids=[context['product']], context=context)
        qty_by_ltn = dict([(i['location'], i['quantity']) for i in pbl])
        to_compute = dict.fromkeys(all_ids, True)
        locations = self.browse(cursor, user, all_ids, context=context)
        childs = {}
        for location in locations:
            if location.parent:
                childs.setdefault(location.parent.id, []).append(location.id)
        self._tree_qty(qty_by_ltn, childs, ids, to_compute)
        return qty_by_ltn

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        if context is None:
            context = {}
        if context.get('product'):
            product_name = product_obj.name_get(cursor, user, context['product'],
                    context=context)[0][1]
            product = product_obj.browse(cursor, user, context['product'],
                    context=context)
            uom_name = uom_obj.name_get(cursor, user, product.default_uom.id,
                    context=context)[0][1]
            return value + ': ' + product_name + ' (' + uom_name + ')'
        return False

Location()


class Party(OSV):
    _name = 'relationship.party'
    supplier_location = fields.Property(type='many2one',
            relation='stock.location', string='Supplier Location',
            group_name='Stock Properties', view_load=True,
            domain=[('type', '=', 'supplier')],
            help='The default source location ' \
                    'when receiving products from the party.')
    customer_location = fields.Property(type='many2one',
            relation='stock.location', string='Customer Location',
            group_name='Stock Properties', view_load=True,
            domain=[('type', '=', 'customer')],
            help='The default destination location ' \
                    'when sending products to the party.')

Party()


class ChooseForecatsDateInit(WizardOSV):
    _name = 'stock.location_forecast_date.init'
    forecast_date = fields.Date(
        'Forecast Date', help='Allow to compute expected '\
            'stock quantities for this date.\n'\
            '* An empty value is an infinite date in the future.\n'\
            '* A date in the past will provide historical values.')
ChooseForecatsDateInit()


class OpenProduct(Wizard):
    'Open Products'
    _name = 'stock.product.open'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'stock.location_forecast_date.init',
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
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)

        context = {'locations': data['ids']}
        if data['form']['forecast_date']:
            context['forecast_date'] = data['form']['forecast_date']
        res['context'] = str(context)

        return res

OpenProduct()

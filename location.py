"Wharehouse"
from trytond.osv import fields, OSV

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
    address = fields.Many2One("partner.address", "Address",
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
    childs = fields.One2Many("stock.location", "parent", "Childs",)
    input_location = fields.Many2One(
        "stock.location", "Input", states=STATES_WH,
        domain="[('type','=','storage'), ('parent', 'child_of', [active_id])]")
    output_location = fields.Many2One(
        "stock.location", "Output", states=STATES_WH,
        domain="[('type','=','storage'), ('parent', 'child_of', [active_id])]")
    storage_location = fields.Many2One(
        "stock.location", "Storage", states=STATES_WH,
        domain="[('type','=','storage'), ('parent', 'child_of', [active_id])]")

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

Location()


class Partner(OSV):
    _name = 'partner.partner'
    supplier_location = fields.Property(type='many2one',
            relation='stock.location', string='Supplier Location',
            group_name='Stock Properties', view_load=True,
            domain=[('type', '=', 'supplier')],
            help='The default source location ' \
                    'when receiving products from the partner.')
    customer_location = fields.Property(type='many2one',
            relation='stock.location', string='Customer Location',
            group_name='Stock Properties', view_load=True,
            domain=[('type', '=', 'customer')],
            help='The default destination location ' \
                    'when sending products to the partner.')

Partner()

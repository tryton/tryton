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
    name = fields.Char("Name", size=64, required=True, states=STATES,)
    code = fields.Char("Code", size=32, states=STATES, select=1)
    active = fields.Boolean('Active', select=1)
    address = fields.Many2One("partner.address", "Address",
            states=STATES_WH)
    type = fields.Selection([('supplier', 'Supplier'),
                              ('customer', 'Customer'),
                              ('inventory', 'Inventory'),
                              ('procurement', 'Procurement'),
                              ('warehouse', 'Warehouse'),
                              ('storage', 'Storage'),
                              ('production', 'Production')],
                             'Location type', states=STATES,)
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

    # TODO: champ calcule vers product (retournant les product dispo)
    # + context qui passe la location courante et permet de calculer
    # les qtt des produits. et on ne met ce o2m que dans une certaine vue

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

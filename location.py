"Wharehouse"
from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}

class Location(OSV):
    "Stock Location"
    _name = 'stock.location'
    _order = 'name'
    _description = __doc__
    name = fields.Char("Name", size=64, required=True, states=STATES,)
    code = fields.Char("Code", size=32, states=STATES, select=True,)
    active = fields.Boolean('Active', select=True)
    usage = fields.Selection([('supplier','Supplier'),
                              ('customer','Customer'),
                              ('inventory','Inventory'),
                              ('procurement','Procurement'),
                              ('production','Production')],
                             'Location type', states=STATES,)
    warehouse = fields.Many2One("stock.warehouse", "Warehouse", select="1")

    def default_active(self, cursor, user, context=None):
        return True

    def name_search(self, cursor, user, name,  args=None, operator='ilike',
                    context=None, limit=80):
        if not args:
            args=[]
        ids = self.search(cursor, user, [('code','=',name)]+ args, limit=limit,
                          context=context)
        if not ids:
            ids = self.search(cursor, user, [('name',operator,name)]+ args,
                              limit=limit, context=context)
        result = self.name_get(cursor, user, ids, context)
        return result

Location()


class Warehouse(OSV):
    _name = "stock.warehouse"
    _inherit = "stock.warehouse"
    input_location = fields.Many2One("stock.location", "Input location")
    output_location = fields.Many2One("stock.location", "output location")

Warehouse()

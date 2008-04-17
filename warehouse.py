"Wharehouse"
from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}


class Warehouse(OSV):
    "Warehouse"
    _name = 'stock.warehouse'
    _order = 'name'
    _description = __doc__
    name = fields.Char("Name", size=64, required=True, select=True)
    address = fields.Many2One("partner.address", "Address")
    locations = fields.One2Many(
        "stock.location", "warehouse", "Storage locations",)
    active = fields.Boolean('Active', select=True)

    def default_active(self, cursor, user, context=None):
        return True

Warehouse()

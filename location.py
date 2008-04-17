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
    usage = fields.Selection([('supplier', 'Supplier'),
                              ('customer', 'Customer'),
                              ('inventory', 'Inventory'),
                              ('procurement', 'Procurement'),
                              ('production', 'Production')],
                             'Location type', states=STATES,)
    warehouse = fields.Many2One("stock.warehouse", "Warehouse", select="1")

    # TODO: champ calcule vers product (retournant les product dispo)
    # + context qui passe la location courante et permet de calculer
    # les qtt des produits. et on ne met ce o2m que dans une certaine vue

    def default_active(self, cursor, user, context=None):
        return True

    def name_search(self, cursor, user, name,  args=None, operator='ilike',
                    context=None, limit=80):
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

    def products_by_location(self, cursor, user, location_ids,
                            product_ids=None, context=None):
        if not location_ids:
            return []
        prod_by_loc_view = self.pool.get("stock.product_by_location")
        uom_obj = self.pool.get("product.uom")
        where_clause = [('location', 'in', location_ids)]
        if product_ids:
            where_clause.append(('product', 'in', product_ids))

        view_ids = prod_by_loc_view.search(
            cursor, user, where_clause, context=context)

        res = {}
        for line in prod_by_loc_view.browse(
            cursor, user, view_ids, context=context):

            key = line.location.id, line.product.id, line.product.default_uom.id
            if key not in res:
                res[key] = 0
            res[key] += uom_obj.compute_qty(
                cursor, user, line.uom, line.quantity, line.product.default_uom)


        return [{'location': key[0],
                 'product':key[1],
                 'uom': key[2],
                 'quantity': val} for key,val in res.iteritems()]

Location()


class Warehouse(OSV):
    _name = "stock.warehouse"
    _inherit = "stock.warehouse"
    input_location = fields.Many2One("stock.location", "Input location", required=True,)
    output_location = fields.Many2One("stock.location", "Output location", required=True,)
    store_location = fields.Many2One("stock.location", "Default store location", required=True,)

Warehouse()

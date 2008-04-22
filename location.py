"Wharehouse"
from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}

class Location(OSV):
    "Stock Location"
    _name = 'stock.location'
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

    def __init__(self):
        super(Location, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

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

    def raw_products_by_location(self, cursor, user, location_ids,
                            product_ids=None, context=None):
        select_clause = \
            "select location, product, uom, sum(quantity) as quantity "\
             "from ( "\
               "SELECT to_location as location, product, uom, "\
                      "sum(quantity) as quantity "\
               "FROM stock_move "\
               "WHERE state = 'done' and to_%s "\
               "GROUP by to_location, product ,uom  "\
             "UNION  "\
               "SELECT from_location as location, product, uom, "\
                      "-sum(quantity) as quantity "\
               "FROM stock_move "\
               "WHERE state = 'done' and from_%s "\
               "GROUP by from_location, product, uom "\
             ") "\
            "as T group by T.location, T.product, T.uom "\

        where_clause = "location IN (" + \
            ",".join(["%s" for i in location_ids]) + ") "
        where_ids = location_ids
        if product_ids:
            where_clause += "AND product in (" + \
                ",".join(["%s" for i in product_ids]) + ")"
            where_ids += product_ids
        cursor.execute(select_clause % (where_clause, where_clause),
                       where_ids + where_ids)

        return cursor.fetchall()

    def products_by_location(self, cursor, user, location_ids,
                            product_ids=None, context=None):

        uom_obj = self.pool.get("product.uom")
        product_obj = self.pool.get("product.product")
        if not location_ids:
            return []
        if not product_ids:
            product_ids = product_obj.search(cursor, user, [], context=context)

        uom_ids = uom_obj.search(cursor, user, [], context=context)
        uom_by_id = dict((x.id, x) for x in uom_obj.browse(
                cursor, user, uom_ids, context=context))
        uom_by_prod = dict((x.id, x.default_uom) for x in product_obj.browse(
                cursor, user, product_ids, context=context))

        res = {}
        for line in self.raw_products_by_location(
            cursor, user, location_ids, product_ids, context=context):

            location, product, uom, quantity= line
            key = (location, product, uom)
            if key not in res:
                res[key] = 0
            res[key] += uom_obj.compute_qty(
                cursor, user, uom_by_id[uom], quantity, uom_by_prod[product])

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

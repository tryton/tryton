from trytond.osv import fields, OSV


class Product(OSV):
    "Product"
    _name = "product.product"
    _description = __doc__
    _inherits = {'product.template': 'product_template'}

    product_template = fields.Many2One('product.template', 'Product Template',
            required=True)
    code = fields.Char("Code", size=None)
    description = fields.Text("Description", translate=True)

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for product in self.browse(cursor, user, ids, context=context):
            name = product.name
            if product.code:
                name = '[' + product.code + '] ' + product.name
            res.append((product.id, name))
        return res

    def name_search(self, cursor, user, name, args=None, operator='ilike',
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

Product()

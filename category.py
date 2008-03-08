from trytond.osv import fields, OSV


class Category(OSV):
    "Product Category"
    _name = "product.category"
    _description = __doc__
    _order = "parent,name"

    name = fields.Char('Name', size=64, required=True)
    complete_name = fields.Function('get_complete_name', type="char", string='Complete Name')
    parent = fields.Many2One('product.category','Parent Category', select=True)
    childs = fields.One2Many('product.category', 'parent',
            string='Child Categories')

    def get_complete_name(self, cursor, user, ids, name, arg, context):
        res = self.name_get(cursor, user, ids, context)
        return dict(res)

    def name_get(self, cursor, user, ids, context=None):
        if not len(ids):
            return []
        categories = self.browse(cursor, user, ids, context=context)
        res = []
        for category in categories:
            if category.parent:
                name = category.parent.name+' / '+ category.name
            else:
                name = category.name
            res.append((category.id, name))
        return res

Category()

from trytond.osv import fields, OSV


class Category(OSV):
    "Product Category"
    _name = "product.category"
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    complete_name = fields.Function('get_complete_name', type="char",
            string='Complete Name')
    parent = fields.Many2One('product.category','Parent', select=1)
    childs = fields.One2Many('product.category', 'parent',
            string='Childs')

    def __init__(self):
        super(Category, self).__init__()
        self._order.insert(0, ('parent', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def get_complete_name(self, cursor, user, ids, name, arg, context=None):
        res = self.name_get(cursor, user, ids, context=context)
        return dict(res)

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
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

#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


class Category(ModelSQL, ModelView):
    "Product Category"
    _name = "product.category"
    _description = __doc__

    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One('product.category','Parent', select=1)
    childs = fields.One2Many('product.category', 'parent',
            string='Children')

    def __init__(self):
        super(Category, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

    def get_rec_name(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return {}
        res = {}
        categories = self.browse(cursor, user, ids, context=context)
        for category in categories:
            if category.parent:
                name = category.parent.name+' / '+ category.name
            else:
                name = category.name
            res[category.id] = name
        return res

Category()

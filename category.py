#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False",
}


class Category(OSV):
    "Category"
    _name = "relationship.category"
    _description = __doc__
    _parent_name = 'parent'
    name = fields.Char('Category Name', required=True, size=64,
           states=STATES)
    parent = fields.Many2One('relationship.category', 'Parent Category',
           select=1, states=STATES)
    complete_name = fields.Function('get_complete_name',
           type="char", string='Name', states=STATES)
    childs = fields.One2Many('relationship.category', 'parent',
       'Childs Category', states=STATES)
    active = fields.Boolean('Active')

    def __init__(self):
        super(Category, self).__init__()
        self._constraints += [
            ('check_recursion',
             'Error! You can not create recursive categories.', ['parent'])
        ]
        self._order.insert(1, ('name', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return 1

    def get_complete_name(self, cursor, user, ids, name, arg,
            context=None):
        res = self.name_get(cursor, user, ids, context)
        return dict(res)

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
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

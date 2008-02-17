from trytond.osv import fields, OSV
STATES = {'readonly': "active == False",}

class Category(OSV):
    "Partner Category"

    _name = "partner.category"
    _description = __doc__
    _order = 'parent,name'
    _parent_name = 'parent'

    _columns = {
        'name': fields.Char('Category Name', required=True, size=64,
                states= STATES,),
        'parent': fields.Many2One('partner.category', 'Parent Category',
                select=True, states= STATES,),
        'complete_name': fields.Function('complete_name',
                type="char", string='Name', states= STATES,),
        'childs': fields.One2Many('partner.category', 'parent',
            'Childs Category', states= STATES,),
        'active' : fields.Boolean('Active'),
    }

    _defaults = {
        'active' : lambda *a: 1,
    }

    _constraints = [
        ('check_recursion',
         'Error! You can not create recursive categories.', ['parent'])
    ]

    def complete_name(self, cursor, user, obj_id, name, value, arg,
            context=None):
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

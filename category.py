#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']

SEPARATOR = ' / '


class Category(ModelSQL, ModelView):
    "Category"
    _name = "party.category"
    _description = __doc__
    name = fields.Char('Name', required=True, states=STATES, translate=True,
        depends=DEPENDS)
    parent = fields.Many2One('party.category', 'Parent',
        select=True, states=STATES, depends=DEPENDS)
    childs = fields.One2Many('party.category', 'parent',
       'Children', states=STATES, depends=DEPENDS)
    active = fields.Boolean('Active')

    def __init__(self):
        super(Category, self).__init__()
        self._sql_constraints = [
            ('name_parent_uniq', 'UNIQUE(name, parent)',
                'The name of a party category must be unique by parent!'),
        ]
        self._constraints += [
            ('check_recursion', 'recursive_categories'),
            ('check_name', 'wrong_name'),
        ]
        self._error_messages.update({
            'recursive_categories': 'You can not create recursive categories!',
            'wrong_name': 'You can not use "%s" in name field!' % SEPARATOR,
        })
        self._order.insert(1, ('name', 'ASC'))

    def default_active(self):
        return True

    def check_name(self, ids):
        for category in self.browse(ids):
            if SEPARATOR in category.name:
                return False
        return True

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}

        def _name(category):
            if category.id in res:
                return res[category.id]
            elif category.parent:
                return _name(category.parent) + SEPARATOR + category.name
            else:
                return category.name
        for category in self.browse(ids):
            res[category.id] = _name(category)
        return res

    def search_rec_name(self, name, clause):
        if isinstance(clause[2], basestring):
            values = clause[2].split(SEPARATOR)
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name))
                field = 'parent.' + field
            ids = self.search(domain, order=[])
            return [('id', 'in', ids)]
        #TODO Handle list
        return [('name',) + tuple(clause[1:])]

Category()

#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval

__all__ = ['Category']

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']

SEPARATOR = ' / '


class Category(ModelSQL, ModelView):
    "Category"
    __name__ = 'party.category'
    name = fields.Char('Name', required=True, states=STATES, translate=True,
        depends=DEPENDS)
    parent = fields.Many2One('party.category', 'Parent',
        select=True, states=STATES, depends=DEPENDS)
    childs = fields.One2Many('party.category', 'parent',
       'Children', states=STATES, depends=DEPENDS)
    active = fields.Boolean('Active')

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        cls._sql_constraints = [
            ('name_parent_uniq', 'UNIQUE(name, parent)',
                'The name of a party category must be unique by parent.'),
            ]
        cls._error_messages.update({
                'wrong_name': ('Invalid category name "%%s": You can not use '
                    '"%s" in name field.' % SEPARATOR),
                })
        cls._order.insert(1, ('name', 'ASC'))

    @staticmethod
    def default_active():
        return True

    @classmethod
    def validate(cls, categories):
        super(Category, cls).validate(categories)
        cls.check_recursion(categories, rec_name='name')
        for category in categories:
            category.check_name()

    def check_name(self):
        if SEPARATOR in self.name:
            self.raise_user_error('wrong_name', (self.name,))

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + SEPARATOR + self.name
        return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if isinstance(clause[2], basestring):
            values = clause[2].split(SEPARATOR)
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name))
                field = 'parent.' + field
            categories = cls.search(domain, order=[])
            return [('id', 'in', [category.id for category in categories])]
        #TODO Handle list
        return [('name',) + tuple(clause[1:])]

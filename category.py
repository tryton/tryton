# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.conditionals import Coalesce
from sql.operators import Equal

from trytond import backend
from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, Exclude)
from trytond.pyson import Eval

__all__ = ['Category']

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']

SEPARATOR = ' / '


class Category(DeactivableMixin, ModelSQL, ModelView):
    "Category"
    __name__ = 'party.category'
    name = fields.Char('Name', required=True, states=STATES, translate=True,
        depends=DEPENDS,
        help="The main identifier of the category.")
    parent = fields.Many2One('party.category', 'Parent',
        select=True, states=STATES, depends=DEPENDS,
        help="Add the category below the parent.")
    childs = fields.One2Many('party.category', 'parent',
       'Children', states=STATES, depends=DEPENDS,
        help="Add children below the category.")

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('name_parent_exclude',
                Exclude(t, (t.name, Equal), (Coalesce(t.parent, -1), Equal)),
                'The name of a party category must be unique by parent.'),
            ]
        cls._error_messages.update({
                'wrong_name': ('Invalid category name "%%s": You can not use '
                    '"%s" in name field.' % SEPARATOR),
                })
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table_h = TableHandler(cls, module_name)

        super(Category, cls).__register__(module_name)

        # Migration from 4.6: replace unique by exclude
        table_h.drop_constraint('name_parent_uniq')

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
            return domain
        # TODO Handle list
        return [('name',) + tuple(clause[1:])]

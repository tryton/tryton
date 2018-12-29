# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.conditionals import Coalesce
from sql.operators import Equal

from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, Exclude, tree)
from trytond.pyson import Eval

__all__ = ['Category']

STATES = {
    'readonly': ~Eval('active'),
}
DEPENDS = ['active']


class Category(DeactivableMixin, tree(separator=' / '), ModelSQL, ModelView):
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
                'party.msg_category_name_unique'),
            ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Category, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 4.6: replace unique by exclude
        table_h.drop_constraint('name_parent_uniq')

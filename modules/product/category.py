#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields

__all__ = ['Category']


class Category(ModelSQL, ModelView):
    "Product Category"
    __name__ = "product.category"
    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One('product.category', 'Parent', select=True)
    childs = fields.One2Many('product.category', 'parent',
            string='Children')

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def validate(cls, categories):
        super(Category, cls).validate(categories)
        cls.check_recursion(categories, rec_name='name')

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + ' / ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if isinstance(clause[2], basestring):
            values = clause[2].split('/')
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name.strip()))
                field = 'parent.' + field
        else:
            domain = [('name',) + tuple(clause[1:])]
        ids = [w.id for w in cls.search(domain, order=[])]
        return [('parent', 'child_of', ids)]

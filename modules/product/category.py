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

        cls._constraints += [
            ('check_recursion', 'recursive_categories'),
            ]
        cls._error_messages.update({
                'recursive_categories': \
                    'You can not create recursive categories!',
                })

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + ' / ' + self.name
        else:
            return self.name

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields, tree
from trytond.pyson import PYSONEncoder


class Category(tree(separator=' / '), ModelSQL, ModelView):
    "Product Category"
    __name__ = "product.category"
    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One(
        'product.category', "Parent", select=True,
        help="Used to add structure above the category.")
    childs = fields.One2Many(
        'product.category', 'parent', string="Children",
        help="Used to add structure below the category.")
    templates = fields.Many2Many(
        'product.template-product.category', 'category', 'template',
        "Products")

    @classmethod
    def __setup__(cls):
        super(Category, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))
        cls._buttons.update({
                'add_products': {
                    'icon': 'tryton-add',
                    },
                })

    @classmethod
    @ModelView.button_action('product.act_category_product')
    def add_products(cls, categories):
        return {
            'res_id': [categories[0].id],
            'pyson_domain': PYSONEncoder().encode(
                [('id', '=', categories[0].id)]),
             }

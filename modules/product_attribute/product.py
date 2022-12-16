# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, DictSchemaMixin, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class AttributeSet(ModelSQL, ModelView, metaclass=PoolMeta):
    "Product Attribute Set"
    __name__ = 'product.attribute.set'
    name = fields.Char('Name', required=True, translate=True,
        help="The main identifier of product attribute set.")
    attributes = fields.Many2Many('product.attribute-product.attribute-set',
        'attribute_set', 'attribute', 'Attributes',
        help="Add attributes to the set.")


class Attribute(DictSchemaMixin, ModelSQL, ModelView, metaclass=PoolMeta):
    "Product Attribute"
    __name__ = 'product.attribute'
    sets = fields.Many2Many('product.attribute-product.attribute-set',
        'attribute', 'attribute_set', 'Sets',
        help="Add sets to the attribute.")


class AttributeAttributeSet(ModelSQL, metaclass=PoolMeta):
    "Product Attribute - Set"
    __name__ = 'product.attribute-product.attribute-set'
    attribute = fields.Many2One('product.attribute', 'Attribute',
        ondelete='CASCADE', select=True, required=True)
    attribute_set = fields.Many2One('product.attribute.set', 'Set',
        ondelete='CASCADE', select=True, required=True)


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    attribute_set = fields.Many2One('product.attribute.set', 'Attribute Set',
        help="Select a set of attributes to apply on the variants.")


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    attributes = fields.Dict('product.attribute', 'Attributes',
        domain=[
            ('sets', '=', Eval('_parent_template', {}).get('attribute_set',
                    Eval('attribute_set', -1))),
            ],
        states={
            'readonly': (~Eval('attribute_set')
                & ~Eval('_parent_template', {}).get('attribute_set')),
            },
        depends=['attribute_set'],
        help="Add attributes to the variant.")

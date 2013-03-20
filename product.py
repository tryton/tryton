#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, DictSchemaMixin, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

__metaclass__ = PoolMeta
__all__ = ['ProductAttributeSet', 'ProductAttribute',
    'ProductAttributeAttributeSet', 'Template', 'Product']


class ProductAttributeSet(ModelSQL, ModelView):
    "Product Attribute Set"
    __name__ = 'product.attribute.set'
    name = fields.Char('Name', required=True, translate=True)
    attributes = fields.Many2Many('product.attribute-product.attribute-set',
        'attribute_set', 'attribute', 'Attributes')


class ProductAttribute(DictSchemaMixin, ModelSQL, ModelView):
    "Product Attribute"
    __name__ = 'product.attribute'
    sets = fields.Many2Many('product.attribute-product.attribute-set',
        'attribute', 'attribute_set', 'Sets')


class ProductAttributeAttributeSet(ModelSQL):
    "Product Attribute - Set"
    __name__ = 'product.attribute-product.attribute-set'
    attribute = fields.Many2One('product.attribute', 'Attribute',
        ondelete='CASCADE', select=True, required=True)
    attribute_set = fields.Many2One('product.attribute.set', 'Set',
        ondelete='CASCADE', select=True, required=True)


class Template:
    __name__ = 'product.template'
    attribute_set = fields.Many2One('product.attribute.set', 'Set')


class Product:
    __name__ = 'product.product'
    attributes = fields.Dict('product.attribute', 'Attributes',
        domain=[
            ('sets', '=',
                Eval('_parent_template', {}).get('attribute_set', -1)),
            ],
        states={
            'readonly': ~Eval('_parent_template', {}),
            })

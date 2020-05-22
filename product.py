# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    locations = fields.One2Many('stock.product.location', 'template',
        "Default Locations",
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            },
        depends=['type'])

    @classmethod
    def copy(cls, templates, default=None):
        pool = Pool()
        ProductLocation = pool.get('stock.product.location')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_locations = 'locations' not in default
        default.setdefault('locations', None)
        new_templates = super().copy(templates, default)
        if copy_locations:
            old2new = {}
            to_copy = []
            for template, new_template in zip(templates, new_templates):
                to_copy.extend(l for l in template.locations if not l.product)
                old2new[template.id] = new_template.id
            if to_copy:
                ProductLocation.copy(to_copy, {
                        'template': lambda d: old2new[d['template']],
                        })
        return new_templates


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    locations = fields.One2Many('stock.product.location', 'product',
        "Default Locations",
        domain=[
            ('template', '=', Eval('template')),
            ],
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            },
        depends=['type', 'template'])

    @classmethod
    def copy(cls, products, default=None):
        pool = Pool()
        ProductLocation = pool.get('stock.product.location')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_locations = 'locations' not in default
        if 'template' in default:
            default.setdefault('locations', None)
        new_products = super().copy(products, default)
        if 'template' in default and copy_locations:
            template2new = {}
            product2new = {}
            to_copy = []
            for product, new_product in zip(products, new_products):
                if product.locations:
                    to_copy.extend(product.locations)
                    template2new[product.template.id] = new_product.template.id
                    product2new[product.id] = new_product.id
            if to_copy:
                ProductLocation.copy(to_copy, {
                        'product': lambda d: product2new[d['product']],
                        'template': lambda d: template2new[d['template']],
                        })
        return new_products

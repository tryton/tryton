# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    location_places = fields.One2Many(
        'stock.product.location.place', 'template',
        "Places per Location",
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            })

    def get_place(self, location):
        for place in self.location_places:
            if (not place.product
                    and place.location == location):
                return place

    @classmethod
    def copy(cls, templates, default=None):
        pool = Pool()
        ProductLocationPlace = pool.get('stock.product.location.place')
        default = default.copy() if default is not None else {}

        copy_location_places = 'location_places' not in default
        default.setdefault('location_places', None)
        new_templates = super().copy(templates, default=default)
        if copy_location_places:
            old2new, to_copy = {}, []
            for template, new_template in zip(templates, new_templates):
                to_copy.extend(
                    p for p in template.location_places if not p.product)
                old2new[template.id] = new_template.id
            if to_copy:
                ProductLocationPlace.copy(to_copy, {
                        'template': lambda d: old2new[d['template']],
                        })
        return new_templates


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    location_places = fields.One2Many(
        'stock.product.location.place', 'product',
        "Places per Location",
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            })

    def get_place(self, location):
        for place in self.location_places:
            if place.location == location:
                return place
        return self.template.get_place(location)

    @classmethod
    def copy(cls, products, default=None):
        pool = Pool()
        ProductLocationPlace = pool.get('stock.product.location.place')
        default = default.copy() if default is not None else {}

        copy_location_places = 'location_places' not in default
        if 'template' in default:
            default.setdefault('location_places', None)
        new_products = super().copy(products, default=default)
        if 'template' in default and copy_location_places:
            template2new, product2new, to_copy = {}, {}, []
            for product, new_product in zip(products, new_products):
                if product.location_places:
                    to_copy.extend(product.location_places)
                    template2new[product.template.id] = new_product.template.id
                    product2new[product.id] = new_product.id
            if to_copy:
                ProductLocationPlace.copy(to_copy, {
                        'product': lambda d: product2new[d['product']],
                        'template': lambda d: template2new[d['template']],
                        })
        return new_products

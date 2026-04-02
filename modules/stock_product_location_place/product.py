# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.modules.product import (
    copy_product_filtered, copy_template_filtered)
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Template(copy_template_filtered('location_places'), metaclass=PoolMeta):
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


class Product(copy_product_filtered('location_places'), metaclass=PoolMeta):
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

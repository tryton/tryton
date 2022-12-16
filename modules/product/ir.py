# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.config import config
from trytond.model import fields
from trytond.pool import PoolMeta

price_decimal = config.getint('product', 'price_decimal', default=4)


class Configuration(metaclass=PoolMeta):
    __name__ = 'ir.configuration'
    product_price_decimal = fields.Integer("Product Price Decimal")

    @classmethod
    def default_product_price_decimal(cls):
        return price_decimal

    def check(self):
        super().check()
        if self.product_price_decimal != price_decimal:
            raise ValueError(
                "The price_decimal %s in [product] configuration section "
                "is different from the value %s in 'ir.configuration'." % (
                    price_decimal, self.product_price_decimal))

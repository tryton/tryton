# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import ir
from . import uom
from . import category
from . import product
from . import configuration
from .product import price_digits, round_price
from .uom import uom_conversion_digits

__all__ = [price_digits, round_price, uom_conversion_digits]


def register():
    Pool.register(
        ir.Configuration,
        uom.UomCategory,
        uom.Uom,
        category.Category,
        product.Template,
        product.Product,
        product.ProductIdentifier,
        product.ProductListPrice,
        # before ProductCostPrice for migration
        product.ProductCostPriceMethod,
        product.ProductCostPrice,
        product.TemplateCategory,
        product.TemplateCategoryAll,
        configuration.Configuration,
        configuration.ConfigurationDefaultCostPriceMethod,
        module='product', type_='model')

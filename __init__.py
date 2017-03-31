# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .uom import *
from .category import *
from .product import *
from .configuration import *


def register():
    Pool.register(
        UomCategory,
        Uom,
        Category,
        Template,
        Product,
        ProductListPrice,
        ProductCostPrice,
        TemplateCategory,
        Configuration,
        ConfigurationDefaultCostPriceMethod,
        module='product', type_='model')

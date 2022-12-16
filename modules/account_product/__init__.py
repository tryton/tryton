# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .product import *
from .configuration import *
from . import account


def register():
    Pool.register(
        ProductConfiguration,
        Category,
        CategoryAccount,
        CategoryCustomerTax,
        CategorySupplierTax,
        account.CreateChartProperties,
        Template,
        TemplateAccount,
        TemplateCustomerTax,
        TemplateSupplierTax,
        Product,
        TemplateAccountCategory,
        TemplateCategoryAll,
        Configuration,
        ConfigurationDefaultAccount,
        module='account_product', type_='model')
    Pool.register(
        account.CreateChart,
        module='account_product', type_='wizard')

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import product
from . import configuration
from . import account
from . import analytic_account


def register():
    Pool.register(
        product.Category,
        product.CategoryAccount,
        product.CategoryCustomerTax,
        product.CategorySupplierTax,
        account.CreateChartProperties,
        product.Template,
        product.Product,
        product.TemplateAccountCategory,
        product.TemplateCategoryAll,
        configuration.Configuration,
        configuration.ConfigurationDefaultAccount,
        module='account_product', type_='model')
    Pool.register(
        account.MoveLine,
        analytic_account.Rule,
        module='account_product', type_='model', depends=['analytic_account'])
    Pool.register(
        account.CreateChart,
        module='account_product', type_='wizard')

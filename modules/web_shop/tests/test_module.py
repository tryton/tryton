# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class WebShopTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Web Shop module'
    module = 'web_shop'
    extras = [
        'account_tax_rule_country', 'product_attribute', 'product_image',
        'sale_price_list']


del ModuleTestCase

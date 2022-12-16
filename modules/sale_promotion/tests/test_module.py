# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class SalePromotionTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Sale Promotion module'
    module = 'sale_promotion'


del ModuleTestCase

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.modules.company.tests import CompanyTestMixin
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ProductionTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Production module'
    module = 'production'

    @with_transaction()
    def test_on_change_with_planned_start_date(self):
        "Test on_change_with_planned_start_date"
        pool = Pool()
        Production = pool.get('production')
        Product = pool.get('product.product')
        LeadTime = pool.get('production.lead_time')

        date = datetime.date(2016, 11, 26)
        product = Product()
        product.lead_times = []
        production = Production()
        production.planned_date = date
        production.product = product

        self.assertEqual(production.on_change_with_planned_start_date(), date)

        lead_time = LeadTime(bom=None, lead_time=None)
        product.lead_times = [lead_time]
        self.assertEqual(production.on_change_with_planned_start_date(), date)

        lead_time.lead_time = datetime.timedelta(1)
        self.assertEqual(
            production.on_change_with_planned_start_date(),
            datetime.date(2016, 11, 25))


del ModuleTestCase

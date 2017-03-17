# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

import unittest
import doctest
from decimal import Decimal

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class CommissionTestCase(ModuleTestCase):
    'Test Commission module'
    module = 'commission'

    @with_transaction()
    def test_plan_category(self):
        "Test plan with category"
        pool = Pool()
        Category = pool.get('product.category')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        Plan = pool.get('commission.plan')

        category = Category(name="Category")
        category.save()

        unit, = Uom.search([('name', '=', 'Unit')])

        company = create_company()
        with set_company(company):
            commission_template = Template(
                name="Commission",
                type='service',
                list_price=Decimal(10),
                cost_price=Decimal(3),
                default_uom=unit,
                products=None,
                )
            commission_template.save()
            commission_product = Product(template=commission_template)
            commission_product.save()
            template = Template(
                name="Template",
                list_price=Decimal(10),
                cost_price=Decimal(3),
                default_uom=unit,
                products=None,
                categories=[category],
                )
            template.save()
            product = Product(template=template)
            product.save()

            plan, = Plan.create([{
                        'name': "Commission Plan",
                        'commission_product': commission_product.id,
                        'lines': [('create', [{
                                        'category': category.id,
                                        'formula': 'amount * 0.8',
                                        }, {
                                        'formula': 'amount',
                                        }])],
                        }])

            self.assertEqual(plan.compute(Decimal(1), product), Decimal('0.8'))

            template.categories = []
            template.save()

            self.assertEqual(plan.compute(Decimal(1), product), Decimal(1))


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CommissionTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_commission.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

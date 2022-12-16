# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool

from trytond.modules.company.tests import (
    create_company, set_company, create_employee)


class TimesheetCostTestCase(ModuleTestCase):
    'Test TimesheetCost module'
    module = 'timesheet_cost'

    @with_transaction()
    def test_compute_cost_price(self):
        'Test compute_cost_price'
        pool = Pool()
        Party = pool.get('party.party')
        EmployeeCostPrice = pool.get('company.employee_cost_price')

        cost_prices = [
            (datetime.date(2011, 1, 1), Decimal(10)),
            (datetime.date(2012, 1, 1), Decimal(15)),
            (datetime.date(2013, 1, 1), Decimal(20)),
            ]
        test_prices = [
            (datetime.date(2010, 1, 1), 0),
            (datetime.date(2011, 1, 1), Decimal(10)),
            (datetime.date(2011, 6, 1), Decimal(10)),
            (datetime.date(2012, 1, 1), Decimal(15)),
            (datetime.date(2012, 6, 1), Decimal(15)),
            (datetime.date(2013, 1, 1), Decimal(20)),
            (datetime.date(2013, 6, 1), Decimal(20)),
            ]
        party = Party(name='Pam Beesly')
        party.save()
        company = create_company()
        with set_company(company):
            employee = create_employee(company)
            for date, cost_price in cost_prices:
                EmployeeCostPrice(
                    employee=employee,
                    date=date,
                    cost_price=cost_price).save()
            for date, cost_price in test_prices:
                self.assertEqual(employee.compute_cost_price(date), cost_price)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        TimesheetCostTestCase))
    return suite

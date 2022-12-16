# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.pool import Pool
from trytond.modules.company.tests import (
    create_company, set_company, create_employee)


class ProductionWorkTimesheetTestCase(ModuleTestCase):
    'Test Production Work Timesheet module'
    module = 'production_work_timesheet'

    def create_work(self, production_state='draft'):
        pool = Pool()
        Work = pool.get('production.work')
        Operation = pool.get('production.routing.operation')
        WorkCenter = pool.get('production.work.center')
        Production = pool.get('production')

        work_center = WorkCenter(name='Work Center')
        work_center.save()

        operation = Operation(name='Operation')
        operation.timesheet_available = True
        operation.save()

        production = Production(state=production_state)
        production.save()

        work = Work(
            production=production,
            operation=operation,
            work_center=work_center)
        return work

    @with_transaction()
    def test_set_timesheet_work(self):
        'Test _set_timesheet_work'
        pool = Pool()
        Work = pool.get('production.work')
        TimesheetWork = pool.get('timesheet.work')
        Date = pool.get('ir.date')

        company = create_company()
        with set_company(company):
            # Test on create
            work = self.create_work()
            work.save()
            self.assertEqual(len(work.timesheet_works), 1)

            # Test on write
            work.operation.timesheet_available = False
            work.operation.save()
            work.sequence = 1  # trigger write
            work.save()
            self.assertFalse(work.timesheet_works)

            # Test delete
            work = self.create_work()
            work.save()
            timesheet_work, = work.timesheet_works
            timesheet_work_id = timesheet_work.id
            Work.delete([work])
            self.assertFalse(
                TimesheetWork.search([('id', '=', timesheet_work_id)]))

            # Test create as done
            work = self.create_work(production_state='done')
            work.save()
            timesheet_work, = work.timesheet_works
            self.assertEqual(timesheet_work.timesheet_end_date, Date.today())

            # Set write as done
            work = self.create_work()
            work.save()
            work.state = 'done'
            work.save()
            timesheet_work, = work.timesheet_works
            self.assertEqual(timesheet_work.timesheet_end_date, Date.today())

    @with_transaction()
    def test_timesheet_lines(self):
        'Test timesheet_lines'
        pool = Pool()
        TimesheetLine = pool.get('timesheet.line')

        company = create_company()
        with set_company(company):
            work = self.create_work()
            work.save()

            employee = create_employee(company)

            timesheet_line = TimesheetLine(
                employee=employee,
                duration=datetime.timedelta(1))

            work.timesheet_lines = [timesheet_line]
            work.save()

            self.assertEqual(len(work.timesheet_lines), 1)


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProductionWorkTimesheetTestCase))
    return suite

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import doctest
import unittest

import trytond.tests.test_tryton
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_checker
from trytond.tests.test_tryton import doctest_teardown
from trytond.transaction import Transaction

from trytond.modules.company.tests import create_company, set_company


class ProjectTestCase(ModuleTestCase):
    'Test Project module'
    module = 'project'

    @with_transaction()
    def test_sum_tree(self):
        'Test sum_tree'
        pool = Pool()
        ProjectWork = pool.get('project.work')

        company = create_company()
        with set_company(company):
            p_work_1, = ProjectWork.create([{
                        'name': 'Work 1',
                        'company': company.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            p_work_1_1, = ProjectWork.create([{
                        'name': 'Work 1 1',
                        'company': company.id,
                        'parent': p_work_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            p_work_1_2, = ProjectWork.create([{
                        'name': 'Work 1 2',
                        'company': company.id,
                        'parent': p_work_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            p_work_1_1_1, = ProjectWork.create([{
                        'name': 'Work 1 1 1',
                        'company': company.id,
                        'parent': p_work_1_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            p_work_1_1_2, = ProjectWork.create([{
                        'name': 'Work 1 1 2',
                        'company': company.id,
                        'parent': p_work_1_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            p_work_1_1_3, = ProjectWork.create([{
                        'name': 'Work 1 1 3',
                        'company': company.id,
                        'parent': p_work_1_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            for work, total_effort in (
                    (p_work_1, 6),
                    (p_work_1_1, 4),
                    (p_work_1_2, 1),
                    (p_work_1_1_1, 1),
                    (p_work_1_1_2, 1),
                    (p_work_1_1_3, 1),
                    ):
                self.assertEqual(work.total_effort,
                    datetime.timedelta(hours=total_effort))

    @with_transaction()
    def test_timesheet_available(self):
        'Test timesheet available'
        pool = Pool()
        ProjectWork = pool.get('project.work')

        company = create_company()
        with set_company(company):
            p_work = ProjectWork()
            p_work.name = 'Project Work'
            p_work.save()

            self.assertFalse(p_work.timesheet_works)

            p_work.timesheet_available = True
            p_work.save()

            self.assertEqual(len(p_work.timesheet_works), 1)

            p_work.timesheet_available = False
            p_work.save()

            self.assertFalse(p_work.timesheet_works)

    @with_transaction(context={'_check_access': True})
    def test_delete_access(self):
        'Test delete_access'
        pool = Pool()
        User = pool.get('res.user')
        Group = pool.get('res.group')
        ModelData = pool.get('ir.model.data')
        ProjectWork = pool.get('project.work')
        TimesheetWork = pool.get('timesheet.work')

        company = create_company()
        with set_company(company):
            project_user = User()
            project_user.login = 'project'
            project_user.company = company
            project_user.main_company = company
            project_group = Group(ModelData.get_id(
                    'project', 'group_project_admin'))
            project_user.groups = [project_group]
            project_user.save()
            with Transaction().set_user(project_user.id):
                p_work = ProjectWork()
                p_work.name = 'Project Work'
                p_work.timesheet_available = True
                p_work.save()

                self.assertEqual(len(p_work.timesheet_works), 1)
                ProjectWork.delete([p_work])
                self.assertEqual(TimesheetWork.search([]), [])

    @with_transaction()
    def test_timesheet_default_work_empty(self):
        "Test timesheet default work with no context"
        pool = Pool()
        ProjectWork = pool.get('project.work')
        TimesheetLine = pool.get('timesheet.line')

        company = create_company()
        with set_company(company):
            p_work = ProjectWork()
            p_work.name = "Work"
            p_work.timesheet_available = True
            p_work.save()

            self.assertFalse(TimesheetLine.default_work())

    @with_transaction()
    def test_timesheet_default_work_single(self):
        "Test timesheet default work with 1 work in context"
        pool = Pool()
        ProjectWork = pool.get('project.work')
        TimesheetLine = pool.get('timesheet.line')

        company = create_company()
        with set_company(company):
            p_work = ProjectWork()
            p_work.name = "Work"
            p_work.timesheet_available = True
            p_work.save()

            with Transaction().set_context({'project.work': [p_work.id]}):
                self.assertEqual(
                    TimesheetLine.default_work(),
                    p_work.timesheet_works[0].id)

    @with_transaction()
    def test_timesheet_default_work_multiple(self):
        "Test timesheet default work with multiple work in context"
        pool = Pool()
        ProjectWork = pool.get('project.work')
        TimesheetLine = pool.get('timesheet.line')

        company = create_company()
        with set_company(company):
            works = ProjectWork.create([
                    {'name': "Work 1", 'timesheet_available': True},
                    {'name': "Work 2", 'timesheet_available': True},
                    ])

            with Transaction().set_context(
                    {'project.work': map(int, works)}):
                self.assertFalse(TimesheetLine.default_work())


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProjectTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_project_status.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class ProjectTestCase(ModuleTestCase):
    'Test Project module'
    module = 'project'

    def setUp(self):
        super(ProjectTestCase, self).setUp()
        trytond.tests.test_tryton.install_module('project')
        self.timesheet_work = POOL.get('timesheet.work')
        self.project_work = POOL.get('project.work')
        self.company = POOL.get('company.company')

    def test0010sum_tree(self):
        'Test sum_tree'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])

            t_work_1, = self.timesheet_work.create([{
                        'name': 'Work 1',
                        'company': company.id,
                        }])
            p_work_1, = self.project_work.create([{
                        'work': t_work_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_1, = self.timesheet_work.create([{
                        'name': 'Work 1 1',
                        'company': company.id,
                        'parent': t_work_1.id,
                        }])
            p_work_1_1, = self.project_work.create([{
                        'work': t_work_1_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_2, = self.timesheet_work.create([{
                        'name': 'Work 1 1',
                        'company': company.id,
                        'parent': t_work_1.id,
                        }])
            p_work_1_2, = self.project_work.create([{
                        'work': t_work_1_2.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_1_1, = self.timesheet_work.create([{
                        'name': 'Work 1 1 1',
                        'company': company.id,
                        'parent': t_work_1_1.id,
                        }])
            p_work_1_1_1, = self.project_work.create([{
                        'work': t_work_1_1_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_1_2, = self.timesheet_work.create([{
                        'name': 'Work 1 1 2',
                        'company': company.id,
                        'parent': t_work_1_1.id,
                        }])
            p_work_1_1_2, = self.project_work.create([{
                        'work': t_work_1_1_2.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_1_3, = self.timesheet_work.create([{
                        'name': 'Work 1 1 2',
                        'company': company.id,
                        'parent': t_work_1_1.id,
                        }])
            p_work_1_1_3, = self.project_work.create([{
                        'work': t_work_1_1_3.id,
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


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProjectTestCase))
    return suite

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class ProjectTestCase(ModuleTestCase):
    'Test Project module'
    module = 'project'

    @with_transaction()
    def test_sum_tree(self):
        'Test sum_tree'
        pool = Pool()
        TimesheetWork = pool.get('timesheet.work')
        ProjectWork = pool.get('project.work')

        company = create_company()
        with set_company(company):
            t_work_1, = TimesheetWork.create([{
                        'name': 'Work 1',
                        'company': company.id,
                        }])
            p_work_1, = ProjectWork.create([{
                        'name': 'Work 1',
                        'company': company.id,
                        'work': t_work_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_1, = TimesheetWork.create([{
                        'name': 'Work 1 1',
                        'company': company.id,
                        'parent': t_work_1.id,
                        }])
            p_work_1_1, = ProjectWork.create([{
                        'name': 'Work 1 1',
                        'company': company.id,
                        'parent': p_work_1.id,
                        'work': t_work_1_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_2, = TimesheetWork.create([{
                        'name': 'Work 1 1',
                        'company': company.id,
                        'parent': t_work_1.id,
                        }])
            p_work_1_2, = ProjectWork.create([{
                        'name': 'Work 1 2',
                        'company': company.id,
                        'parent': p_work_1.id,
                        'work': t_work_1_2.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_1_1, = TimesheetWork.create([{
                        'name': 'Work 1 1 1',
                        'company': company.id,
                        'parent': t_work_1_1.id,
                        }])
            p_work_1_1_1, = ProjectWork.create([{
                        'name': 'Work 1 1 1',
                        'company': company.id,
                        'parent': p_work_1_1.id,
                        'work': t_work_1_1_1.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_1_2, = TimesheetWork.create([{
                        'name': 'Work 1 1 2',
                        'company': company.id,
                        'parent': t_work_1_1.id,
                        }])
            p_work_1_1_2, = ProjectWork.create([{
                        'name': 'Work 1 1 2',
                        'company': company.id,
                        'parent': p_work_1_1.id,
                        'work': t_work_1_1_2.id,
                        'effort_duration': datetime.timedelta(hours=1),
                        }])

            t_work_1_1_3, = TimesheetWork.create([{
                        'name': 'Work 1 1 3',
                        'company': company.id,
                        'parent': t_work_1_1.id,
                        }])
            p_work_1_1_3, = ProjectWork.create([{
                        'name': 'Work 1 1 3',
                        'company': company.id,
                        'parent': p_work_1_1.id,
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
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProjectTestCase))
    return suite

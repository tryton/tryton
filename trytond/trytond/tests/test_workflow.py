# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool


class WorkflowTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    # TODO add test for Workflow.transition
    @with_transaction()
    def test_transition(self):
        'Test transition'
        pool = Pool()
        Workflowed = pool.get('test.workflowed')

        wkf, = Workflowed.create([{}])

        Workflowed.run([wkf])
        self.assertEqual(wkf.state, 'running')

        wkf.state = 'end'
        wkf.save()
        Workflowed.run([wkf])
        self.assertEqual(wkf.state, 'end')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(WorkflowTestCase)

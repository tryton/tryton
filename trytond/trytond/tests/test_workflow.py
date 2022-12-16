# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.transaction import Transaction
from trytond.tests.test_tryton import (POOL, DB_NAME, USER, CONTEXT,
    install_module)


class WorkflowTestCase(unittest.TestCase):

    def setUp(self):
        install_module('tests')
        self.workflow = POOL.get('test.workflowed')

    # TODO add test for Workflow.transition
    def test0010transition(self):
        'Test transition'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            wkf, = self.workflow.create([{}])

            self.workflow.run([wkf])
            self.assertEqual(wkf.state, 'running')

            wkf.state = 'end'
            wkf.save()
            self.workflow.run([wkf])
            self.assertEqual(wkf.state, 'end')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(WorkflowTestCase)

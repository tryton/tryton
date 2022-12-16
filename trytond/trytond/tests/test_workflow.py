# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.transaction import Transaction
from trytond.tests.test_tryton import (POOL, DB_NAME, USER, CONTEXT,
    install_module)


class WorkflowTestCase(unittest.TestCase):

    def setUp(self):
        install_module('test')
        self.workflow_obj = POOL.get('test.workflowed')

    # TODO add test for Workflow.transition
    def test0010transition(self):
        'Test transition'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            wkf_id = self.workflow_obj.create({})

            self.workflow_obj.run([wkf_id])
            self.assertEqual(self.workflow_obj.read(wkf_id)['state'],
                'running')

            self.workflow_obj.write(wkf_id, {
                    'state': 'end',
                    })
            self.workflow_obj.run([wkf_id])
            self.assertEqual(self.workflow_obj.read(wkf_id)['state'], 'end')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(WorkflowTestCase)


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())

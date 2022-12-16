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

    def test0010object_creation(self):
        'Test workflow object creation'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            wkf_id = self.workflow_obj.create({
                    'name': 'value = 3',
                    'value': 3,
                    })
            self.assertEqual(self.workflow_obj.read(wkf_id)['state'], 'Start')

            wkf_id = self.workflow_obj.create({
                    'name': 'value = 10',
                    'value': 10,
                    })
            self.assertEqual(self.workflow_obj.read(wkf_id)['state'], 'Middle')

            wkf_id = self.workflow_obj.create({
                    'name': 'value = 6',
                    'value': 6,
                    })
            self.assertEqual(self.workflow_obj.read(wkf_id)['state'], 'End')

            transaction.cursor.rollback()

    def test0020object_modification(self):
        'Test workflow object modification'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            wkf_id = self.workflow_obj.create({
                    'name': 'value = 3',
                    'value': 3,
                    })
            wkf_id = self.workflow_obj.create({
                    'name': 'value = 10',
                    'value': 10,
                    })

            wkf_id, = self.workflow_obj.search([('name', '=', 'value = 3')])
            self.workflow_obj.write(wkf_id, {'value': 11})
            self.assertEqual(self.workflow_obj.read(wkf_id)['state'], 'Middle')

            wkf_id, = self.workflow_obj.search([('name', '=', 'value = 10')])
            self.workflow_obj.write(wkf_id, {'value': 6})
            self.assertEqual(self.workflow_obj.read(wkf_id)['state'], 'End')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(WorkflowTestCase)


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.config import CONFIG
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
    install_module


class ModelSQLTestCase(unittest.TestCase):
    '''
    Test ModelSQL
    '''

    def setUp(self):
        install_module('test')
        self.modelsql = POOL.get('test.modelsql')

    def test0010required_field_missing(self):
        '''
        Test error message when a required field is missing.
        '''
        if CONFIG['db_type'] not in ('postgresql', 'mysql'):
            # SQLite not concerned because tryton don't set "NOT NULL"
            # constraint: 'ALTER TABLE' don't support NOT NULL constraint
            # without default value
            return
        fields = {
            'desc': '',
            'integer': 0,
            }
        for key, value in fields.iteritems():
            with Transaction().start(DB_NAME, USER, context=CONTEXT):
                try:
                    self.modelsql.create([{key: value}])
                except UserError, err:
                    # message must not quote key
                    msg = "'%s' not missing but quoted in error: '%s'" % (key,
                            err.message)
                    self.assertTrue(key not in err.message, msg)
                    continue
                self.fail('UserError should be caught')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelSQLTestCase)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())

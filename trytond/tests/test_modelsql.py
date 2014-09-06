# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest
import time

from trytond import backend
from trytond.exceptions import UserError, ConcurrencyException
from trytond.transaction import Transaction
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
    install_module


class ModelSQLTestCase(unittest.TestCase):
    'Test ModelSQL'

    def setUp(self):
        install_module('tests')
        self.modelsql = POOL.get('test.modelsql')
        self.modelsql_timestamp = POOL.get('test.modelsql.timestamp')

    @unittest.skipIf(backend.name() == 'sqlite',
        'SQLite not concerned because tryton don\'t set "NOT NULL"'
        'constraint: "ALTER TABLE" don\'t support NOT NULL constraint'
        'without default value')
    def test0010required_field_missing(self):
        'Test error message when a required field is missing'
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

    def test0020check_timestamp(self):
        'Test check timestamp'
        # cursor must be committed between each changes otherwise NOW() returns
        # always the same timestamp.
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cursor = transaction.cursor
            record, = self.modelsql_timestamp.create([{}])
            cursor.commit()

            timestamp = self.modelsql_timestamp.read([record.id],
                ['_timestamp'])[0]['_timestamp']

            if backend.name() in ('sqlite', 'mysql'):
                # timestamp precision of sqlite is the second
                time.sleep(1)

            self.modelsql_timestamp.write([record], {})
            cursor.commit()

            transaction.timestamp[str(record)] = timestamp
            self.assertRaises(ConcurrencyException,
                self.modelsql_timestamp.write, [record], {})

            transaction.timestamp[str(record)] = timestamp
            self.assertRaises(ConcurrencyException,
                self.modelsql_timestamp.delete, [record])

            transaction.timestamp.pop(str(record), None)
            self.modelsql_timestamp.write([record], {})
            cursor.commit()
            self.modelsql_timestamp.delete([record])
            cursor.commit()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelSQLTestCase)

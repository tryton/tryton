#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.backend.sqlite.database import Database as SQLiteDatabase


class PurchaseTestCase(unittest.TestCase):
    '''
    Test Purchase module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('purchase')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('purchase')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()


def doctest_dropdb(test):
    database = SQLiteDatabase().connect()
    cursor = database.cursor(autocommit=True)
    try:
        database.drop(cursor, ':memory:')
        cursor.commit()
    finally:
        cursor.close()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        PurchaseTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_purchase.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='UTF-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())

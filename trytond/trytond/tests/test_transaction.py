#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT, install_module
from trytond.transaction import Transaction


def empty_transaction(*args, **kwargs):
    '''
    Just starts a transaction in the context manager and returns `True`
    and stops transaction for the given arguments.

    All positional arguments are passed to `start` method of transaction
    '''
    with Transaction().start(*args, **kwargs):
        return True


def manipulate_cursor(*args, **kwargs):
    '''
    Just start a transaction in the context manager and close the cursor
    during the transaction so that the cursor.close in the stop fails
    '''
    with Transaction().start(*args, **kwargs) as transaction:
        transaction.cursor.close()
        transaction.cursor = None
        return True


class TransactionTestCase(unittest.TestCase):
    '''
    Test the Transaction Context manager
    '''

    def setUp(self):
        install_module('test')

    def test0010nonexistdb(self):
        '''
        Attempt opening a transaction with a non existant DB and ensure that
        it stops cleanly and allows starting of next transaction
        '''
        self.assertRaises(
            Exception, empty_transaction, "Non existant DB", USER,
            context=CONTEXT)
        self.assertTrue(empty_transaction(DB_NAME, USER, context=CONTEXT))

    def test0020cursorclose(self):
        '''
        Manipulate the cursor during the transaction so that the close in
        transaction stop fails. Ensure that this does not affect opening of
        another transaction
        '''
        self.assertRaises(
            Exception, manipulate_cursor, DB_NAME, USER, context=CONTEXT)
        self.assertTrue(empty_transaction(DB_NAME, USER, context=CONTEXT))


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TransactionTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)

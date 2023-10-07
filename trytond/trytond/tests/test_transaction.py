# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from unittest.mock import Mock

from trytond import backend
from trytond.tests.test_tryton import CONTEXT, DB_NAME, USER, activate_module
from trytond.transaction import Transaction


def empty_transaction(*args, **kwargs):
    '''
    Just starts a transaction in the context manager and returns `True`
    and stops transaction for the given arguments.

    All positional arguments are passed to `start` method of transaction
    '''
    with Transaction().start(*args, **kwargs):
        return True


class TransactionTestCase(unittest.TestCase):
    'Test the Transaction Context manager'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def test_nonexistdb(self):
        '''Attempt opening a transaction with a non existant DB
        and ensure that it stops cleanly and allows starting of next
        transaction'''
        self.assertRaises(
            Exception, empty_transaction, "Non existant DB", USER,
            context=CONTEXT)
        self.assertTrue(empty_transaction(DB_NAME, USER, context=CONTEXT))

    def test_set_user(self):
        'Test set_user'
        with Transaction().start(DB_NAME, USER, context=CONTEXT) \
                as transaction:
            self.assertEqual(transaction.user, USER)
            self.assertEqual(transaction.context.get('user'), None)

            with Transaction().set_user(0):
                self.assertEqual(transaction.user, 0)
                self.assertEqual(transaction.context.get('user'), None)

            with Transaction().set_user(0, set_context=True):
                self.assertEqual(transaction.user, 0)
                self.assertEqual(transaction.context.get('user'), USER)

                # Nested same set_user should keep original context user
                with Transaction().set_user(0, set_context=True):
                    self.assertEqual(transaction.user, 0)
                    self.assertEqual(transaction.context.get('user'), USER)

                # Unset user context
                with Transaction().set_user(0, set_context=False):
                    self.assertEqual(transaction.user, 0)
                    self.assertEqual(transaction.context.get('user'), None)

            # set context for non root
            self.assertRaises(ValueError,
                Transaction().set_user, 2, set_context=True)

            # not set context for non root
            with Transaction().set_user(2):
                self.assertEqual(transaction.user, 2)

    def test_stacked_transactions(self):
        'Test that transactions are stacked / unstacked correctly'
        with Transaction().start(DB_NAME, USER, context=CONTEXT) \
                as transaction:
            with transaction.new_transaction() as new_transaction:
                self.assertIsNot(new_transaction, transaction)
                self.assertIsNot(Transaction(), transaction)
                self.assertIs(Transaction(), new_transaction)
            self.assertIs(Transaction(), transaction)

    def test_two_phase_commit(self):
        # A successful transaction
        dm = Mock()
        with Transaction().start(DB_NAME, USER, context=CONTEXT) \
                as transaction:
            transaction.join(dm)

        dm.tpc_begin.assert_called_once_with(transaction)
        dm.commit.assert_called_once_with(transaction)
        dm.tpc_vote.assert_called_once_with(transaction)
        dm.tpc_abort.assert_not_called()
        dm.tpc_finish.assert_called_once_with(transaction)

        # Failing in the datamanager
        dm.reset_mock()
        dm.tpc_vote.side_effect = ValueError('Failing the datamanager')
        try:
            with Transaction().start(DB_NAME, USER, context=CONTEXT) \
                    as transaction:
                transaction.join(dm)
        except ValueError:
            pass

        dm.tpc_begin.assert_called_once_with(transaction)
        dm.commit.assert_called_once_with(transaction)
        dm.tpc_vote.assert_called_once_with(transaction)
        dm.tpc_abort.assert_called_once_with(transaction)
        dm.tpc_finish.assert_not_called()

        # Failing in tryton
        dm.reset_mock()
        try:
            with Transaction().start(DB_NAME, USER, context=CONTEXT) \
                    as transaction:
                transaction.join(dm)
                raise ValueError('Failing in tryton')
        except ValueError:
            pass

        dm.tpc_begin.assert_not_called()
        dm.commit.assert_not_called()
        dm.tpc_vote.assert_not_called()
        dm.tpc_abort.assert_called_once_with(transaction)
        dm.tpc_finish.assert_not_called()

    @unittest.skipUnless(backend.name == 'postgresql', "Test pg_settings")
    def test_postgresl_statement_timeout(self):
        get_timeout = (
            "SELECT setting FROM pg_settings "
            "WHERE name='statement_timeout'")

        with Transaction().start(DB_NAME, USER) as transaction:
            cursor = transaction.connection.cursor()
            cursor.execute(get_timeout)
            self.assertEqual('0', cursor.fetchone()[0])

        with Transaction().start(DB_NAME, USER, timeout=1) as transaction:
            cursor = transaction.connection.cursor()
            cursor.execute(get_timeout)
            self.assertEqual('1000', cursor.fetchone()[0])

    @unittest.skipUnless(backend.name == 'postgresql', "Use pg_sleep")
    def test_postgresql_statement_timeout_exception(self):
        with self.assertRaises(backend.DatabaseTimeoutError):
            with Transaction().start(DB_NAME, USER, timeout=1) as transaction:
                cursor = transaction.connection.cursor()
                cursor.execute("SELECT pg_sleep(2)")

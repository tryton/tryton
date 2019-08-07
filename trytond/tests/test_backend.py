# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

from sql import Select
from sql.functions import CurrentTimestamp, ToChar

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction


class BackendTestCase(unittest.TestCase):
    "Test the backend"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_current_timestamp_static_transaction(self):
        "Test CURRENT_TIMESTAMP is static during transaction"
        query = Select([CurrentTimestamp()])
        cursor = Transaction().connection.cursor()

        cursor.execute(*query)
        current, = cursor.fetchone()
        cursor.execute(*query)
        second, = cursor.fetchone()

        self.assertEqual(current, second)

    @with_transaction()
    def test_current_timestamp_reset_after_commit(self):
        "Test CURRENT_TIMESTAMP is reset after commit"
        query = Select([CurrentTimestamp()])
        cursor = Transaction().connection.cursor()

        cursor.execute(*query)
        current, = cursor.fetchone()
        Transaction().commit()
        cursor.execute(*query)
        second, = cursor.fetchone()

        self.assertNotEqual(current, second)

    @with_transaction()
    def test_current_timestamp_different_transaction(self):
        "Test CURRENT_TIMESTAMP is different per transaction"
        query = Select([CurrentTimestamp()])
        cursor = Transaction().connection.cursor()

        cursor.execute(*query)
        current, = cursor.fetchone()

        with Transaction().new_transaction() as transaction:
            cursor = transaction.connection.cursor()
            cursor.execute(*query)
            second, = cursor.fetchone()

        self.assertNotEqual(current, second)

    @with_transaction()
    def test_to_char_datetime(self):
        "Test TO_CHAR with datetime"
        now = datetime.datetime.now()
        query = Select([ToChar(now, 'YYYYMMDD HH24:MI:SS.US')])
        cursor = Transaction().connection.cursor()

        cursor.execute(*query)
        text, = cursor.fetchone()

        self.assertEqual(text, now.strftime('%Y%m%d %H:%M:%S.%f'))

    @with_transaction()
    def test_to_char_date(self):
        "Test TO_CHAR with date"
        today = datetime.date.today()
        query = Select([ToChar(today, 'YYYY-MM-DD')])
        cursor = Transaction().connection.cursor()

        cursor.execute(*query)
        text, = cursor.fetchone()

        self.assertEqual(text, today.strftime('%Y-%m-%d'))


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(BackendTestCase)

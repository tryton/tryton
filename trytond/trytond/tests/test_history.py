#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
import datetime

from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.config import CONFIG


class HistoryTestCase(unittest.TestCase):
    'Test History'

    def setUp(self):
        install_module('tests')

    def test0010read(self):
        'Test read history'
        History = POOL.get('test.history')

        # Create some history entry
        # It is needed to commit to have different timestamps

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=1)
            history.save()
            history_id = history.id
            first = history.create_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            history.value = 2
            history.save()
            second = history.write_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            history.value = 3
            history.save()
            third = history.write_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for timestamp, value in [
                    (first, 1),
                    (second, 2),
                    (third, 3),
                    (datetime.datetime.now(), 3),
                    (datetime.datetime.max, 3),
                    ]:
                with Transaction().set_context(_datetime=timestamp):
                    history = History(history_id)
                    self.assertEqual(history.value, value)

            with Transaction().set_context(_datetime=datetime.datetime.min):
                self.assertRaises(UserError, History.read, [history_id])

    @unittest.skipIf(CONFIG['db_type'] in ('sqlite', 'mysql'),
        'now() is not the start of the transaction')
    def test0020read_same_timestamp(self):
        'Test read history with same timestamp'
        History = POOL.get('test.history')

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=1)
            history.save()
            history_id = history.id
            first = history.create_date

            history.value = 2
            history.save()
            second = history.write_date

            self.assertEqual(first, second)

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            history.value = 3
            history.save()
            third = history.write_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for timestamp, value in [
                    (first, 2),
                    (third, 3),
                    ]:
                with Transaction().set_context(_datetime=timestamp):
                    history = History(history_id)
                    self.assertEqual(history.value, value)

    def test0030history_revisions(self):
        'Test history revisions'
        History = POOL.get('test.history')

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=1)
            history.save()
            history_id = history.id
            first = history.create_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            history.value = 2
            history.save()
            second = history.write_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            history.value = 3
            history.save()
            third = history.write_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            revisions = History.history_revisions([history_id])
            self.assertEqual(revisions, [
                    (third, history_id, u'Administrator'),
                    (second, history_id, u'Administrator'),
                    (first, history_id, u'Administrator'),
                    ])

    def test0040restore_history(self):
        'Test restore history'
        History = POOL.get('test.history')

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=1)
            history.save()
            history_id = history.id
            first = history.create_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            history.value = 2
            history.save()

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            History.restore_history([history_id], first)
            history = History(history_id)
            self.assertEqual(history.value, 1)

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            History.restore_history([history_id], datetime.datetime.min)
            self.assertRaises(UserError, History.read, [history_id])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(HistoryTestCase)

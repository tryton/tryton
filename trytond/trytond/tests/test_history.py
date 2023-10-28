# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest
from unittest.mock import patch

from trytond import backend
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction


class HistoryTestCase(unittest.TestCase):
    'Test History'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def tearDown(self):
        pool = Pool()
        History = pool.get('test.history')
        HistoryLine = pool.get('test.history.line')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        for Model in [History, HistoryLine]:
            table = Model.__table__()
            history_table = Model.__table_history__()
            cursor.execute(*table.delete())
            cursor.execute(*history_table.delete())
        transaction.commit()

    @with_transaction()
    def test_read(self):
        'Test read history'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()

        # Create some history entry
        # It is needed to commit to have different timestamps
        history = History(value=1)
        history.save()
        history_id = history.id
        first = history.create_date

        transaction.commit()

        history = History(history_id)
        history.value = 2
        history.save()
        second = history.write_date

        transaction.commit()

        history = History(history_id)
        history.value = 3
        history.save()
        third = history.write_date

        transaction.commit()

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
            with self.assertRaises(AccessError):
                History.read([history_id], ['value'])

    @unittest.skipUnless(backend.name == 'postgresql',
        'CURRENT_TIMESTAMP as transaction_timestamp is specific to postgresql')
    @with_transaction()
    def test_read_same_timestamp(self):
        'Test read history with same timestamp'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()

        history = History(value=1)
        history.save()
        history_id = history.id
        first = history.create_date

        history.value = 2
        history.save()
        second = history.write_date

        self.assertEqual(first, second)

        transaction.commit()

        history = History(history_id)
        history.value = 3
        history.save()
        third = history.write_date

        transaction.commit()

        for timestamp, value in [
                (first, 2),
                (third, 3),
                ]:
            with Transaction().set_context(_datetime=timestamp):
                history = History(history_id)
                self.assertEqual(history.value, value)

    @with_transaction()
    def test_history_revisions(self):
        'Test history revisions'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()

        history = History(value=1)
        history.save()
        history_id = history.id
        first = history.create_date

        transaction.commit()

        history = History(history_id)
        history.value = 2
        history.save()
        second = history.write_date

        transaction.commit()

        history = History(history_id)
        history.value = 3
        history.save()
        third = history.write_date

        transaction.commit()

        revisions = History.history_revisions([history_id])
        self.assertEqual(revisions, [
                (third, history_id, 'Administrator'),
                (second, history_id, 'Administrator'),
                (first, history_id, 'Administrator'),
                ])

    @with_transaction()
    def test_restore_history(self):
        'Test restore history'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()

        history = History(value=1)
        history.save()
        history_id = history.id
        first = history.create_date

        transaction.commit()

        history = History(history_id)
        history.value = 2
        history.save()

        transaction.commit()

        History.restore_history([history_id], first)
        history = History(history_id)
        self.assertEqual(history.value, 1)

        transaction.rollback()

        History.restore_history([history_id], datetime.datetime.min)
        with self.assertRaises(AccessError):
            History.read([history_id], ['value'])

        transaction.rollback()

        History.delete([History(history_id)])

        transaction.commit()

        History.restore_history([history_id], datetime.datetime.max)
        with self.assertRaises(AccessError):
            History.read([history_id], ['value'])

    @with_transaction()
    def test_restore_history_before(self):
        'Test restore history before'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()

        history = History(value=1)
        history.save()
        history_id = history.id

        transaction.commit()

        history = History(history_id)
        history.value = 2
        history.save()
        second = history.write_date

        transaction.commit()

        history = History(history_id)
        history.value = 3
        history.save()

        transaction.commit()

        History.restore_history_before([history_id], second)
        history = History(history_id)
        self.assertEqual(history.value, 1)

    @unittest.skipUnless(backend.name == 'postgresql',
        'CURRENT_TIMESTAMP as transaction_timestamp is specific to postgresql')
    @with_transaction()
    def test_restore_history_same_timestamp(self):
        'Test restore history with same timestamp'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()

        history = History(value=1)
        history.save()
        history_id = history.id
        first = history.create_date
        history.value = 2
        history.save()
        second = history.create_date

        self.assertEqual(first, second)

        transaction.commit()

        history = History(history_id)
        history.value = 3
        history.save()

        transaction.commit()

        History.restore_history([history_id], first)
        history = History(history_id)
        self.assertEqual(history.value, 2)

    @with_transaction()
    def test_search_historical_records_no_window_functions(self):
        database = Transaction().database
        with patch.object(database, 'has_window_functions') as has_wf:
            has_wf.return_value = False
            self._test_search_historical_records()

    @with_transaction()
    def test_search_historical_records(self):
        self._test_search_historical_records()

    def _test_search_historical_records(self):
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()

        first = History(value=1)
        first.save()
        first_stamp = first.create_date
        # Commit so that further call are at a different timestamp
        transaction.commit()

        second = History(value=1)
        first.value = 2
        History.save([first, second])
        second_stamp = second.create_date
        transaction.commit()

        third = History(value=1)
        second.value = 2
        History.delete([first])
        History.save([second, third])
        third_stamp = third.create_date
        transaction.commit()

        third.value = 2
        History.delete([second])
        third.save()
        transaction.commit()

        for test_name, timestamp, expected_1, expected_2 in [
                ('min', datetime.datetime.min, [], []),
                ('first', first_stamp, [first], []),
                ('second', second_stamp, [second], [first]),
                ('third', third_stamp, [third], [second]),
                ('max', datetime.datetime.max, [], [third]),
                ('no history', None, [], [third]),
                ]:
            with Transaction().set_context(_datetime=timestamp):
                with self.subTest(f"{test_name} ('value', '=', 1)"):
                    records = History.search([('value', '=', 1)])
                    self.assertEqual(records, expected_1)
                with self.subTest(f"{test_name} ('value', '=', 2)"):
                    records = History.search([('value', '=', 2)])
                    self.assertEqual(records, expected_2)

    @with_transaction()
    def test_ordered_search(self):
        'Test ordered search of history models'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()
        order = [('value', 'ASC')]

        history = History(value=1)
        history.save()
        first_id = history.id
        first_stamp = history.create_date
        transaction.commit()

        history = History(value=2)
        history.save()
        second_id = history.id
        second_stamp = history.create_date

        transaction.commit()

        first, second = History.search([], order=order)

        self.assertEqual(first.id, first_id)
        self.assertEqual(second.id, second_id)

        first.value = 3
        first.save()
        third_stamp = first.write_date
        transaction.commit()

        results = [
            (first_stamp, [first]),
            (second_stamp, [first, second]),
            (third_stamp, [second, first]),
            (datetime.datetime.now(), [second, first]),
            (datetime.datetime.max, [second, first]),
            ]
        for timestamp, instances in results:
            with Transaction().set_context(_datetime=timestamp):
                records = History.search([], order=order)
                self.assertEqual(records, instances)
            transaction.rollback()

        to_delete, _ = History.search([], order=order)

        self.assertEqual(to_delete.id, second.id)

        History.delete([to_delete])
        transaction.commit()

        results = [
            (first_stamp, [first]),
            (second_stamp, [first, second]),
            (third_stamp, [second, first]),
            (datetime.datetime.now(), [first]),
            (datetime.datetime.max, [first]),
            ]
        for timestamp, instances in results:
            with Transaction().set_context(_datetime=timestamp,
                    from_test=True):
                records = History.search([], order=order)
                self.assertEqual(records, instances)
            transaction.rollback()

    @unittest.skipUnless(backend.name == 'postgresql',
        'CURRENT_TIMESTAMP as transaction_timestamp is specific to postgresql')
    @with_transaction()
    def test_ordered_search_same_timestamp(self):
        'Test ordered search  with same timestamp'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()
        order = [('value', 'ASC')]

        history = History(value=1)
        history.save()
        first_stamp = history.create_date
        history.value = 4
        history.save()
        second_stamp = history.write_date

        self.assertEqual(first_stamp, second_stamp)
        transaction.commit()

        results = [
            (second_stamp, [history], [4]),
            (datetime.datetime.now(), [history], [4]),
            (datetime.datetime.max, [history], [4]),
            ]

        for timestamp, instances, values in results:
            with Transaction().set_context(_datetime=timestamp,
                    last_test=True):
                records = History.search([], order=order)
                self.assertEqual(records, instances)
                self.assertEqual([x.value for x in records], values)
            transaction.rollback()

    @with_transaction()
    def test_ordered_search_nested(self):
        "Test ordered search nested"
        pool = Pool()
        History = pool.get('test.history')
        HistoryLine = pool.get('test.history.line')
        transaction = Transaction()
        order = [('history.value', 'ASC')]

        history = History(value=1)
        history.save()
        history2 = History(value=2)
        history2.save()
        line = HistoryLine(history=history)
        line.save()
        line2 = HistoryLine(history=history2)
        line2.save()
        first_stamp = line2.create_date
        transaction.commit()

        history.value = 3
        history.save()
        second_stamp = history.write_date
        transaction.commit()

        results = [
            (first_stamp, [line, line2]),
            (second_stamp, [line2, line]),
            ]
        for timestamp, instances in results:
            with Transaction().set_context(_datetime=timestamp):
                records = HistoryLine.search([], order=order)
                self.assertListEqual(records, instances)

    @with_transaction()
    def test_browse(self):
        'Test browsing history'
        pool = Pool()
        History = pool.get('test.history')
        Line = pool.get('test.history.line')
        transaction = Transaction()

        history = History(value=1)
        history.save()
        history_id = history.id
        line_a = Line(name='a', history=history)
        line_a.save()
        line_a_id = line_a.id
        line_b = Line(name='b', history=history)
        line_b.save()
        line_b_id = line_b.id

        first_stamp = line_b.create_date

        history.stamp = first_stamp
        history.save()

        transaction.commit()

        history = History(history_id)
        history.value = 2
        history.save()

        Line.delete([Line(line_b_id)])

        line_a = Line(line_a_id)
        line_a.name = 'c'
        line_a.save()

        second_stamp = line_a.write_date

        transaction.commit()

        history = History(history_id)
        self.assertEqual(history.value, 2)
        self.assertEqual([l.name for l in history.lines], ['c'])
        self.assertEqual(history.stamp, first_stamp)
        self.assertEqual(
            [l.name for l in history.lines_at_stamp], ['a', 'b'])

        with Transaction().set_context(_datetime=first_stamp):
            history = History(history_id)
        self.assertEqual(history.value, 1)
        self.assertEqual([l.name for l in history.lines], ['a', 'b'])

        with Transaction().set_context(_datetime=second_stamp):
            history = History(history_id)
        self.assertEqual(history.value, 2)
        self.assertEqual([l.name for l in history.lines], ['c'])
        self.assertEqual(history.stamp, first_stamp)
        self.assertEqual(
            [l.name for l in history.lines_at_stamp], ['a', 'b'])

    @with_transaction()
    def test_search_cursor_max(self):
        'Test search with number of history entries at database.IN_MAX'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()
        database = transaction.database

        history = History(value=-1)
        history.save()

        for history.value in range(database.IN_MAX + 1):
            history.save()

        with transaction.set_context(_datetime=datetime.datetime.max):
            record, = History.search([])

            self.assertEqual(record.value, database.IN_MAX)

    @with_transaction()
    def test_search_cursor_max_entries(self):
        'Test search for skipping first history entries at database.IN_MAX'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()
        database = transaction.database

        for i in range(0, 2):
            history = History(value=-1)
            history.save()

            for history.value in range(database.IN_MAX + 1):
                history.save()

        with transaction.set_context(_datetime=datetime.datetime.max):
            records = History.search([])

            self.assertEqual({r.value for r in records}, {database.IN_MAX})
            self.assertEqual(len(records), 2)

    @with_transaction()
    def test_search_cursor_max_histories(self):
        'Test search with number of histories at database.IN_MAX'
        pool = Pool()
        History = pool.get('test.history')
        transaction = Transaction()
        database = transaction.database

        n = database.IN_MAX + 1
        History.create([{'value': 1}] * n)

        with transaction.set_context(_datetime=datetime.datetime.max):
            records = History.search([])

            self.assertEqual({r.value for r in records}, {1})
            self.assertEqual(len(records), n)

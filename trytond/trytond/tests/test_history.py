# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime

from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond import backend


class HistoryTestCase(unittest.TestCase):
    'Test History'

    def setUp(self):
        install_module('tests')

    def tearDown(self):
        History = POOL.get('test.history')
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cursor = transaction.cursor
            table = History.__table__()
            history_table = History.__table_history__()
            cursor.execute(*table.delete())
            cursor.execute(*history_table.delete())
            cursor.commit()

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

    @unittest.skipIf(backend.name() in ('sqlite', 'mysql'),
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

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            History.delete([History(history_id)])

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            History.restore_history([history_id], datetime.datetime.max)
            self.assertRaises(UserError, History.read, [history_id])

    def test0041restore_history_before(self):
        'Test restore history before'
        History = POOL.get('test.history')

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=1)
            history.save()
            history_id = history.id

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

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            History.restore_history_before([history_id], second)
            history = History(history_id)
            self.assertEqual(history.value, 1)

    @unittest.skipIf(backend.name() in ('sqlite', 'mysql'),
        'now() is not the start of the transaction')
    def test0045restore_history_same_timestamp(self):
        'Test restore history with same timestamp'
        History = POOL.get('test.history')

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=1)
            history.save()
            history_id = history.id
            first = history.create_date
            history.value = 2
            history.save()
            second = history.create_date

            self.assertEqual(first, second)

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            history.value = 3
            history.save()

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            History.restore_history([history_id], first)
            history = History(history_id)
            self.assertEqual(history.value, 2)

    def test0050ordered_search(self):
        'Test ordered search of history models'
        History = POOL.get('test.history')
        order = [('value', 'ASC')]

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=1)
            history.save()
            first_id = history.id
            first_stamp = history.create_date
            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=2)
            history.save()
            second_id = history.id
            second_stamp = history.create_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            first, second = History.search([], order=order)

            self.assertEqual(first.id, first_id)
            self.assertEqual(second.id, second_id)

            first.value = 3
            first.save()
            third_stamp = first.write_date
            transaction.cursor.commit()

        results = [
            (first_stamp, [first]),
            (second_stamp, [first, second]),
            (third_stamp, [second, first]),
            (datetime.datetime.now(), [second, first]),
            (datetime.datetime.max, [second, first]),
            ]
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for timestamp, instances in results:
                with Transaction().set_context(_datetime=timestamp):
                    records = History.search([], order=order)
                    self.assertEqual(records, instances)

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            to_delete, _ = History.search([], order=order)

            self.assertEqual(to_delete.id, second.id)

            History.delete([to_delete])
            transaction.cursor.commit()

        results = [
            (first_stamp, [first]),
            (second_stamp, [first, second]),
            (third_stamp, [second, first]),
            (datetime.datetime.now(), [first]),
            (datetime.datetime.max, [first]),
            ]
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for timestamp, instances in results:
                with Transaction().set_context(_datetime=timestamp,
                        from_test=True):
                    records = History.search([], order=order)
                    self.assertEqual(records, instances)

    @unittest.skipIf(backend.name() in ('sqlite', 'mysql'),
        'now() is not the start of the transaction')
    def test0060_ordered_search_same_timestamp(self):
        'Test ordered search  with same timestamp'
        History = POOL.get('test.history')
        order = [('value', 'ASC')]

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(value=1)
            history.save()
            first_stamp = history.create_date
            history.value = 4
            history.save()
            second_stamp = history.write_date

            self.assertEqual(first_stamp, second_stamp)
            transaction.cursor.commit()

        results = [
            (second_stamp, [history], [4]),
            (datetime.datetime.now(), [history], [4]),
            (datetime.datetime.max, [history], [4]),
            ]

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            for timestamp, instances, values in results:
                with Transaction().set_context(_datetime=timestamp,
                        last_test=True):
                    records = History.search([], order=order)
                    self.assertEqual(records, instances)
                    self.assertEqual([x.value for x in records], values)

    def test0070_browse(self):
        'Test browsing history'
        History = POOL.get('test.history')
        Line = POOL.get('test.history.line')

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
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

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            history.value = 2
            history.save()

            Line.delete([Line(line_b_id)])

            line_a = Line(line_a_id)
            line_a.name = 'c'
            line_a.save()

            second_stamp = line_a.write_date

            transaction.cursor.commit()

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            history = History(history_id)
            self.assertEqual(history.value, 2)
            self.assertEqual([l.name for l in history.lines], ['c'])

            with Transaction().set_context(_datetime=first_stamp):
                history = History(history_id)
            self.assertEqual(history.value, 1)
            self.assertEqual([l.name for l in history.lines], ['a', 'b'])

            with Transaction().set_context(_datetime=second_stamp):
                history = History(history_id)
            self.assertEqual(history.value, 2)
            self.assertEqual([l.name for l in history.lines], ['c'])

    def test0080_search_cursor_max(self):
        'Test search with number of history entries at cursor.IN_MAX'
        History = POOL.get('test.history')

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cursor = transaction.cursor

            history = History(value=-1)
            history.save()

            for history.value in range(cursor.IN_MAX + 1):
                history.save()

            with transaction.set_context(_datetime=datetime.datetime.max):
                record, = History.search([])

                self.assertEqual(record.value, cursor.IN_MAX)

    def test0090_search_cursor_max_entries(self):
        'Test search for skipping first history entries at cursor.IN_MAX'
        History = POOL.get('test.history')

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cursor = transaction.cursor

            for i in xrange(0, 2):
                history = History(value=-1)
                history.save()

                for history.value in range(cursor.IN_MAX + 1):
                    history.save()

            with transaction.set_context(_datetime=datetime.datetime.max):
                records = History.search([])

                self.assertEqual({r.value for r in records}, {cursor.IN_MAX})
                self.assertEqual(len(records), 2)

    def test0100_search_cursor_max_histories(self):
        'Test search with number of histories at cursor.IN_MAX'
        History = POOL.get('test.history')

        with Transaction().start(DB_NAME, USER,
                                 context=CONTEXT) as transaction:
            cursor = transaction.cursor

            n = cursor.IN_MAX + 1
            History.create([{'value': 1}] * n)

            with transaction.set_context(_datetime=datetime.datetime.max):
                records = History.search([])

                self.assertEqual({r.value for r in records}, {1})
                self.assertEqual(len(records), n)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(HistoryTestCase)

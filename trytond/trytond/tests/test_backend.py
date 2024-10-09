# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import math

from sql import Cast, Literal, Select, Table, functions
from sql.functions import CurrentTimestamp, DateTrunc, ToChar

from trytond.model import fields
from trytond.sql.functions import NumRange
from trytond.sql.operators import RangeContain, RangeIn, RangeOverlap
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)
from trytond.transaction import Transaction


class BackendTestCase(TestCase):
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
        now = dt.datetime.now()
        query = Select([ToChar(now, 'YYYYMMDD HH24:MI:SS.US')])
        cursor = Transaction().connection.cursor()

        cursor.execute(*query)
        text, = cursor.fetchone()

        self.assertEqual(text, now.strftime('%Y%m%d %H:%M:%S.%f'))

    @with_transaction()
    def test_to_char_date(self):
        "Test TO_CHAR with date"
        today = dt.date.today()
        query = Select([ToChar(today, 'YYYY-MM-DD')])
        cursor = Transaction().connection.cursor()

        cursor.execute(*query)
        text, = cursor.fetchone()

        self.assertEqual(text, today.strftime('%Y-%m-%d'))

    @with_transaction()
    def test_functions(self):
        "Test functions"
        cursor = Transaction().connection.cursor()
        tests = [
            (functions.Abs(-1), 1),
            (functions.Cbrt(27), 3),
            (functions.Ceil(-42.8), -42),
            (functions.Degrees(0.5), 28.6478897565412),
            (functions.Div(9, 4), 2),
            (functions.Exp(1.), math.e),
            (functions.Floor(-42.8), -43),
            (functions.Ln(2.), 0.693147180559945),
            (functions.Log(100.0), 2),
            (functions.Mod(9, 4), 1),
            (functions.Pi(), math.pi),
            (functions.Power(9, 3), 729),
            (functions.Radians(45.), math.pi / 4),
            (functions.Round(42.4), 42),
            (functions.Round(42.4382, 2), 42.44),
            (functions.Sign(-8.4), -1),
            (functions.Sqrt(2.), 1.4142135623731),
            (functions.Trunc(42.8), 42),
            (functions.Trunc(42.4348, 2), 42.43),
            (functions.Acos(0.5), 1.0471975511965979),
            (functions.Asin(0.5), 0.5235987755982989),
            (functions.Atan(0.5), 0.4636476090008061),
            (functions.Atan2(0.5, 0.5), 0.7853981633974483),
            (functions.Cos(1), 0.5403023058681398),
            (functions.Cot(0), math.inf),
            (functions.Cot(1), 0.6420926159343306),
            (functions.Sin(1), 0.8414709848078965),
            (functions.Tan(1), 1.5574077246549023),
            (functions.CharLength('jose'), 4),
            (functions.Lower('TOM'), 'tom'),
            (functions.Overlay('Txxxxas', 'hom', 2, 4), 'Thomas'),
            (functions.Position('om', 'Thomas'), 3),
            (functions.Substring('Thomas', 2, 3), 'hom'),
            # (functions.Substring('Thomas', '...$'), 'mas'),
            # (functions.Substring('Thomas', '%#"o_a#"_', '#'), 'oma'),
            (functions.Trim('yxTomxx', 'BOTH', 'xyz'), 'Tom'),
            (functions.Trim(Literal('yxTomxxx'), 'BOTH', 'xyz'), "Tom"),
            (functions.Upper('tom'), 'TOM'),
            ]
        for func, result in tests:
            with self.subTest(func=str(func)):
                cursor.execute(*Select([func]))
                value, = cursor.fetchone()
                if isinstance(result, str):
                    self.assertEqual(value, result)
                else:
                    self.assertAlmostEqual(float(value), float(result))

    @with_transaction()
    def test_function_random(self):
        "Test RANDOM function"
        cursor = Transaction().connection.cursor()
        cursor.execute(*Select([functions.Random()]))
        value, = cursor.fetchone()
        self.assertGreaterEqual(value, 0)
        self.assertLessEqual(value, 1)

    @with_transaction()
    def test_function_setseed(self):
        "Test SETSEED function"
        cursor = Transaction().connection.cursor()
        cursor.execute(*Select([functions.SetSeed(1)]))

    @with_transaction()
    def test_function_date_trunc(self):
        "Test DateTrunc function"
        cursor = Transaction().connection.cursor()
        date = dt.datetime(2001, 2, 16, 20, 38, 40, 100)
        for type_, result in [
                ('microsecond', dt.datetime(2001, 2, 16, 20, 38, 40, 100)),
                ('second', dt.datetime(2001, 2, 16, 20, 38, 40)),
                ('minute', dt.datetime(2001, 2, 16, 20, 38)),
                ('hour', dt.datetime(2001, 2, 16, 20)),
                ('day', dt.datetime(2001, 2, 16)),
                ('month', dt.datetime(2001, 2, 1)),
                ]:
            for type_ in [type_.lower(), type_.upper()]:
                with self.subTest(type_=type_):
                    cursor.execute(*Select([DateTrunc(type_, date)]))
                    value, = cursor.fetchone()
                    self.assertEqual(str(value), str(result))

    @with_transaction()
    def test_function_date_trunc_null(self):
        "test DateTrunc function with NULL"
        cursor = Transaction().connection.cursor()
        date = fields.Date("Test")

        cursor.execute(*Select([DateTrunc('month', date.sql_cast(None))]))
        value, = cursor.fetchone()
        self.assertEqual(value, None)

    @with_transaction()
    def test_operator_range_contain(self):
        "Test Range Contain operator"
        cursor = Transaction().connection.cursor()
        numeric = fields.Numeric("Test")

        def Num(value):
            return Cast(value, numeric.sql_type().base)

        for expression, value in [
                (RangeContain(NumRange(2, 4), NumRange(2, 3)), True),
                (RangeContain(NumRange(2, 4), NumRange(1, 2)), False),
                (RangeContain(
                        NumRange(2, 4, '(]'), NumRange(2, 3, '[)')), False),
                (RangeContain(NumRange(None, 4), NumRange(2, 3)), True),
                (RangeContain(NumRange(None, 2), NumRange(2, 3)), False),
                (RangeContain(NumRange(None, 2), NumRange(None, 2)), True),
                (RangeContain(NumRange(2, 4), NumRange(2, None)), False),
                (RangeContain(NumRange(2, None), NumRange(2, None)), True),
                (RangeContain(NumRange(2, 4), Num(1)), False),
                (RangeContain(NumRange(2, 4), Num(3)), True),
                (RangeContain(NumRange(2, 4), Num(2)), True),
                (RangeContain(NumRange(2, 4), Num(4)), False),
                ]:
            with self.subTest(expression=expression.params):
                cursor.execute(*Select([expression]))
                result, = cursor.fetchone()
                self.assertEqual(result, value)

    @with_transaction()
    def test_operator_range_in(self):
        "Test Range In operator"
        cursor = Transaction().connection.cursor()
        numeric = fields.Numeric("Test")

        def Num(value):
            return Cast(value, numeric.sql_type().base)

        for expression, value in [
                (RangeIn(NumRange(2, 3), NumRange(2, 4)), True),
                (RangeIn(Num(2), NumRange(2, 4)), True),
                ]:
            with self.subTest(expression=expression.params):
                cursor.execute(*Select([expression]))
                result, = cursor.fetchone()
                self.assertEqual(result, value)

    @with_transaction()
    def test_operator_range_overlap(self):
        "test Range Overlap operator"
        cursor = Transaction().connection.cursor()

        for expression, value in [
                (RangeOverlap(NumRange(3, 7), NumRange(4, 12)), True),
                (RangeOverlap(NumRange(3, 4), NumRange(7, 12)), False),
                (RangeOverlap(NumRange(2, 3), NumRange(3, 4)), False),
                (RangeOverlap(
                        NumRange(2, 3, '(]'), NumRange(3, 4, '[)')), True),
                (RangeOverlap(NumRange(None, 3), NumRange(3, 4)), False),
                (RangeOverlap(NumRange(2, None), NumRange(3, 4)), True),
                (RangeOverlap(NumRange(None, 3), NumRange(3, None)), False),
                (RangeOverlap(NumRange(None, 3), NumRange(None, 4)), True),
                (RangeOverlap(NumRange(2, None), NumRange(3, None)), True),
                ]:
            with self.subTest(expression=expression.params):
                cursor.execute(*Select([expression]))
                result, = cursor.fetchone()
                self.assertEqual(result, value)

                expression.left, expression.right = (
                    expression.right, expression.left)
                cursor.execute(*Select([expression]))
                result, = cursor.fetchone()
                self.assertEqual(result, value)

    @with_transaction()
    def test_estimated_count(self):
        "Test estimated count queries"
        database = Transaction().database
        connection = Transaction().connection

        count = database.estimated_count(connection, Table('res_user'))

        self.assertGreaterEqual(count, 0)

    @with_transaction()
    def test_estimated_count_table_query(self):
        "Test estimated count queries on Model using a table query"
        database = Transaction().database
        connection = Transaction().connection

        query = Select([Literal(1)])
        count = database.estimated_count(connection, query)

        self.assertEqual(count, 1)

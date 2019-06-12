# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
import doctest
import sys

import sql
import sql.operators

from trytond.tools import (
    reduce_ids, reduce_domain, decimal_, is_instance_method, file_open,
    strip_wildcard, lstrip_wildcard, rstrip_wildcard)
from trytond.tools.string_ import StringPartitioned


class ToolsTestCase(unittest.TestCase):
    'Test tools'
    table = sql.Table('test')

    def test_reduce_ids_empty(self):
        'Test reduce_ids empty list'
        self.assertEqual(reduce_ids(self.table.id, []), sql.Literal(False))

    def test_reduce_ids_continue(self):
        'Test reduce_ids continue list'
        self.assertEqual(reduce_ids(self.table.id, list(range(10))),
            sql.operators.Or(((self.table.id >= 0) & (self.table.id <= 9),)))

    def test_reduce_ids_one_hole(self):
        'Test reduce_ids continue list with one hole'
        self.assertEqual(reduce_ids(self.table.id, list(range(10)) + list(range(20, 30))),
            ((self.table.id >= 0) & (self.table.id <= 9))
            | ((self.table.id >= 20) & (self.table.id <= 29)))

    def test_reduce_ids_short_continue(self):
        'Test reduce_ids short continue list'
        self.assertEqual(reduce_ids(self.table.id, list(range(4))),
            sql.operators.Or((self.table.id.in_(list(range(4))),)))

    def test_reduce_ids_complex(self):
        'Test reduce_ids complex list'
        self.assertEqual(reduce_ids(self.table.id,
                list(range(10)) + list(range(25, 30)) + list(range(15, 20))),
            (((self.table.id >= 0) & (self.table.id <= 14))
                | (self.table.id.in_(list(range(25, 30))))))

    def test_reduce_ids_complex_small_continue(self):
        'Test reduce_ids complex list with small continue'
        self.assertEqual(reduce_ids(self.table.id,
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 18, 19, 21]),
            (((self.table.id >= 1) & (self.table.id <= 12))
                | (self.table.id.in_([15, 18, 19, 21]))))

    @unittest.skipIf(sys.flags.optimize, "assert removed by optimization")
    def test_reduce_ids_float(self):
        'Test reduce_ids with integer as float'
        self.assertEqual(reduce_ids(self.table.id,
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0,
                    15.0, 18.0, 19.0, 21.0]),
            (((self.table.id >= 1.0) & (self.table.id <= 12.0))
                | (self.table.id.in_([15.0, 18.0, 19.0, 21.0]))))
        self.assertRaises(AssertionError, reduce_ids, self.table.id, [1.1])

    def test_reduce_domain(self):
        'Test reduce_domain'
        clause = ('x', '=', 'x')
        tests = (
            ([clause], ['AND', clause]),
            ([clause, [clause]], ['AND', clause, clause]),
            (['AND', clause, [clause]], ['AND', clause, clause]),
            ([clause, ['AND', clause]], ['AND', clause, clause]),
            ([clause, ['AND', clause, clause]],
                ['AND', clause, clause, clause]),
            (['AND', clause, ['AND', clause]], ['AND', clause, clause]),
            ([[[clause]]], ['AND', clause]),
            (['OR', clause], ['OR', clause]),
            (['OR', clause, [clause]], ['OR', clause, ['AND', clause]]),
            (['OR', clause, [clause, clause]],
                ['OR', clause, ['AND', clause, clause]]),
            (['OR', clause, ['OR', clause]], ['OR', clause, clause]),
            (['OR', clause, [clause, ['OR', clause, clause]]],
                ['OR', clause, ['AND', clause, ['OR', clause, clause]]]),
            (['OR', [clause]], ['OR', ['AND', clause]]),
            ([], []),
            (['OR', clause, []], ['OR', clause, []]),
            (['AND', clause, []], ['AND', clause, []]),
        )
        for i, j in tests:
            self.assertEqual(reduce_domain(i), j,
                    '%s -> %s != %s' % (i, reduce_domain(i), j))

    def test_is_instance_method(self):
        'Test is_instance_method'

        class Foo(object):

            @staticmethod
            def static():
                pass

            @classmethod
            def klass(cls):
                pass

            def instance(self):
                pass

        self.assertFalse(is_instance_method(Foo, 'static'))
        self.assertFalse(is_instance_method(Foo, 'klass'))
        self.assertTrue(is_instance_method(Foo, 'instance'))

    def test_file_open(self):
        "Test file_open"
        with file_open('__init__.py', subdir=None) as fp:
            self.assertTrue(fp)

        with file_open('ir/__init__.py') as fp:
            self.assertTrue(fp)

        with self.assertRaisesRegex(IOError, "File not found :"):
            with file_open('ir/noexist'):
                pass

        with self.assertRaisesRegex(IOError, "Permission denied:"):
            with file_open('/etc/passwd'):
                pass

        with self.assertRaisesRegex(IOError, "Permission denied:"):
            with file_open('../../foo'):
                pass

    def test_file_open_suffix(self):
        "Test file_open from same root name but with a suffix"
        with self.assertRaisesRegex(IOError, "Permission denied:"):
            file_open('../trytond_suffix', subdir=None)

    def test_strip_wildcard(self):
        'Test strip wildcard'
        for clause, result in [
                ('%a%', 'a'),
                ('%%%%a%%%', 'a'),
                ('\\%a%', '\\%a'),
                ('\\%a\\%', '\\%a\\%'),
                ('a', 'a'),
                ('', ''),
                (None, None),
                ]:
            self.assertEqual(
                strip_wildcard(clause), result, msg=clause)

    def test_strip_wildcard_different_wildcard(self):
        'Test strip wildcard with different wildcard'
        self.assertEqual(strip_wildcard('___a___', '_'), 'a')

    def test_lstrip_wildcard(self):
        'Test lstrip wildcard'
        for clause, result in [
                ('%a', 'a'),
                ('%a%', 'a%'),
                ('%%%%a%', 'a%'),
                ('\\%a%', '\\%a%'),
                ('a', 'a'),
                ('', ''),
                (None, None),
                ]:
            self.assertEqual(
                lstrip_wildcard(clause), result, msg=clause)

    def test_lstrip_wildcard_different_wildcard(self):
        'Test lstrip wildcard with different wildcard'
        self.assertEqual(lstrip_wildcard('___a', '_'), 'a')

    def test_rstrip_wildcard(self):
        'Test rstrip wildcard'
        for clause, result in [
                ('a%', 'a'),
                ('%a%', '%a'),
                ('%a%%%%%', '%a'),
                ('%a\\%', '%a\\%'),
                ('a', 'a'),
                ('', ''),
                (None, None),
                ]:
            self.assertEqual(
                rstrip_wildcard(clause), result, msg=clause)

    def test_rstrip_wildcard_diferent_wildcard(self):
        self.assertEqual(rstrip_wildcard('a___', '_'), 'a')


class StringPartitionedTestCase(unittest.TestCase):
    "Test StringPartitioned"

    def test_init(self):
        s = StringPartitioned('foo')

        self.assertEqual(s, 'foo')
        self.assertEqual(s._parts, ('foo',))

    def test_init_partitioned(self):
        s = StringPartitioned(
            StringPartitioned('foo') + StringPartitioned('bar'))

        self.assertEqual(s, 'foobar')
        self.assertEqual(s._parts, ('foo', 'bar'))

    def test_iter(self):
        s = StringPartitioned('foo')

        self.assertEqual(list(s), ['foo'])

    def test_len(self):
        s = StringPartitioned('foo')

        self.assertEqual(len(s), 3)

    def test_str(self):
        s = StringPartitioned('foo')

        s = str(s)

        self.assertEqual(s, 'foo')
        self.assertIsInstance(s, str)
        self.assertNotIsInstance(s, StringPartitioned)

    def test_add(self):
        s = StringPartitioned('foo')

        s = s + 'bar'

        self.assertEqual(s, 'foobar')
        self.assertEqual(list(s), ['foo', 'bar'])

    def test_radd(self):
        s = StringPartitioned('foo')

        s = 'bar' + s

        self.assertEqual(s, 'barfoo')
        self.assertEqual(list(s), ['bar', 'foo'])


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in [ToolsTestCase, StringPartitionedTestCase]:
        suite.addTests(func(testcase))
    suite.addTest(doctest.DocTestSuite(decimal_))
    return suite

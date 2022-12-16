# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import unittest
import doctest
import sys

import sql
import sql.operators

from trytond.tools import (
    reduce_ids, reduce_domain, decimal_, is_instance_method, file_open,
    strip_wildcard, lstrip_wildcard, rstrip_wildcard, slugify, sortable_values,
    escape_wildcard, unescape_wildcard, is_full_text, firstline)
from trytond.tools.string_ import StringPartitioned, LazyString
from trytond.tools.domain_inversion import (
    domain_inversion, parse, simplify, merge, concat, unique_value,
    eval_domain, localize_domain,
    prepare_reference_domain, extract_reference_models)


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
        self.assertEqual(reduce_ids(
                self.table.id, list(range(10)) + list(range(20, 30))),
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

    def test_escape_wildcard(self):
        self.assertEqual(
            escape_wildcard('foo%bar_baz\\'),
            'foo\\%bar\\_baz\\\\')

    def test_unescape_wildcard(self):
        "Test unescape_wildcard"
        self.assertEqual(
            unescape_wildcard('foo\\%bar\\_baz\\\\'),
            'foo%bar_baz\\')

    def test_is_full_text(self):
        "Test is_full_text"
        for value, result in [
                ('foo', True),
                ('%foo bar%', True),
                ('foo%', False),
                ('foo_bar', False),
                ('foo\\_bar', True),
                ]:
            with self.subTest(value=value):
                self.assertEqual(is_full_text(value), result)

    def test_slugify(self):
        "Test slugify"
        self.assertEqual(slugify('unicode ♥ is ☢'), 'unicode-is')

    def test_slugify_hyphenate(self):
        "Test hyphenate in slugify"
        self.assertEqual(slugify('foo bar', hyphenate='_'), 'foo_bar')


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


class LazyStringTestCase(unittest.TestCase):
    "Test LazyString"

    def test_init(self):
        s = LazyString(lambda: 'foo')

        self.assertIsInstance(s, LazyString)
        self.assertEqual(str(s), 'foo')

    def test_init_args(self):
        s = LazyString(lambda a: a, 'foo')

        self.assertIsInstance(s, LazyString)
        self.assertEqual(str(s), 'foo')

    def test_add(self):
        s = LazyString(lambda: 'foo')

        s = s + 'bar'

        self.assertEqual(s, 'foobar')

    def test_radd(self):
        s = LazyString(lambda: 'foo')

        s = 'bar' + s

        self.assertEqual(s, 'barfoo')


class DomainInversionTestCase(unittest.TestCase):
    "Test domain_inversion"

    def test_simple_inversion(self):
        domain = [['x', '=', 3]]
        self.assertEqual(domain_inversion(domain, 'x'), [['x', '=', 3]])

        domain = []
        self.assertEqual(domain_inversion(domain, 'x'), True)
        self.assertEqual(domain_inversion(domain, 'x', {'x': 5}), True)
        self.assertEqual(domain_inversion(domain, 'z', {'x': 7}), True)

        domain = [['x.id', '>', 5]]
        self.assertEqual(domain_inversion(domain, 'x'), [['x.id', '>', 5]])

    def test_and_inversion(self):
        domain = [['x', '=', 3], ['y', '>', 5]]
        self.assertEqual(domain_inversion(domain, 'x'), [['x', '=', 3]])
        self.assertEqual(domain_inversion(domain, 'x', {'y': 4}), False)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': 6}), [['x', '=', 3]])

        domain = [['x', '=', 3], ['y', '=', 5]]
        self.assertEqual(domain_inversion(domain, 'z'), True)
        self.assertEqual(domain_inversion(domain, 'z', {'x': 2, 'y': 7}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': None}), [['x', '=', 3]])

        domain = [['x.id', '>', 5], ['y', '<', 3]]
        self.assertEqual(domain_inversion(domain, 'y'), [['y', '<', 3]])
        self.assertEqual(
            domain_inversion(domain, 'y', {'x': 3}), [['y', '<', 3]])
        self.assertEqual(domain_inversion(domain, 'x'), [['x.id', '>', 5]])

    def test_or_inversion(self):
        domain = ['OR', ['x', '=', 3], ['y', '>', 5], ['z', '=', 'abc']]
        self.assertEqual(domain_inversion(domain, 'x'), True)
        self.assertEqual(domain_inversion(domain, 'x', {'y': 4}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': 4, 'z': 'ab'}),
            [['x', '=', 3]])
        self.assertEqual(domain_inversion(domain, 'x', {'y': 7}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': 7, 'z': 'b'}), True)
        self.assertEqual(domain_inversion(domain, 'x', {'z': 'abc'}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': 4, 'z': 'abc'}), True)

        domain = ['OR', ['x', '=', 3], ['y', '=', 5]]
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': None}), [['x', '=', 3]])

        domain = ['OR', ['x', '=', 3], ['y', '>', 5]]
        self.assertEqual(domain_inversion(domain, 'z'), True)

        domain = ['OR', ['x.id', '>', 5], ['y', '<', 3]]
        self.assertEqual(domain_inversion(domain, 'y'), True)
        self.assertEqual(domain_inversion(domain, 'y', {'z': 4}), True)
        self.assertEqual(domain_inversion(domain, 'y', {'x': 3}), True)

        domain = ['OR', ['length', '>', 5], ['language.code', '=', 'de_DE']]
        self.assertEqual(
            domain_inversion(domain, 'length', {'length': 0, 'name': 'n'}),
            True)

    def test_orand_inversion(self):
        domain = ['OR', [['x', '=', 3], ['y', '>', 5], ['z', '=', 'abc']],
            [['x', '=', 4]], [['y', '>', 6]]]
        self.assertEqual(domain_inversion(domain, 'x'), True)
        self.assertEqual(domain_inversion(domain, 'x', {'y': 4}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'z': 'abc', 'y': 7}), True)
        self.assertEqual(domain_inversion(domain, 'x', {'y': 7}), True)
        self.assertEqual(domain_inversion(domain, 'x', {'z': 'ab'}), True)

    def test_andor_inversion(self):
        domain = [['OR', ['x', '=', 4], ['y', '>', 6]], ['z', '=', 3]]
        self.assertEqual(domain_inversion(domain, 'z'), [['z', '=', 3]])
        self.assertEqual(
            domain_inversion(domain, 'z', {'x': 5}), [['z', '=', 3]])
        self.assertEqual(
            domain_inversion(domain, 'z', {'x': 5, 'y': 5}), [['z', '=', 3]])
        self.assertEqual(
            domain_inversion(domain, 'z', {'x': 5, 'y': 7}), [['z', '=', 3]])

    def test_andand_inversion(self):
        domain = [[['x', '=', 4], ['y', '>', 6]], ['z', '=', 3]]
        self.assertEqual(domain_inversion(domain, 'z'), [['z', '=', 3]])
        self.assertEqual(
            domain_inversion(domain, 'z', {'x': 5}), [['z', '=', 3]])
        self.assertEqual(
            domain_inversion(domain, 'z', {'y': 5}), [['z', '=', 3]])
        self.assertEqual(
            domain_inversion(domain, 'z', {'x': 4, 'y': 7}), [['z', '=', 3]])

        domain = [
            [['x', '=', 4], ['y', '>', 6], ['z', '=', 2]], [['w', '=', 2]]]
        self.assertEqual(
            domain_inversion(domain, 'z', {'x': 4}), [['z', '=', 2]])

    def test_oror_inversion(self):
        domain = ['OR', ['OR', ['x', '=', 3], ['y', '>', 5]],
            ['OR', ['x', '=', 2], ['z', '=', 'abc']],
            ['OR', ['y', '=', 8], ['z', '=', 'y']]]
        self.assertEqual(domain_inversion(domain, 'x'), True)
        self.assertEqual(domain_inversion(domain, 'x', {'y': 4}), True)
        self.assertEqual(domain_inversion(domain, 'x', {'z': 'ab'}), True)
        self.assertEqual(domain_inversion(domain, 'x', {'y': 7}), True)
        self.assertEqual(domain_inversion(domain, 'x', {'z': 'abc'}), True)
        self.assertEqual(domain_inversion(domain, 'x', {'z': 'y'}), True)
        self.assertEqual(domain_inversion(domain, 'x', {'y': 8}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': 8, 'z': 'b'}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': 4, 'z': 'y'}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': 7, 'z': 'abc'}), True)
        self.assertEqual(
            domain_inversion(domain, 'x', {'y': 4, 'z': 'b'}),
            ['OR', [['x', '=', 3]], [['x', '=', 2]]])

    def test_parse(self):
        domain = parse([['x', '=', 5]])
        self.assertEqual(domain.variables, set('x'))

        domain = parse(['OR', ['x', '=', 4], ['y', '>', 6]])
        self.assertEqual(domain.variables, set('xy'))

        domain = parse([['OR', ['x', '=', 4], ['y', '>', 6]], ['z', '=', 3]])
        self.assertEqual(domain.variables, set('xyz'))

        domain = parse([[['x', '=', 4], ['y', '>', 6]], ['z', '=', 3]])
        self.assertEqual(domain.variables, set('xyz'))

    def test_simplify(self):
        domain = [['x', '=', 3]]
        self.assertEqual(simplify(domain), [['x', '=', 3]])

        domain = [[['x', '=', 3]]]
        self.assertEqual(simplify(domain), [['x', '=', 3]])

        domain = ['OR', ['x', '=', 3]]
        self.assertEqual(simplify(domain), [['x', '=', 3]])

        domain = ['OR', [['x', '=', 3]], [['y', '=', 5]]]
        self.assertEqual(
            simplify(domain), ['OR', [['x', '=', 3]], [['y', '=', 5]]])

        domain = ['OR', ['x', '=', 3], ['AND', ['y', '=', 5]]]
        self.assertEqual(
            simplify(domain), ['OR', ['x', '=', 3], [['y', '=', 5]]])

        domain = ['AND']
        self.assertEqual(simplify(domain), [])

        domain = ['OR']
        self.assertEqual(simplify(domain), [])

    def test_merge(self):
        domain = [['x', '=', 6], ['y', '=', 7]]
        self.assertEqual(merge(domain), ['AND', ['x', '=', 6], ['y', '=', 7]])

        domain = ['AND', ['x', '=', 6], ['y', '=', 7]]
        self.assertEqual(merge(domain), ['AND', ['x', '=', 6], ['y', '=', 7]])

        domain = [['z', '=', 8], ['AND', ['x', '=', 6], ['y', '=', 7]]]
        self.assertEqual(
            merge(domain),
            ['AND', ['z', '=', 8], ['x', '=', 6], ['y', '=', 7]])

        domain = ['OR', ['x', '=', 1], ['y', '=', 2], ['z', '=', 3]]
        self.assertEqual(
            merge(domain), ['OR', ['x', '=', 1], ['y', '=', 2], ['z', '=', 3]])

        domain = ['OR', ['x', '=', 1], ['OR', ['y', '=', 2], ['z', '=', 3]]]
        self.assertEqual(
            merge(domain), ['OR', ['x', '=', 1], ['y', '=', 2], ['z', '=', 3]])

        domain = ['OR', ['x', '=', 1], ['AND', ['y', '=', 2], ['z', '=', 3]]]
        self.assertEqual(
            merge(domain),
            ['OR', ['x', '=', 1], ['AND', ['y', '=', 2], ['z', '=', 3]]])

        domain = [['z', '=', 8], ['OR', ['x', '=', 6], ['y', '=', 7]]]
        self.assertEqual(
            merge(domain),
            ['AND', ['z', '=', 8], ['OR', ['x', '=', 6], ['y', '=', 7]]])

        domain = ['AND', ['OR', ['a', '=', 1], ['b', '=', 2]],
            ['OR', ['c', '=', 3], ['AND', ['d', '=', 4], ['d2', '=', 6]]],
            ['AND', ['d', '=', 5], ['e', '=', 6]], ['f', '=', 7]]
        self.assertEqual(
            merge(domain),
            ['AND', ['OR', ['a', '=', 1], ['b', '=', 2]],
                ['OR', ['c', '=', 3], ['AND', ['d', '=', 4], ['d2', '=', 6]]],
                ['d', '=', 5], ['e', '=', 6], ['f', '=', 7]])

    def test_concat(self):
        domain1 = [['a', '=', 1]]
        domain2 = [['b', '=', 2]]
        self.assertEqual(
            concat(domain1, domain2), ['AND', ['a', '=', 1], ['b', '=', 2]])
        self.assertEqual(concat([], domain1), domain1)
        self.assertEqual(concat(domain2, []), domain2)
        self.assertEqual(concat([], []), [])
        self.assertEqual(
            concat(domain1, domain2, domoperator='OR'),
            ['OR', [['a', '=', 1]], [['b', '=', 2]]])

    def test_unique_value(self):
        domain = [['a', '=', 1]]
        self.assertEqual(unique_value(domain), (True, '=', 1))

        domain = [['a', '!=', 1]]
        self.assertFalse(unique_value(domain)[0])

        domain = [['a', '=', 1], ['a', '=', 2]]
        self.assertFalse(unique_value(domain)[0])

        domain = [['a.b', '=', 1]]
        self.assertFalse(unique_value(domain)[0])

        domain = [['a.id', '=', 1, 'model']]
        self.assertEqual(unique_value(domain), (True, '=', ['model', 1]))

        domain = [['a.b.id', '=', 1, 'model']]
        self.assertEqual(unique_value(domain), (False, None, None))

    def test_evaldomain(self):
        domain = [['x', '>', 5]]
        self.assertTrue(eval_domain(domain, {'x': 6}))
        self.assertFalse(eval_domain(domain, {'x': 4}))

        domain = [['x', '>', None]]
        self.assertFalse(eval_domain(domain, {'x': dt.date.today()}))
        self.assertFalse(eval_domain(domain, {'x': dt.datetime.now()}))

        domain = [['x', '<', dt.date.today()]]
        self.assertFalse(eval_domain(domain, {'x': None}))
        domain = [['x', '<', dt.datetime.now()]]
        self.assertFalse(eval_domain(domain, {'x': None}))

        domain = [['x', 'in', [3, 5]]]
        self.assertTrue(eval_domain(domain, {'x': 3}))
        self.assertFalse(eval_domain(domain, {'x': 4}))
        self.assertTrue(eval_domain(domain, {'x': [3]}))
        self.assertTrue(eval_domain(domain, {'x': [3, 4]}))
        self.assertFalse(eval_domain(domain, {'x': [1, 2]}))
        self.assertFalse(eval_domain(domain, {'x': None}))

        domain = [['x', 'in', [1, None]]]
        self.assertTrue(eval_domain(domain, {'x': None}))
        self.assertFalse(eval_domain(domain, {'x': 2}))

        domain = [['x', 'not in', [3, 5]]]
        self.assertFalse(eval_domain(domain, {'x': 3}))
        self.assertTrue(eval_domain(domain, {'x': 4}))
        self.assertFalse(eval_domain(domain, {'x': [3]}))
        self.assertFalse(eval_domain(domain, {'x': [3, 4]}))
        self.assertTrue(eval_domain(domain, {'x': [1, 2]}))
        self.assertFalse(eval_domain(domain, {'x': None}))

        domain = [['x', 'not in', [1, None]]]
        self.assertFalse(eval_domain(domain, {'x': None}))
        self.assertTrue(eval_domain(domain, {'x': 2}))

        domain = [['x', 'like', 'abc']]
        self.assertTrue(eval_domain(domain, {'x': 'abc'}))
        self.assertFalse(eval_domain(domain, {'x': ''}))
        self.assertFalse(eval_domain(domain, {'x': 'xyz'}))
        self.assertFalse(eval_domain(domain, {'x': 'abcd'}))

        domain = [['x', 'not like', 'abc']]
        self.assertTrue(eval_domain(domain, {'x': 'xyz'}))
        self.assertTrue(eval_domain(domain, {'x': 'ABC'}))
        self.assertFalse(eval_domain(domain, {'x': 'abc'}))

        domain = [['x', 'not ilike', 'abc']]
        self.assertTrue(eval_domain(domain, {'x': 'xyz'}))
        self.assertFalse(eval_domain(domain, {'x': 'ABC'}))
        self.assertFalse(eval_domain(domain, {'x': 'abc'}))

        domain = [['x', 'like', 'a%']]
        self.assertTrue(eval_domain(domain, {'x': 'a'}))
        self.assertTrue(eval_domain(domain, {'x': 'abcde'}))
        self.assertFalse(eval_domain(domain, {'x': ''}))
        self.assertFalse(eval_domain(domain, {'x': 'ABCDE'}))
        self.assertFalse(eval_domain(domain, {'x': 'xyz'}))

        domain = [['x', 'ilike', 'a%']]
        self.assertTrue(eval_domain(domain, {'x': 'a'}))
        self.assertTrue(eval_domain(domain, {'x': 'A'}))
        self.assertFalse(eval_domain(domain, {'x': ''}))
        self.assertFalse(eval_domain(domain, {'x': 'xyz'}))

        domain = [['x', 'like', 'a_']]
        self.assertTrue(eval_domain(domain, {'x': 'ab'}))
        self.assertFalse(eval_domain(domain, {'x': 'a'}))
        self.assertFalse(eval_domain(domain, {'x': 'abc'}))

        domain = [['x', 'like', 'a\\%b']]
        self.assertTrue(eval_domain(domain, {'x': 'a%b'}))
        self.assertFalse(eval_domain(domain, {'x': 'ab'}))
        self.assertFalse(eval_domain(domain, {'x': 'a123b'}))

        domain = [['x', 'like', '\\%b']]
        self.assertTrue(eval_domain(domain, {'x': '%b'}))
        self.assertFalse(eval_domain(domain, {'x': 'b'}))
        self.assertFalse(eval_domain(domain, {'x': '123b'}))

        domain = [['x', 'like', 'a\\_c']]
        self.assertTrue(eval_domain(domain, {'x': 'a_c'}))
        self.assertFalse(eval_domain(domain, {'x': 'abc'}))
        self.assertFalse(eval_domain(domain, {'x': 'ac'}))

        domain = [['x', 'like', 'a\\\\_c']]
        self.assertTrue(eval_domain(domain, {'x': 'a\\bc'}))
        self.assertFalse(eval_domain(domain, {'x': 'abc'}))

        domain = ['OR', ['x', '>', 10], ['x', '<', 0]]
        self.assertTrue(eval_domain(domain, {'x': 11}))
        self.assertTrue(eval_domain(domain, {'x': -4}))
        self.assertFalse(eval_domain(domain, {'x': 5}))

        domain = ['OR', ['x', '>', 0], ['x', '=', None]]
        self.assertTrue(eval_domain(domain, {'x': 1}))
        self.assertTrue(eval_domain(domain, {'x': None}))
        self.assertFalse(eval_domain(domain, {'x': -1}))
        self.assertFalse(eval_domain(domain, {'x': 0}))

        domain = [['x', '>', 0], ['OR', ['x', '=', 3], ['x', '=', 2]]]
        self.assertFalse(eval_domain(domain, {'x': 1}))
        self.assertTrue(eval_domain(domain, {'x': 3}))
        self.assertTrue(eval_domain(domain, {'x': 2}))
        self.assertFalse(eval_domain(domain, {'x': 4}))
        self.assertFalse(eval_domain(domain, {'x': 5}))
        self.assertFalse(eval_domain(domain, {'x': 6}))

        domain = ['OR', ['x', '=', 4], [['x', '>', 6], ['x', '<', 10]]]
        self.assertTrue(eval_domain(domain, {'x': 4}))
        self.assertTrue(eval_domain(domain, {'x': 7}))
        self.assertFalse(eval_domain(domain, {'x': 3}))
        self.assertFalse(eval_domain(domain, {'x': 5}))
        self.assertFalse(eval_domain(domain, {'x': 11}))

        domain = [['x', '=', 'test,1']]
        self.assertTrue(eval_domain(domain, {'x': ('test', 1)}))
        self.assertTrue(eval_domain(domain, {'x': 'test,1'}))
        self.assertFalse(eval_domain(domain, {'x': ('test', 2)}))
        self.assertFalse(eval_domain(domain, {'x': 'test,2'}))

        domain = [['x', '=', ('test', 1)]]
        self.assertTrue(eval_domain(domain, {'x': ('test', 1)}))
        self.assertTrue(eval_domain(domain, {'x': 'test,1'}))
        self.assertFalse(eval_domain(domain, {'x': ('test', 2)}))
        self.assertFalse(eval_domain(domain, {'x': 'test,2'}))

        domain = [['x', '=', 1]]
        self.assertTrue(eval_domain(domain, {'x': [1, 2]}))
        self.assertFalse(eval_domain(domain, {'x': [2]}))

        domain = [['x', '=', None]]
        self.assertTrue(eval_domain(domain, {'x': []}))

        domain = [['x', '=', ['foo', 1]]]
        self.assertTrue(eval_domain(domain, {'x': 'foo,1'}))
        self.assertTrue(eval_domain(domain, {'x': ('foo', 1)}))
        self.assertTrue(eval_domain(domain, {'x': ['foo', 1]}))

        domain = [['x', '=', ('foo', 1)]]
        self.assertTrue(eval_domain(domain, {'x': 'foo,1'}))
        self.assertTrue(eval_domain(domain, {'x': ('foo', 1)}))
        self.assertTrue(eval_domain(domain, {'x': ['foo', 1]}))

        domain = [['x', '=', 'foo,1']]
        self.assertTrue(eval_domain(domain, {'x': ['foo', 1]}))
        self.assertTrue(eval_domain(domain, {'x': ('foo', 1)}))

    def test_localize(self):
        domain = [['x', '=', 5]]
        self.assertEqual(localize_domain(domain), [['x', '=', 5]])

        domain = [['x', '=', 5], ['x.code', '=', 7]]
        self.assertEqual(
            localize_domain(domain, 'x'), [['id', '=', 5], ['code', '=', 7]])

        domain = [['x', 'ilike', 'foo%'], ['x.code', '=', 'test']]
        self.assertEqual(
            localize_domain(domain, 'x'),
            [['rec_name', 'ilike', 'foo%'], ['code', '=', 'test']])

        domain = ['OR',
            ['AND', ['x', '>', 7], ['x', '<', 15]], ['x.code', '=', 8]]
        self.assertEqual(
            localize_domain(domain, 'x'),
            ['OR', ['AND', ['id', '>', 7], ['id', '<', 15]], ['code', '=', 8]])

        domain = [['x', 'child_of', [1]]]
        self.assertEqual(
            localize_domain(domain, 'x'), [['x', 'child_of', [1]]])

        domain = [['x', 'child_of', [1], 'y']]
        self.assertEqual(
            localize_domain(domain, 'x'), [['y', 'child_of', [1]]])

        domain = [['x.y', 'child_of', [1], 'parent']]
        self.assertEqual(
            localize_domain(domain, 'x'), [['y', 'child_of', [1], 'parent']])

        domain = [['x.y.z', 'child_of', [1], 'parent', 'model']]
        self.assertEqual(
            localize_domain(domain, 'x'),
            [['y.z', 'child_of', [1], 'parent', 'model']])

        domain = [['x.id', '=', 1, 'y']]
        self.assertEqual(
            localize_domain(domain, 'x', False), [['id', '=', 1, 'y']])
        self.assertEqual(localize_domain(domain, 'x', True), [['id', '=', 1]])

        domain = [['a.b.c', '=', 1, 'y', 'z']]
        self.assertEqual(
            localize_domain(domain, 'x', False), [['b.c', '=', 1, 'y', 'z']])
        self.assertEqual(
            localize_domain(domain, 'x', True), [['b.c', '=', 1, 'z']])

    def test_prepare_reference_domain(self):
        domain = [['x', 'like', 'A%']]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [[]])

        domain = [['x', '=', 'A']]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [[]])

        domain = [['x.y', 'child_of', [1], 'model', 'parent']]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [['x.y', 'child_of', [1], 'model', 'parent']])

        domain = [['x.y', 'like', 'A%', 'model']]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [['x.y', 'like', 'A%', 'model']])

        domain = [['x', '=', 'model,1']]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [['x.id', '=', 1, 'model']])

        domain = [['x', '!=', 'model,1']]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [['x.id', '!=', 1, 'model']])

        domain = [['x', '=', 'model,%']]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [['x.id', '!=', None, 'model']])

        domain = [['x', '!=', 'model,%']]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [['x', 'not like', 'model,%']])

        domain = [['x', 'in',
                ['model_a,1', 'model_b,%', 'model_c,3', 'model_a,2']]]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [['OR',
                ['x.id', 'in', [1, 2], 'model_a'],
                ['x.id', '!=', None, 'model_b'],
                ['x.id', 'in', [3], 'model_c'],
                ]])

        domain = [['x', 'not in',
                ['model_a,1', 'model_b,%', 'model_c,3', 'model_a,2']]]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [['AND',
                ['x.id', 'not in', [1, 2], 'model_a'],
                ['x', 'not like', 'model_b,%'],
                ['x.id', 'not in', [3], 'model_c'],
                ]])

        domain = [['x', 'in', ['model_a,1', 'foo']]]
        self.assertEqual(
            prepare_reference_domain(domain, 'x'),
            [[]])

    def test_extract_models(self):
        domain = [['x', 'like', 'A%']]
        self.assertEqual(extract_reference_models(domain, 'x'), set())
        self.assertEqual(extract_reference_models(domain, 'y'), set())

        domain = [['x', 'like', 'A%', 'model']]
        self.assertEqual(extract_reference_models(domain, 'x'), {'model'})
        self.assertEqual(extract_reference_models(domain, 'y'), set())

        domain = ['OR',
            ['x.y', 'like', 'A%', 'model_A'],
            ['x.z', 'like', 'B%', 'model_B']]
        self.assertEqual(
            extract_reference_models(domain, 'x'), {'model_A', 'model_B'})
        self.assertEqual(extract_reference_models(domain, 'y'), set())

    def test_sortable_values(self):
        def key(values):
            return values

        values = [
            (('a', 1), ('b', None)),
            (('a', 1), ('b', 3)),
            (('a', 1), ('b', 2)),
            ]

        with self.assertRaises(TypeError):
            sorted(values, key=key)
        self.assertEqual(
            sorted(values, key=sortable_values(key)), [
                (('a', 1), ('b', 2)),
                (('a', 1), ('b', 3)),
                (('a', 1), ('b', None)),
                ])

    def test_firstline(self):
        "Test firstline"
        for text, result in [
                ("", ""),
                ("first line\nsecond line", "first line"),
                ("\nsecond line", "second line"),
                ("\n\nthird line", "third line"),
                (" \nsecond line", "second line"),
                ]:
            with self.subTest(text=text, result=result):
                self.assertEqual(firstline(text), result)


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in [ToolsTestCase,
            StringPartitionedTestCase,
            DomainInversionTestCase]:
        suite.addTests(func(testcase))
    suite.addTest(doctest.DocTestSuite(decimal_))
    return suite

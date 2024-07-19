# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import doctest
import sys
import unittest
from copy import deepcopy
from io import BytesIO

import sql
import sql.operators

from trytond.tools import (
    cached_property, decimal_, escape_wildcard, file_open, firstline,
    grouped_slice, is_full_text, is_instance_method, likify, lstrip_wildcard,
    pairwise_longest, reduce_domain, reduce_ids, remove_forbidden_chars,
    rstrip_wildcard, slugify, sortable_values, strip_wildcard, timezone,
    unescape_wildcard)
from trytond.tools.domain_inversion import (
    canonicalize, concat, domain_inversion, eval_domain,
    extract_reference_models, localize_domain, merge, parse,
    prepare_reference_domain, simplify, sort, unique_value)
from trytond.tools.immutabledict import ImmutableDict
from trytond.tools.logging import format_args
from trytond.tools.string_ import LazyString, StringPartitioned

try:
    from trytond.tools import barcode
except ImportError:
    barcode = None
try:
    from trytond.tools import qrcode
except ImportError:
    qrcode = None


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

    def test_grouped_slice(self):
        "Test grouped slice"
        for (values, count, result) in [
                (list(range(10)), 5, [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]]),
                (list(range(5)), 5, [[0, 1, 2, 3, 4]]),
                (list(range(5)), 2, [[0, 1], [2, 3], [4]]),
                ]:
            with self.subTest(values=values, count=count):
                self.assertEqual(
                    list(map(list, grouped_slice(values, count))), result)

    def test_grouped_slice_generator(self):
        "Test grouped slice"
        self.assertEqual(
            list(map(list, grouped_slice((x for x in range(10)), 5))),
            [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]])

    def test_pairwise_longest(self):
        "Test pairwise_longest"
        self.assertEqual(
            list(pairwise_longest(range(3))), [(0, 1), (1, 2), (2, None)])

    def test_pairwise_longest_empty(self):
        "Test pairwise_longest empty"
        self.assertEqual(list(pairwise_longest([])), [])

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

        with self.assertRaisesRegex(
                FileNotFoundError, "No such file or directory:"):
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
                ('%%a%%', '%a%'),
                ('\\%a%', '\\%a'),
                ('\\%a\\%', '\\%a\\%'),
                ('a', 'a'),
                ('', ''),
                (None, None),
                ]:
            with self.subTest(clause=clause):
                self.assertEqual(strip_wildcard(clause), result)

    def test_strip_wildcard_different_wildcard(self):
        'Test strip wildcard with different wildcard'
        self.assertEqual(strip_wildcard('_a_', '_'), 'a')

    def test_lstrip_wildcard(self):
        'Test lstrip wildcard'
        for clause, result in [
                ('%a', 'a'),
                ('%a%', 'a%'),
                ('%%a%', '%a%'),
                ('\\%a%', '\\%a%'),
                ('a', 'a'),
                ('', ''),
                (None, None),
                ]:
            self.assertEqual(
                lstrip_wildcard(clause), result, msg=clause)

    def test_lstrip_wildcard_different_wildcard(self):
        'Test lstrip wildcard with different wildcard'
        self.assertEqual(lstrip_wildcard('_a', '_'), 'a')

    def test_rstrip_wildcard(self):
        'Test rstrip wildcard'
        for clause, result in [
                ('a%', 'a'),
                ('%a%', '%a'),
                ('%a%%', '%a%'),
                ('%a\\%', '%a\\%'),
                ('a', 'a'),
                ('', ''),
                (None, None),
                ]:
            self.assertEqual(
                rstrip_wildcard(clause), result, msg=clause)

    def test_rstrip_wildcard_different_wildcard(self):
        self.assertEqual(rstrip_wildcard('a_', '_'), 'a')

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
                ('%%foo bar%', False),
                ('%foo bar%%', False),
                ('foo%', False),
                ('foo_bar', False),
                ('foo\\_bar', True),
                ]:
            with self.subTest(value=value):
                self.assertEqual(is_full_text(value), result)

    def test_likify(self):
        "Test likify"
        for value, result in [
                ('', '%'),
                ('foo', '%foo%'),
                ('foo%', 'foo%'),
                ('f_o', 'f_o'),
                ('%foo%', '%foo%'),
                ('foo\\_bar', '%foo\\_bar%'),
                ]:
            with self.subTest(value=value):
                self.assertEqual(likify(value), result)

    def test_slugify(self):
        "Test slugify"
        self.assertEqual(slugify('unicode ♥ is ☢'), 'unicode-is')

    def test_slugify_hyphenate(self):
        "Test hyphenate in slugify"
        self.assertEqual(slugify('foo bar', hyphenate='_'), 'foo_bar')

    def test_sortable_values_couple(self):
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

    def test_sortable_values_single(self):
        def key(values):
            return values

        values = [
            (1, None),
            (1, 3),
            (1, 2),
            ]

        with self.assertRaises(TypeError):
            sorted(values, key=key)
        self.assertEqual(
            sorted(values, key=sortable_values(key)), [
                (1, 2),
                (1, 3),
                (1, None),
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

    def test_remove_forbidden_chars(self):
        "Test remove_forbidden_chars"
        for string, result in [
                ("", ""),
                (None, None),
                ("\ttest", "test"),
                (" test ", "test"),
                ]:
            with self.subTest(string=string):
                self.assertEqual(remove_forbidden_chars(string), result)

    def test_get_tzinfo_valid(self):
        "Test get_tzinfo with an valid timezone"
        zi = timezone.get_tzinfo('Europe/Brussels')
        now = dt.datetime(2022, 5, 17, tzinfo=zi)
        self.assertEqual(str(now), "2022-05-17 00:00:00+02:00")

    def test_get_tzinfo_invalid(self):
        "Test get_tzinfo with an invalid timezone"
        zi = timezone.get_tzinfo('foo')
        now = dt.datetime(2022, 5, 17, tzinfo=zi)
        self.assertEqual(str(now), "2022-05-17 00:00:00+00:00")

    def test_availabe_timezones(self):
        "Test available_timezones"
        available_timezones = timezone.available_timezones()
        self.assertTrue(available_timezones)
        self.assertIsInstance(available_timezones, set)

    def test_format_args(self):
        "Test format_args"
        for args, kwargs, short_form, long_form in [
                (tuple(), {}, "()", "()"),
                (('abcdefghijklmnopqrstuvwxyz',), {},
                    "('abcdefghijklmnopq...')",
                    "('abcdefghijklmnopqrstuvwxyz')"),
                ((b'foo',), {}, "(<3 bytes>)", "(b'foo')"),
                (([1, 2, 3, 4], [4, 5, 6, 7], [8, 9, 10, 11]), {},
                    "([1, 2, 3, 4], [4, 5, 6, 7], [8, 9, 10, 11])",
                    "([1, 2, 3, 4], [4, 5, 6, 7], [8, 9, 10, 11])"),
                (([1, 2, 3, 4, 5, 6], [4, 5, 6, 7], [8, 9, 10, 11]), {},
                    "([1, 2, 3, 4, 5, ...], [4, 5, 6, 7], [8, 9, 10, 11])",
                    "([1, 2, 3, 4, 5, 6], [4, 5, 6, 7], [8, 9, 10, 11])"),
                (([1, 2, 3], 'foo'), {'a': '1'},
                    "([1, 2, 3], 'foo', a='1')",
                    "([1, 2, 3], 'foo', a='1')"),
                ((list(range(5)),), {},
                    "([0, 1, 2, 3, 4])",
                    "([0, 1, 2, 3, 4])"),
                ((list(range(6)),), {},
                    "([0, 1, 2, 3, 4, ...])",
                    "([0, 1, 2, 3, 4, 5])"),
                (('a', 'b', 'c', 'd'), {},
                    "('a', 'b', 'c', ...)", "('a', 'b', 'c', 'd')"),
                (([1, [2, [3, [4, [5, [6]]]]]],), {},
                    "([1, [2, [3, [4, [5, ...]]]]])",
                    "([1, [2, [3, [4, [5, [6]]]]]])"),
                (tuple(), {'a': 1, 'b': 2}, "(a=1, b=2)", "(a=1, b=2)"),
                ((list(range(10)), 'foo'), {'a': '1'},
                    "([0, 1, 2, 3, 4, ...], 'foo', a='1')",
                    "([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 'foo', a='1')"),
                ((list(range(4)), 'foo'), {k: k for k in 'abcdefg'},
                    "([0, 1, 2, 3], 'foo', a='a', ...)",
                    "([0, 1, 2, 3], 'foo', a='a', b='b', c='c', d='d',"
                    " e='e', f='f', g='g')"),
                ((list(range(5)), list(range(20, 25))),
                    {k: list(range(7)) for k in 'ab'},
                    "([0, 1, 2, 3, 4], [20, 21, 22, 23, 24], "
                    "a=[0, 1, 2, 3, 4, ...], ...)",
                    "([0, 1, 2, 3, 4], [20, 21, 22, 23, 24], "
                    "a=[0, 1, 2, 3, 4, 5, 6], b=[0, 1, 2, 3, 4, 5, 6])"),
                (tuple(), {k: {i: i for i in range(7)} for k in 'abcd'},
                    "(a={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, ...}, "
                    "b={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, ...}, "
                    "c={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, ...}, ...)",
                    "(a={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}, "
                    "b={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}, "
                    "c={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}, "
                    "d={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6})"),
                ]:
            with self.subTest(form='short', args=args, kwargs=kwargs):
                self.assertEqual(
                    str(format_args(args, kwargs, max_args=3, max_items=5)),
                    short_form)
            with self.subTest(form='long', args=args, kwargs=kwargs):
                self.assertEqual(
                    str(format_args(
                            args, kwargs, verbose=True, max_args=3,
                            max_items=5)),
                    long_form)


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


class ImmutableDictTestCase(unittest.TestCase):
    "Test ImmutableDict"

    def test_setitem(self):
        "__setitem__ not allowed"
        d = ImmutableDict()

        with self.assertRaises(TypeError):
            d['foo'] = 'bar'

    def test_delitem(self):
        "__delitem__ not allowed"
        d = ImmutableDict(foo='bar')

        with self.assertRaises(TypeError):
            del d['foo']

    def test_ior(self):
        "__ior__ not allowed"
        d = ImmutableDict()

        with self.assertRaises(TypeError):
            d |= {'foo': 'bar'}

    def test_clear(self):
        "clear not allowed"
        d = ImmutableDict(foo='bar')

        with self.assertRaises(TypeError):
            d.clear()

    def test_pop(self):
        "pop not allowed"
        d = ImmutableDict(foo='bar')

        with self.assertRaises(TypeError):
            d.pop('foo')

    def test_popitem(self):
        "popitem not allowed"
        d = ImmutableDict(foo='bar')

        with self.assertRaises(TypeError):
            d.popitem('foo')

    def test_setdefault(self):
        "setdefault not allowed"
        d = ImmutableDict()

        with self.assertRaises(TypeError):
            d.setdefault('foo', 'bar')

    def test_update(self):
        "update not allowed"
        d = ImmutableDict()

        with self.assertRaises(TypeError):
            d.update({'foo': 'bar'})

    def test_deepcopy(self):
        "deepcopying should be possible"
        original = ImmutableDict(foo={'a': 1}, bar=2, baz=1.3)
        copy = deepcopy(original)

        self.assertEqual(original, copy)
        self.assertIsNot(original, copy)

        self.assertEqual(original['foo'], copy['foo'])
        self.assertIsNot(original['foo'], copy['foo'])


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
            ['OR', ['x', '=', 3], ['x', '=', 2]])

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

        domain = [[['x', '=', 3], ['y', '=', 4]]]
        self.assertEqual(simplify(domain), [['x', '=', 3], ['y', '=', 4]])

        domain = ['OR', ['x', '=', 3]]
        self.assertEqual(simplify(domain), [['x', '=', 3]])

        domain = ['OR', [['x', '=', 3]], [['y', '=', 5]]]
        self.assertEqual(
            simplify(domain), ['OR', ['x', '=', 3], ['y', '=', 5]])

        domain = ['OR', ['x', '=', 3], ['AND', ['y', '=', 5]]]
        self.assertEqual(
            simplify(domain), ['OR', ['x', '=', 3], ['y', '=', 5]])

        domain = ['OR', ('x', '=', 1), ['OR', ('x', '=', 2), ('x', '=', 3)]]
        self.assertEqual(
            simplify(domain),
            ['OR', ('x', '=', 1), ('x', '=', 2), ('x', '=', 3)])

        domain = [['x', '=', 3], ['OR']]
        self.assertEqual(simplify(domain), [['x', '=', 3]])

        domain = ['OR', ['x', '=', 3], []]
        self.assertEqual(simplify(domain), [])

        domain = ['OR', ['x', '=', 3], ['OR']]
        self.assertEqual(simplify(domain), [])

        domain = [['x', '=', 3], []]
        self.assertEqual(simplify(domain), [['x', '=', 3]])

        domain = [['x', '=', 3], ['AND']]
        self.assertEqual(simplify(domain), [['x', '=', 3]])

        domain = ['AND']
        self.assertEqual(simplify(domain), [])

        domain = ['OR']
        self.assertEqual(simplify(domain), [])

    def test_simplify_deduplicate(self):
        "Test deduplicate"
        clause = ('x', '=', 'x')
        another = ('y', '=', 'y')
        third = ('z', '=', 'z')
        tests = [
            ([], []),
            (['OR', []], []),
            (['AND', []], []),
            ([clause], [clause]),
            (['OR', clause], [clause]),
            ([clause, clause], [clause]),
            (['OR', clause, clause], [clause]),
            ([clause, [clause, clause]], [clause]),
            ([clause, another], [clause, another]),
            (['OR', clause, another], ['OR', clause, another]),
            ([clause, clause, another], [clause, another]),
            ([clause, [clause, clause], another], [clause, another]),
            ([clause, clause, another, another], [clause, another]),
            ([clause, another, clause, another], [clause, another]),
            (
                ['AND', ['OR', clause, another], third],
                ['AND', ['OR', clause, another], third]),
            ]

        for input, expected in tests:
            with self.subTest(input=input):
                self.assertEqual(simplify(input), expected)

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
            ['OR', ['a', '=', 1], ['b', '=', 2]])

    def test_unique_value(self):
        domain = [['a', '=', 1]]
        self.assertEqual(unique_value(domain), (True, 'a', 1))

        domain = [['a', '!=', 1]]
        self.assertFalse(unique_value(domain)[0])

        domain = [['a', '=', 1], ['a', '=', 2]]
        self.assertFalse(unique_value(domain)[0])

        domain = [['a.b', '=', 1]]
        self.assertFalse(unique_value(domain)[0])

        domain = [['a.id', '=', 1, 'model']]
        self.assertEqual(unique_value(domain), (True, 'a.id', ['model', 1]))

        domain = [['a.b.id', '=', 1, 'model']]
        self.assertEqual(unique_value(domain), (False, None, None))
        self.assertEqual(
            unique_value(domain, single_value=False), (False, None, None))

        domain = [['a', 'in', [1]]]
        self.assertEqual(unique_value(domain), (True, 'a', 1))
        self.assertEqual(
            unique_value(domain, single_value=False), (False, None, None))

        domain = [['a', 'in', [1, 2]]]
        self.assertEqual(unique_value(domain), (False, None, None))

        domain = [['a', 'in', []]]
        self.assertEqual(unique_value(domain), (False, None, None))

        domain = [['a.b', 'in', [1]]]
        self.assertEqual(unique_value(domain), (False, None, None))

        domain = [['a.id', 'in', [1], 'model']]
        self.assertEqual(unique_value(domain), (True, 'a.id', ['model', 1]))
        self.assertEqual(
            unique_value(domain, single_value=False), (False, None, None))

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

    def test_sort(self):
        "Test sorting domain"
        for (domain, expected) in [
                ([], []),
                (['AND'], ['AND']),
                (['OR'], ['OR']),
                ([('foo', '=', 1)], [('foo', '=', 1)]),
                ([('foo', '=', 1000), ('foo', '=', 0)],
                    [('foo', '=', 0), ('foo', '=', 1000)]),
                ([('foo', '=', 1), ('foo', '=', None)],
                    [('foo', '=', None), ('foo', '=', 1)]),
                ([('foo', '=', 1), []], [[], ('foo', '=', 1)]),
                ([[[[('foo', '=', 1)]]], [[('foo', '=', 1)]]],
                    [[[('foo', '=', 1)]], [[[('foo', '=', 1)]]]]),
                ([[('foo', '=', 1), ('bar', '=', 2)],
                    [('foo', '=', 1), ('bar', '=', 2), ('baz', '=', 3)]],
                    [[('bar', '=', 2), ('baz', '=', 3), ('foo', '=', 1)],
                        [('bar', '=', 2), ('foo', '=', 1)]]),
                (['OR', ('foo', '=', 1), ('foo', '=', None),
                    ['AND', ('bar', '=', 2), ('baz', '=', 3)]],
                    ['OR', ('foo', '=', None), ('foo', '=', 1),
                        ['AND', ('bar', '=', 2), ('baz', '=', 3)]]),
                ([('foo', '=', 'bar'), ('foo', '=', None)],
                    [('foo', '=', None), ('foo', '=', 'bar')]),
                ]:
            with self.subTest(domain=domain):
                self.assertEqual(sort(domain), expected)

    def test_canonicalize(self):
        "Test domain canonicalization"
        for (domain, expected) in [
                ([], []),
                (['AND'], []),
                (['OR'], []),
                ([('foo', '=', 1), ('bar', '=', 2)],
                    [('bar', '=', 2), ('foo', '=', 1)]),
                ([[('foo', '=', 1)]], [('foo', '=', 1)]),
                (['AND', ['OR', ('bar', '=', 2), ('baz', '=', 3)],
                    ('foo', '=', 1)],
                    [('foo', '=', 1),
                        ['OR', ('bar', '=', 2), ('baz', '=', 3)]]),
                (['OR', ['AND', ('bar', '=', 2), ('baz', '=', 3)],
                    ('foo', '=', 1)],
                    ['OR', ('foo', '=', 1),
                        [('bar', '=', 2), ('baz', '=', 3)]]),
                (['AND', ['AND', ('bar', '=', 2), ('baz', '=', 3)],
                    ('foo', '=', 1)],
                    [('bar', '=', 2), ('baz', '=', 3), ('foo', '=', 1)]),
                (['OR', ['OR', ('bar', '=', 2), ('baz', '=', 3)],
                    ('foo', '=', 1)],
                    ['OR', ('bar', '=', 2), ('baz', '=', 3), ('foo', '=', 1)]),
                ]:
            with self.subTest(domain=domain):
                self.assertEqual(canonicalize(domain), expected)


@unittest.skipUnless(barcode, "required barcode")
class BarcodeTestCase(unittest.TestCase):
    "Test barcode module"

    def test_generate_svg(self):
        "Test generate SVG"
        image = barcode.generate_svg('ean', "8749903790831")
        self.assertIsInstance(image, BytesIO)
        self.assertIsNotNone(image.getvalue())

    def test_generate_png(self):
        "Test generate PNG"
        image = barcode.generate_png('ean', "8749903790831")
        self.assertIsInstance(image, BytesIO)
        self.assertIsNotNone(image.getvalue())


@unittest.skipUnless(qrcode, "required qrcode")
class QRCodeTestCase(unittest.TestCase):
    "Test qrcode module"

    def test_generate_svg(self):
        "Test generate SVG"
        image = qrcode.generate_svg("Tryton")
        self.assertIsInstance(image, BytesIO)
        self.assertIsNotNone(image.getvalue())

    def test_generate_png(self):
        "Test generate PNG"
        image = qrcode.generate_png("Tryton")
        self.assertIsInstance(image, BytesIO)
        self.assertIsNotNone(image.getvalue())


class CachedProperty:
    _count = 0

    def get_count(self):
        self._count += 1
        return self._count

    cached_count = cached_property(get_count)


class CachedPropertySlots:
    __slots__ = ('_count', '__weakref__')

    def __init__(self):
        self._count = 0

    def get_count(self):
        self._count += 1
        return self._count

    cached_count = cached_property(get_count)


class CachedPropertyTestCase(unittest.TestCase):
    "Test cached_property"

    def test_cached_property_clear(self):
        "Test clear cached property"
        item = CachedProperty()

        self.assertEqual(item.cached_count, 1)
        del item.cached_count
        self.assertEqual(item.cached_count, 2)

    def test_cached_property_with_slots(self):
        "Test cached property with slots"
        item = CachedPropertySlots()

        self.assertEqual(item.cached_count, 1)
        self.assertEqual(item.cached_count, 1)
        self.assertEqual(item.get_count(), 2)
        self.assertEqual(item.cached_count, 1)

    def test_cached_property_with_slots_clear(self):
        "Test clear cached property with slots"
        item = CachedPropertySlots()

        self.assertEqual(item.cached_count, 1)
        del item.cached_count
        self.assertEqual(item.cached_count, 2)


def load_tests(loader, tests, pattern):
    tests.addTest(doctest.DocTestSuite(decimal_))
    return tests

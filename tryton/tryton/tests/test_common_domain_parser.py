# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from decimal import Decimal
from unittest import TestCase

from tryton.common import untimezoned_date
from tryton.common.domain_parser import (
    group_operator, quote, split_target_value, convert_value, format_value,
    complete_value, parenthesize, rlist, operatorize, DomainParser, udlex,
    likify)


class DomainParserTestCase(TestCase):
    "Test common domain_parser"

    def test_group_operator(self):
        "Test group_operator"
        self.assertEqual(
            list(group_operator(iter(['a', '>', '=']))), ['a', '>='])
        self.assertEqual(
            list(group_operator(iter(['>', '=', 'b']))), ['>=', 'b'])
        self.assertEqual(
            list(group_operator(iter(['a', '=', 'b']))), ['a', '=', 'b'])
        self.assertEqual(
            list(group_operator(iter(['a', '>', '=', 'b']))), ['a', '>=', 'b'])
        self.assertEqual(
            list(group_operator(iter(['a', '>', '=', '=']))), ['a', '>=', '='])

    def test_likify(self):
        "Test likify"
        for value, result in [
                ('', '%'),
                ('foo', '%foo%'),
                ('foo%', 'foo%'),
                ('foo_bar', 'foo_bar'),
                ('foo\\%', '%foo\\%%'),
                ('foo\\_bar', '%foo\\_bar%'),
                ]:
            with self.subTest(value=value):
                self.assertEqual(likify(value), result)

    def test_quote(self):
        "Test quote"
        self.assertEqual(quote('test'), 'test')
        self.assertEqual(quote('foo bar'), '"foo bar"')
        self.assertEqual(quote('"foo"'), '\\\"foo\\\"')
        self.assertEqual(quote('foo\\bar'), 'foo\\\\bar')

    def test_split_target_value(self):
        "Test split_target_value"
        field = {
            'type': 'reference',
            'selection': [
                ('spam', 'Spam'),
                ('ham', 'Ham'),
                ('e', 'Eggs'),
                ]
            }
        for value, result in (
                ('Spam', (None, 'Spam')),
                ('foo', (None, 'foo')),
                ('Spam,', ('spam', '')),
                ('Ham,bar', ('ham', 'bar')),
                ('Eggs,foo', ('e', 'foo')),
                ):
            self.assertEqual(
                split_target_value(field, value), result,
                msg="split_target_value(%r, %r)" % (field, value))

    def test_convert_boolean(self):
        "Test convert boolean"
        field = {
            'type': 'boolean',
            }
        for value, result in (
                ('Y', True),
                ('yes', True),
                ('t', True),
                ('1', True),
                ('N', False),
                ('False', False),
                ('no', False),
                ('0', False),
                (None, None),
                ):
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))

    def test_convert_float(self):
        "Test convert float"
        field = {
            'type': 'float',
            }
        for value, result in (
                ('1', 1.0),
                ('1.5', 1.5),
                ('', None),
                ('test', None),
                (None, None),
                ):
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))

    def test_convert_float_factor(self):
        "Test convert float with factor"
        field = {
            'type': 'float',
            'factor': '100',
            }
        self.assertEqual(convert_value(field, '42'), 0.42)

    def test_convert_integer(self):
        "Test convert integer"
        field = {
            'type': 'integer',
            }
        for value, result in (
                ('1', 1),
                ('1.5', 1),
                ('', None),
                ('test', None),
                (None, None),
                ):
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))

    def test_convert_integer_factor(self):
        "Test convert integer with factor"
        field = {
            'type': 'integer',
            'factor': '2',
            }
        self.assertEqual(convert_value(field, '6'), 3)

    def test_convert_numeric(self):
        "Test convert numeric"
        field = {
            'type': 'numeric',
            }
        for value, result in (
                ('1', Decimal(1)),
                ('1.5', Decimal('1.5')),
                ('', None),
                ('test', None),
                (None, None),
                ):
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))

    def test_convert_numeric_factor(self):
        "Test convert numeric with factor"
        field = {
            'type': 'numeric',
            'factor': '5',
            }
        self.assertEqual(convert_value(field, '1'), Decimal('0.2'))

    def test_convert_selection(self):
        "Test convert selection"
        field = {
            'type': 'selection',
            'selection': [
                ('male', 'Male'),
                ('female', 'Female'),
                ],
            }
        field_with_empty = field.copy()
        field_with_empty['selection'] = (field_with_empty['selection']
            + [('', '')])
        for value, result in (
                ('Male', 'male'),
                ('male', 'male'),
                ('test', 'test'),
                (None, None),
                ('', ''),
                ):
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))
            self.assertEqual(
                convert_value(field_with_empty, value), result,
                msg="convert_value(%r, %r)" % (field_with_empty, value))

    def test_convert_datetime(self):
        "Test convert datetime"
        field = {
            'type': 'datetime',
            'format': '"%H:%M:%S"',
            }
        for value, result in (
                ('12/04/2002', untimezoned_date(dt.datetime(2002, 12, 4))),
                ('12/04/2002 12:30:00', untimezoned_date(
                        dt.datetime(2002, 12, 4, 12, 30))),
                ('02/03/04', untimezoned_date(dt.datetime(2004, 2, 3))),
                ('02/03/04 05:06:07', untimezoned_date(
                        dt.datetime(2004, 2, 3, 5, 6, 7))),
                ('test', None),
                (None, None),
                ):
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))

    def test_convert_date(self):
        "Test convert date"
        field = {
            'type': 'date',
            }
        for value, result in (
                ('12/04/2002', dt.date(2002, 12, 4)),
                ('test', None),
                (None, None),
                ):
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))

    def test_convert_time(self):
        "Test convert time"
        field = {
            'type': 'time',
            'format': '"%H:%M:%S"',
            }
        for value, result in (
                ('12:30:00', dt.time(12, 30, 0)),
                ('test', None),
                (None, None),
                ):
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))

    def test_convert_timedelta(self):
        "Test convert timedelta"
        field = {
            'type': 'timedelta',
            }
        for value, result in [
                ('1d 2:00', dt.timedelta(days=1, hours=2)),
                ('foo', dt.timedelta()),
                (None, None),
                ]:
            self.assertEqual(
                convert_value(field, value), result,
                msg="convert_value(%r, %r)" % (field, value))

    def test_format_boolean(self):
        "Test format boolean"
        field = {
            'type': 'boolean',
            }
        for value, result in (
                (True, 'True'),
                (False, 'False'),
                (None, ''),
                ):
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))

    def test_format_integer(self):
        "Test format integer"
        field = {
            'type': 'integer',
            }
        for value, result in (
                (1, '1'),
                (1.5, '1'),
                (0, '0'),
                (0.0, '0'),
                (False, ''),
                (None, ''),
                ):
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))

    def test_format_integer_factor(self):
        "Test format integer with factor"
        field = {
            'type': 'integer',
            'factor': '2',
            }
        self.assertEqual(format_value(field, 3), '6')

    def test_format_float(self):
        "Test format float"
        field = {
            'type': 'float',
            }
        for value, result in (
                (1, '1'),
                (1.5, '1.5'),
                (1.50, '1.5'),
                (150.79, '150.79'),
                (0, '0'),
                (0.0, '0'),
                (False, ''),
                (None, ''),
                (1e-12, '0.000000000001'),
                (1.0579e-10, '0.00000000010579'),
                ):
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))

    def test_format_float_factor(self):
        "Test format float with factor"
        field = {
            'type': 'float',
            'factor': '100',
            }
        self.assertEqual(format_value(field, 0.42), '42')

    def test_format_numeric(self):
        "Test format numeric"
        field = {
            'type': 'numeric',
            }
        for value, result in (
                (Decimal(1), '1'),
                (Decimal('1.5'), '1.5'),
                (Decimal('1.50'), '1.5'),
                (Decimal('150.79'), '150.79'),
                (Decimal(0), '0'),
                (Decimal('0.0'), '0'),
                (False, ''),
                (None, ''),
                ):
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))

    def test_format_numeric_factor(self):
        "Test format numeric with factor"
        field = {
            'type': 'numeric',
            'factor': '5',
            }
        self.assertEqual(format_value(field, Decimal('0.2')), '1')

    def test_format_selection(self):
        "Test format selection"
        field = {
            'type': 'selection',
            'selection': [
                ('male', 'Male'),
                ('female', 'Female'),
                ],
            }
        field_with_empty = field.copy()
        field_with_empty['selection'] = (field_with_empty['selection']
            + [('', '')])
        for value, result in (
                ('male', 'Male'),
                ('test', 'test'),
                (False, ''),
                (None, ''),
                ('', ''),
                ):
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))
            self.assertEqual(
                format_value(field_with_empty, value), result,
                msg="format_value(%r, %r)" % (field_with_empty, value))

    def test_format_datetime(self):
        "Test format datetime"
        field = {
            'type': 'datetime',
            'format': '"%H:%M:%S"',
            }
        for value, result in (
                (dt.date(2002, 12, 4), dt.date(2002, 12, 4).strftime('%x')),
                (untimezoned_date(dt.datetime(2002, 12, 4)),
                    dt.date(2002, 12, 4).strftime('%x')),
                (untimezoned_date(dt.datetime(2002, 12, 4, 12, 30)),
                    dt.datetime(2002, 12, 4, 12, 30).strftime(
                        '"%x %H:%M:%S"')),
                (False, ''),
                (None, ''),
                ):
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))

    def test_format_date(self):
        "Test format date"
        field = {
            'type': 'date',
            }
        for value, result in (
                (dt.date(2002, 12, 4), dt.date(2002, 12, 4).strftime('%x')),
                (False, ''),
                (None, ''),
                ):
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))

    def test_format_time(self):
        "Test format time"
        field = {
            'type': 'time',
            'format': '"%H:%M:%S"',
            }
        for value, result in (
                (dt.time(12, 30, 0), '"12:30:00"'),
                (False, ''),
                (None, ''),
                ):
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))

    def test_format_timedelta(self):
        "Test format timedelta"
        field = {
            'type': 'timedelta',
            }
        for value, result in [
                (dt.timedelta(days=1, hours=2), '"1d 02:00"'),
                (dt.timedelta(), ''),
                (None, ''),
                ('', ''),
                ]:
            self.assertEqual(
                format_value(field, value), result,
                msg="format_value(%r, %r)" % (field, value))

    def test_complete_boolean(self):
        "Test complete boolean"
        field = {
            'type': 'boolean',
            }
        for value, result in [
                (None, [True, False]),
                (True, [False]),
                (False, [True]),
                ]:
            self.assertEqual(
                list(complete_value(field, value)), result,
                msg="complete_value(%r, %r)" % (field, value))

    def test_complete_selection(self):
        "Test complete selection"
        field = {
            'type': 'selection',
            'selection': [
                ('male', 'Male'),
                ('female', 'Female'),
                ],
            }
        for value, result in (
                ('m', ['male']),
                ('test', []),
                ('', ['male', 'female']),
                (None, ['male', 'female']),
                (['male', 'f'], [['male', 'female']]),
                (['male', None], [['male', 'male'], ['male', 'female']]),
                ):
            self.assertEqual(
                list(complete_value(field, value)), result,
                msg="complete_value(%r, %r)" % (field, value))

        field_with_empty = field.copy()
        field_with_empty['selection'] = (field_with_empty['selection']
            + [('', '')])
        for value, result in (
                ('m', ['male']),
                ('test', []),
                ('', ['male', 'female', '']),
                (None, ['male', 'female', '']),
                (['male', 'f'], [['male', 'female']]),
                ):
            self.assertEqual(
                list(complete_value(field_with_empty, value)), result,
                msg="complete_value(%r, %r)" % (field_with_empty, value))

    def test_complete_reference(self):
        "Test complete reference"
        field = {
            'type': 'reference',
            'selection': [
                ('spam', 'Spam'),
                ('ham', 'Ham'),
                ('', ''),
                ],
            }
        for value, result in (
                ('s', ['%spam%']),
                ('test', []),
                ('', ['%spam%', '%ham%', '%']),
                (None, ['%spam%', '%ham%', '%']),
                (['spam', 'h'], [['spam', 'ham']]),
                ):
            self.assertEqual(
                list(complete_value(field, value)), result,
                msg="complete_value(%r, %r)" % (field, value))

    def test_parenthesize(self):
        for value, result in (
                (['a'], ['a']),
                (['a', 'b'], ['a', 'b']),
                (['(', 'a', ')'], [['a']]),
                (['a', 'b', '(', 'c', '(', 'd', 'e', ')', 'f', ')', 'g'],
                    ['a', 'b', ['c', ['d', 'e'], 'f'], 'g']),
                (['a', 'b', '(', 'c'], ['a', 'b', ['c']]),
                (['a', 'b', '(', 'c', '(', 'd', 'e', ')', 'f'],
                    ['a', 'b', ['c', ['d', 'e'], 'f']]),
                (['a', 'b', ')'], ['a', 'b']),
                (['a', 'b', ')', 'c', ')', 'd)'], ['a', 'b']),
                ):
            self.assertEqual(
                rlist(parenthesize(iter(value))), result,
                msg="parenthesize(%r)" % value)

    def test_operatorize(self):
        "Test operatorize"
        a = ('a', 'a', 'a')
        b = ('b', 'b', 'b')
        c = ('c', 'c', 'c')
        null_ = ('d', None, 'x')
        double_null_ = ('e', None, None)
        for value, result in (
                (['a'], ['a']),
                (['a', 'or', 'b'], [['OR', 'a', 'b']]),
                (['a', 'or', 'b', 'or', 'c'], [['OR', ['OR', 'a', 'b'], 'c']]),
                (['a', 'b', 'or', 'c'], ['a', ['OR', 'b', 'c']]),
                (['a', 'or', 'b', 'c'], [['OR', 'a', 'b'], 'c']),
                (['a', iter(['b', 'c'])], ['a', ['b', 'c']]),
                (['a', iter(['b', 'c']), 'd'], ['a', ['b', 'c'], 'd']),
                (['a', 'or', iter(['b', 'c'])], [['OR', 'a', ['b', 'c']]]),
                (['a', 'or', iter(['b', 'c']), 'd'],
                    [['OR', 'a', ['b', 'c']], 'd']),
                (['a', iter(['b', 'c']), 'or', 'd'],
                    ['a', ['OR', ['b', 'c'], 'd']]),
                (['a', 'or', iter(['b', 'or', 'c'])],
                    [['OR', 'a', [['OR', 'b', 'c']]]]),
                (['or'], []),
                (['or', 'a'], ['a']),
                (['a', iter(['or', 'b'])], ['a', ['b']]),
                (['a', 'or', 'or', 'b'], [['OR', 'a', 'b']]),
                (['or', 'or', 'a'], ['a']),
                (['or', 'or', 'a', 'b'], ['a', 'b']),
                (['or', 'or', 'a', 'or', 'b'], [['OR', 'a', 'b']]),
                (['a', iter(['b', 'or', 'c'])], ['a', [['OR', 'b', 'c']]]),
                ([a, iter([b, ('or',), c])], [a, [['OR', b, c]]]),
                (['a', iter(['b', 'or'])], ['a', [['OR', 'b']]]),
                ([null_], [null_]),
                ([null_, 'or', double_null_], [['OR', null_, double_null_]]),
                ):
            self.assertEqual(
                rlist(operatorize(iter(value))), result,
                msg="operatorize(%r)" % value)

    def test_stringable(self):
        "Test stringable"
        dom = DomainParser({
                'name': {
                    'string': 'Name',
                    'type': 'char',
                    },
                'multiselection': {
                    'string': "MultiSelection",
                    'type': 'multiselection',
                    'selection': [
                        ('foo', "Foo"),
                        ('bar', "Bar"),
                        ('baz', "Baz"),
                        ],
                    },
                'relation': {
                    'string': 'Relation',
                    'type': 'many2one',
                    'relation_fields': {
                        'name': {
                            'string': "Name",
                            'type': 'char',
                            },
                        },
                    },
                'relations': {
                    'string': 'Relations',
                    'type': 'many2many',
                    },
                })
        valid = ('name', '=', 'Doe')
        invalid = ('surname', '=', 'John')
        self.assertTrue(dom.stringable([valid]))
        self.assertFalse(dom.stringable([invalid]))
        self.assertTrue(dom.stringable(['AND', valid]))
        self.assertFalse(dom.stringable(['AND', valid, invalid]))
        self.assertTrue(dom.stringable([[valid]]))
        self.assertFalse(dom.stringable([[valid], [invalid]]))
        self.assertTrue(dom.stringable([('multiselection', '=', None)]))
        self.assertTrue(dom.stringable([('multiselection', '=', '')]))
        self.assertFalse(dom.stringable([('multiselection', '=', 'foo')]))
        self.assertTrue(dom.stringable([('multiselection', '=', ['foo'])]))
        self.assertTrue(dom.stringable([('relation', '=', None)]))
        self.assertTrue(dom.stringable([('relation', '=', "Foo")]))
        self.assertTrue(dom.stringable([('relation.rec_name', '=', "Foo")]))
        self.assertFalse(dom.stringable([('relation', '=', 1)]))
        self.assertTrue(dom.stringable([('relations', '=', "Foo")]))
        self.assertTrue(dom.stringable([('relations', 'in', ["Foo"])]))
        self.assertFalse(dom.stringable([('relations', 'in', [42])]))
        self.assertTrue(dom.stringable([('relation.name', '=', "Foo")]))

    def test_string(self):
        dom = DomainParser({
                'name': {
                    'string': 'Name',
                    'type': 'char',
                    },
                'surname': {
                    'string': '(Sur)Name',
                    'type': 'char',
                    },
                'date': {
                    'string': 'Date',
                    'type': 'date',
                    },
                'selection': {
                    'string': 'Selection',
                    'type': 'selection',
                    'selection': [
                        ('male', 'Male'),
                        ('female', 'Female'),
                        ('', ''),
                        ],
                    },
                'multiselection': {
                    'string': "MultiSelection",
                    'type': 'multiselection',
                    'selection': [
                        ('foo', "Foo"),
                        ('bar', "Bar"),
                        ('baz', "Baz"),
                        ],
                    },
                'reference': {
                    'string': 'Reference',
                    'type': 'reference',
                    'selection': [
                        ('spam', 'Spam'),
                        ('ham', 'Ham'),
                        ]
                    },
                'many2one': {
                    'string': 'Many2One',
                    'name': 'many2one',
                    'type': 'many2one',
                    'relation_fields': {
                        'name': {
                            'string': "Name",
                            'type': 'char',
                            },
                        },
                    },
                })
        self.assertEqual(dom.string([('name', '=', 'Doe')]), 'Name: =Doe')
        self.assertEqual(dom.string([('name', '=', None)]), 'Name: =')
        self.assertEqual(dom.string([('name', '=', '')]), 'Name: =""')
        self.assertEqual(dom.string([('name', 'ilike', '%')]), 'Name: ')
        self.assertEqual(dom.string([('name', 'ilike', '%Doe%')]), 'Name: Doe')
        self.assertEqual(
            dom.string([('name', 'ilike', '%<%')]), 'Name: "" "<"')
        self.assertEqual(dom.string([('name', 'ilike', 'Doe')]), 'Name: =Doe')
        self.assertEqual(dom.string([('name', 'ilike', 'Doe%')]), 'Name: Doe%')
        self.assertEqual(
            dom.string([('name', 'ilike', 'Doe%%')]), 'Name: =Doe%')
        self.assertEqual(
            dom.string([('name', 'not ilike', '%Doe%')]), 'Name: !Doe')
        self.assertEqual(
            dom.string([('name', 'in', ['John', 'Jane'])]), 'Name: John;Jane')
        self.assertEqual(
            dom.string([('name', 'not in', ['John', 'Jane'])]),
            'Name: !John;Jane')
        self.assertEqual(
            dom.string([
                    ('name', 'ilike', '%Doe%'),
                    ('name', 'ilike', '%Jane%')]),
            'Name: Doe Name: Jane')
        self.assertEqual(
            dom.string(['AND',
                ('name', 'ilike', '%Doe%'),
                ('name', 'ilike', '%Jane%')]),
            'Name: Doe Name: Jane')
        self.assertEqual(
            dom.string(['OR',
                ('name', 'ilike', '%Doe%'),
                ('name', 'ilike', '%Jane%')]),
            'Name: Doe or Name: Jane')
        self.assertEqual(
            dom.string([
                ('name', 'ilike', '%Doe%'),
                ['OR',
                    ('name', 'ilike', '%John%'),
                    ('name', 'ilike', '%Jane%')]]),
            'Name: Doe (Name: John or Name: Jane)')
        self.assertEqual(dom.string([]), '')
        self.assertEqual(
            dom.string([('surname', 'ilike', '%Doe%')]), '"(Sur)Name": Doe')
        self.assertEqual(
            dom.string([('date', '>=', dt.date(2012, 10, 24))]),
            dt.date(2012, 10, 24).strftime('Date: >=%x'))
        self.assertEqual(dom.string([('selection', '=', '')]), 'Selection: ')
        self.assertEqual(dom.string([('selection', '=', None)]), 'Selection: ')
        self.assertEqual(
            dom.string([('selection', '!=', '')]), 'Selection: !""')
        self.assertEqual(
            dom.string([('selection', '=', 'male')]), 'Selection: Male')
        self.assertEqual(
            dom.string([('selection', '!=', 'male')]), 'Selection: !Male')
        self.assertEqual(
            dom.string([('multiselection', '=', None)]), "MultiSelection: =")
        self.assertEqual(
            dom.string([('multiselection', '=', '')]), "MultiSelection: =")
        self.assertEqual(
            dom.string([('multiselection', '!=', '')]), "MultiSelection: !=")
        self.assertEqual(
            dom.string([('multiselection', '=', ['foo'])]),
            "MultiSelection: =Foo")
        self.assertEqual(
            dom.string([('multiselection', '!=', ['foo'])]),
            "MultiSelection: !=Foo")
        self.assertEqual(
            dom.string([('multiselection', '=', ['foo', 'bar'])]),
            "MultiSelection: =Foo;Bar")
        self.assertEqual(
            dom.string([('multiselection', '!=', ['foo', 'bar'])]),
            "MultiSelection: !=Foo;Bar")
        self.assertEqual(
            dom.string([('multiselection', 'in', ['foo'])]),
            "MultiSelection: Foo")
        self.assertEqual(
            dom.string([('multiselection', 'not in', ['foo'])]),
            "MultiSelection: !Foo")
        self.assertEqual(
            dom.string([('multiselection', '=', ['foo', 'bar'])]),
            "MultiSelection: =Foo;Bar")
        self.assertEqual(
            dom.string([('multiselection', '!=', ['foo', 'bar'])]),
            "MultiSelection: !=Foo;Bar")
        self.assertEqual(
            dom.string([('multiselection', 'in', ['foo', 'bar'])]),
            "MultiSelection: Foo;Bar")
        self.assertEqual(
            dom.string([('multiselection', 'not in', ['foo', 'bar'])]),
            "MultiSelection: !Foo;Bar")
        self.assertEqual(
            dom.string([('reference', 'ilike', '%foo%')]),
            'Reference: foo')
        self.assertEqual(
            dom.string([('reference.rec_name', 'ilike', '%bar%', 'spam')]),
            'Reference: Spam,bar')
        self.assertEqual(
            dom.string([('reference', 'in', ['foo', 'bar'])]),
            'Reference: foo;bar')
        self.assertEqual(
            dom.string([('many2one', 'ilike', '%John%')]), 'Many2One: John')
        self.assertEqual(
            dom.string([('many2one.rec_name', 'in', ['John', 'Jane'])]),
            'Many2One: John;Jane')
        self.assertEqual(
            dom.string([('many2one.name', 'ilike', '%Foo%')]),
            "Many2One.Name: Foo")

    def test_group(self):
        "Test group"
        dom = DomainParser({
                'name': {
                    'string': 'Name',
                    },
                'firstname': {
                    'string': 'First Name',
                    },
                'surname': {
                    'string': '(Sur)Name',
                    },
                'relation': {
                    'string': "Relation",
                    'relation': 'relation',
                    'relation_fields': {
                        'name': {
                            'string': "Name",
                            },
                        },
                    },
                })
        self.assertEqual(
            rlist(dom.group(udlex('Name: Doe'))), [('Name', None, 'Doe')])
        self.assertEqual(
            rlist(dom.group(udlex('"(Sur)Name": Doe'))), [
                ('(Sur)Name', None, 'Doe'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: Doe Name: John'))), [
                ('Name', None, 'Doe'),
                ('Name', None, 'John'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: Name: John'))), [
                ('Name', None, None),
                ('Name', None, 'John')])
        self.assertEqual(
            rlist(dom.group(udlex('First Name: John'))), [
                ('First Name', None, 'John'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: Doe First Name: John'))), [
                ('Name', None, 'Doe'),
                ('First Name', None, 'John'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('First Name: John Name: Doe'))), [
                ('First Name', None, 'John'),
                ('Name', None, 'Doe'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('First Name: John First Name: Jane'))), [
                ('First Name', None, 'John'),
                ('First Name', None, 'Jane'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: John Doe'))), [
                ('Name', None, 'John'),
                ('Doe',),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: "John Doe"'))), [
                ('Name', None, 'John Doe'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Doe Name: John'))), [
                ('Doe',),
                ('Name', None, 'John'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: =Doe'))), [('Name', '=', 'Doe')])
        self.assertEqual(
            rlist(dom.group(udlex('Name: =Doe Name: >John'))), [
                ('Name', '=', 'Doe'),
                ('Name', '>', 'John'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('First Name: =John First Name: =Jane'))), [
                ('First Name', '=', 'John'),
                ('First Name', '=', 'Jane'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: John;Jane'))), [
                ('Name', None, ['John', 'Jane'])
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: John;'))), [
                ('Name', None, ['John'])
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: John;Jane Name: Doe'))), [
                ('Name', None, ['John', 'Jane']),
                ('Name', None, 'Doe'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: John; Name: Doe'))), [
                ('Name', None, ['John']),
                ('Name', None, 'Doe'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name:'))), [
                ('Name', None, None),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: ='))), [
                ('Name', '=', None),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: =""'))), [
                ('Name', '=', ''),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: = ""'))), [
                ('Name', '=', ''),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: = Name: Doe'))), [
                ('Name', '=', None),
                ('Name', None, 'Doe'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: \\"foo\\"'))), [
                ('Name', None, '"foo"'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Name: "" <'))), [
                ('Name', '', '<'),
                ])
        self.assertEqual(
            rlist(dom.group(udlex('Relation.Name: Test'))), [
                ('Relation.Name', None, "Test"),
                ])

    def test_parse_clause(self):
        "Test parse clause"
        dom = DomainParser({
                'name': {
                    'string': 'Name',
                    'name': 'name',
                    'type': 'char',
                    },
                'integer': {
                    'string': 'Integer',
                    'name': 'integer',
                    'type': 'integer',
                    },
                'selection': {
                    'string': 'Selection',
                    'name': 'selection',
                    'type': 'selection',
                    'selection': [
                        ('male', 'Male'),
                        ('female', 'Female'),
                        ],
                    },
                'multiselection': {
                    'string': "MultiSelection",
                    'name': 'multiselection',
                    'type': 'multiselection',
                    'selection': [
                        ('foo', "Foo"),
                        ('bar', "Bar"),
                        ('baz', "Baz"),
                        ],
                    },
                'reference': {
                    'string': 'Reference',
                    'name': 'reference',
                    'type': 'reference',
                    'selection': [
                        ('spam', 'Spam'),
                        ('ham', 'Ham'),
                        ]
                    },
                'many2one': {
                    'string': 'Many2One',
                    'name': 'many2one',
                    'type': 'many2one',
                    },
                'relation': {
                    'string': "Relation",
                    'relation': 'relation',
                    'name': 'relation',
                    'relation_fields': {
                        'name': {
                            'string': "Name",
                            'name': 'name',
                            'type': 'char',
                            },
                        },
                    },
                })
        self.assertEqual(
            rlist(dom.parse_clause([('John',)])), [
                ('rec_name', 'ilike', '%John%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Name', None, None)])), [
                ('name', 'ilike', '%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Name', '', None)])), [
                ('name', 'ilike', '%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Name', '=', None)])), [
                ('name', '=', None),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Name', '=', '')])), [
                ('name', '=', ''),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Name', None, 'Doe')])), [
                ('name', 'ilike', '%Doe%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Name', '!', 'Doe')])), [
                ('name', 'not ilike', '%Doe%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Name', None, ['John', 'Jane'])])), [
                ('name', 'in', ['John', 'Jane']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Name', '!', ['John', 'Jane'])])), [
                ('name', 'not in', ['John', 'Jane']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Selection', None, None)])), [
                ('selection', '=', None),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Selection', None, '')])), [
                ('selection', '=', ''),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Selection', None, ['Male', 'Female'])])),
            [('selection', 'in', ['male', 'female'])])
        self.assertEqual(
            rlist(dom.parse_clause([('MultiSelection', None, None)])), [
                ('multiselection', '=', None),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('MultiSelection', None, '')])), [
                ('multiselection', 'in', ['']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('MultiSelection', '=', '')])), [
                ('multiselection', '=', ['']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('MultiSelection', '!', '')])), [
                ('multiselection', 'not in', ['']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('MultiSelection', '!=', '')])), [
                ('multiselection', '!=', ['']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause(
                [('MultiSelection', None, ['Foo', 'Bar'])])), [
                ('multiselection', 'in', ['foo', 'bar']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause(
                [('MultiSelection', '=', ['Foo', 'Bar'])])), [
                ('multiselection', '=', ['foo', 'bar']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause(
                [('MultiSelection', '!', ['Foo', 'Bar'])])), [
                ('multiselection', 'not in', ['foo', 'bar']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause(
                [('MultiSelection', '!=', ['Foo', 'Bar'])])), [
                ('multiselection', '!=', ['foo', 'bar']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Integer', None, None)])), [
                ('integer', '=', None),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Integer', None, '3..5')])), [[
                    ('integer', '>=', 3),
                    ('integer', '<=', 5),
                    ]])
        self.assertEqual(
            rlist(dom.parse_clause([('Reference', None, 'foo')])), [
                ('reference', 'ilike', '%foo%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Reference', None, 'Spam')])), [
                ('reference', 'ilike', '%spam%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Reference', None, 'Spam,bar')])), [
                ('reference.rec_name', 'ilike', '%bar%', 'spam'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Reference', None, ['foo', 'bar'])])), [
                ('reference', 'in', ['foo', 'bar']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause(['OR',
                    ('Name', None, 'John'), ('Name', None, 'Jane')])),
            ['OR',
                ('name', 'ilike', '%John%'),
                ('name', 'ilike', '%Jane%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Many2One', None, 'John')])), [
                ('many2one', 'ilike', '%John%'),
                ])
        self.assertEqual(
            rlist(dom.parse_clause([('Many2One', None, ['John', 'Jane'])])), [
                ('many2one.rec_name', 'in', ['John', 'Jane']),
                ])
        self.assertEqual(
            rlist(dom.parse_clause(iter([iter([['John']])]))), [
                [('rec_name', 'ilike', '%John%')]])
        self.assertEqual(
            rlist(dom.parse_clause(iter([['Relation.Name', None, "Test"]]))),
            [('relation.name', 'ilike', "%Test%")])
        self.assertEqual(
            rlist(dom.parse_clause(iter([['OR']]))),
            [('rec_name', 'ilike', "%OR%")])
        self.assertEqual(
            rlist(dom.parse_clause(iter([['AND']]))),
            [('rec_name', 'ilike', "%AND%")])

    def test_completion_char(self):
        "Test completion char"
        dom = DomainParser({
                'name': {
                    'string': 'Name',
                    'name': 'name',
                    'type': 'char',
                    },
                })
        self.assertEqual(list(dom.completion('Nam')), ['Name: '])
        self.assertEqual(list(dom.completion('Name:')), ['Name: '])
        self.assertEqual(list(dom.completion('Name: foo')), [])
        self.assertEqual(list(dom.completion('Name: !=')), [])
        self.assertEqual(list(dom.completion('Name: !=foo')), [])
        self.assertEqual(list(dom.completion('')), ['Name: '])
        self.assertEqual(list(dom.completion(' ')), ['', 'Name: '])

    def test_completion_many2one(self):
        "Test completion many2one"
        dom = DomainParser({
                'relation': {
                    'name': 'relation',
                    'string': "Relation",
                    'type': 'many2one',
                    'relation_fields': {
                        'name': {
                            'name': 'name',
                            'string': "Name",
                            'type': 'char',
                            },
                        },
                    },
                })
        self.assertEqual(
            list(dom.completion('Relatio')),
            ['Relation: ', 'Relation.Name: '])

    def test_completion_boolean(self):
        "Test completion boolean"
        dom = DomainParser({
                'name': {
                    'string': "Active",
                    'name': 'active',
                    'type': 'boolean',
                    },
                })

        self.assertEqual(list(dom.completion("Act")), ["Active: "])
        self.assertEqual(list(dom.completion("Active:")),
            ["Active: ", "Active: True", "Active: False"])
        self.assertEqual(
            list(dom.completion("Active: t")),
            ["Active: True", "Active: False"])
        self.assertEqual(
            list(dom.completion("Active: f")),
            ["Active: False", "Active: True"])

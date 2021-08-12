# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from shlex import shlex
from types import GeneratorType
import gettext
import locale
import decimal
from decimal import Decimal
import datetime
import io
from collections import OrderedDict

from tryton.common import (
    untimezoned_date, timezoned_date, datetime_strftime, date_format)
from tryton.common.datetime_ import date_parse
from tryton.common.timedelta import parse as timedelta_parse
from tryton.common.timedelta import format as timedelta_format
from tryton.pyson import PYSONDecoder

__all__ = ['DomainParser']

_ = gettext.gettext
ListGeneratorType = type(iter([]))
TupleGeneratorType = type(iter(()))
OPERATORS = (
    '!=',
    '<=',
    '>=',
    '=',
    '!',
    '<',
    '>',
    )


class udlex(shlex):
    "A lexical analyzer class for human domain syntaxes."
    def __init__(self, instream=None):
        shlex.__init__(self, io.StringIO(instream), posix=True)
        self.commenters = ''
        self.quotes = '"'

        class DummyWordchars(object):
            "Simulate str that contains all chars except somes"
            def __contains__(self, item):
                return item not in (':', '>', '<', '=', '!', '"', ';',
                    '(', ')')

        self.wordchars = DummyWordchars()


def isgenerator(value):
    "Test if value is a generator type"
    return isinstance(value, (GeneratorType, ListGeneratorType,
            TupleGeneratorType))


def rlist(value):
    "Convert recursivly generator into list"
    if isgenerator(value) or isinstance(value, list):
        return [rlist(x) for x in value]
    return value


def simplify(value):
    "Remove double nested list"
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], list):
            return simplify(value[0])
        elif (len(value) == 2
                and value[0] in ('AND', 'OR')
                and isinstance(value[1], list)):
            return simplify(value[1])
        elif (len(value) == 3
                and value[0] in ('AND', 'OR')
                and isinstance(value[1], list)
                and value[0] == value[1][0]):
            value = simplify(value[1]) + [value[2]]
        return [simplify(x) for x in value]
    return value


def group_operator(tokens):
    "Group token of operators"
    try:
        cur = next(tokens)
    except StopIteration:
        return
    nex = None
    for nex in tokens:
        if nex == '=' and cur and cur + nex in OPERATORS:
            yield cur + nex
            cur = None
        else:
            if cur is not None:
                yield cur
            cur = nex
    if cur is not None:
        yield cur


def test_group_operator():
    assert list(group_operator(iter(['a', '>', '=']))) == ['a', '>=']
    assert list(group_operator(iter(['>', '=', 'b']))) == ['>=', 'b']
    assert list(group_operator(iter(['a', '=', 'b']))) == ['a', '=', 'b']
    assert list(group_operator(iter(['a', '>', '=', 'b']))) == ['a', '>=', 'b']
    assert list(group_operator(iter(['a', '>', '=', '=']))) == ['a', '>=', '=']


def likify(value, escape='\\'):
    "Add % if needed"
    if not value:
        return '%'
    escaped = value.replace(escape + '%', '').replace(escape + '_', '')
    if '%' in escaped or '_' in escaped:
        return value
    else:
        return '%' + value + '%'


def is_full_text(value, escape='\\'):
    escaped = value.strip('%')
    escaped = escaped.replace(escape + '%', '').replace(escape + '_', '')
    if '%' in escaped or '_' in escaped:
        return False
    return value.startswith('%') and value.endswith('%')


def is_like(value, escape='\\'):
    escaped = value.replace(escape + '%', '').replace(escape + '_', '')
    return '%' in escaped or '_' in escaped


def unescape(value, escape='\\'):
    return value.replace(escape + '%', '%').replace(escape + '_', '_')


def quote(value):
    "Quote string if needed"
    if not isinstance(value, str):
        return value
    if '\\' in value:
        value = value.replace('\\', '\\\\')
    if '"' in value:
        value = value.replace('"', '\\"')
    for test in (':', ' ', '(', ')') + OPERATORS:
        if test in value:
            return '"%s"' % value
    return value


def test_quote():
    assert quote('test') == 'test'
    assert quote('foo bar') == '"foo bar"'
    assert quote('"foo"') == '\\\"foo\\\"'
    assert quote('foo\\bar') == 'foo\\\\bar'


def ending_clause(domain, deep=0):
    "Return the ending clause"
    if not domain:
        return None, deep
    if isinstance(domain[-1], list):
        return ending_clause(domain[-1], deep + 1)
    return domain[-1], deep


def replace_ending_clause(domain, clause):
    "Replace the ending clause"
    for dom in domain[:-1]:
        yield dom
    if isinstance(domain[-1], list):
        yield replace_ending_clause(domain[-1], clause)
    else:
        yield clause


def append_ending_clause(domain, clause, deep):
    "Append clause after the ending clause"
    if not domain:
        yield clause
        return
    for dom in domain[:-1]:
        yield dom
    if isinstance(domain[-1], list):
        yield append_ending_clause(domain[-1], clause, deep - 1)
    else:
        yield domain[-1]
        if deep == 0:
            yield clause


def default_operator(field):
    "Return default operator for field"
    if field['type'] in ('char', 'text', 'many2one', 'many2many', 'one2many',
            'reference'):
        return 'ilike'
    else:
        return '='


def negate_operator(operator):
    "Return negate operator"
    if operator == 'ilike':
        return 'not ilike'
    elif operator == '=':
        return '!='
    elif operator == 'in':
        return 'not in'


def time_format(field):
    return PYSONDecoder({}).decode(field['format'])


def split_target_value(field, value):
    "Split the reference value into target and value"
    assert field['type'] == 'reference'
    target = None
    if isinstance(value, str):
        for key, text in field['selection']:
            if value.lower().startswith(text.lower() + ','):
                target = key
                value = value[len(text) + 1:]
                break
    return target, value


def test_split_target_value():
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
        assert split_target_value(field, value) == result


def convert_value(field, value, context=None):
    "Convert value for field"
    if context is None:
        context = {}

    def convert_boolean():
        if isinstance(value, str):
            return any(test.lower().startswith(value.lower())
                for test in (
                    _('y'), _('Yes'), _('True'), _('t'), '1'))
        else:
            return bool(value)

    def convert_float():
        factor = float(field.get('factor', 1))
        try:
            return locale.atof(value) / factor
        except (ValueError, AttributeError):
            return

    def convert_integer():
        factor = float(field.get('factor', 1))
        try:
            return int(locale.atof(value) / factor)
        except (ValueError, AttributeError):
            return

    def convert_numeric():
        factor = Decimal(field.get('factor', 1))
        try:
            return locale.atof(value, Decimal) / factor
        except (decimal.InvalidOperation, AttributeError):
            return

    def convert_selection():
        if isinstance(value, str):
            for key, text in field['selection']:
                if value.lower() == text.lower():
                    return key
        return value

    def convert_datetime():
        if not value:
            return
        format_ = (
            date_format(context.get('date_format')) + ' ' + time_format(field))
        try:
            dt = date_parse(value, format_)
            return untimezoned_date(dt)
        except ValueError:
            return

    def convert_date():
        if not value:
            return
        format_ = date_format(context.get('date_format'))
        try:
            return date_parse(value, format_).date()
        except (ValueError, TypeError):
            return

    def convert_time():
        if not value:
            return
        try:
            return date_parse(value).time()
        except (ValueError, TypeError):
            return

    def convert_timedelta():
        return timedelta_parse(value, context.get(field.get('converter')))

    def convert_many2one():
        if value == '':
            return None
        return value

    converts = {
        'boolean': convert_boolean,
        'float': convert_float,
        'integer': convert_integer,
        'numeric': convert_numeric,
        'selection': convert_selection,
        'reference': convert_selection,
        'datetime': convert_datetime,
        'date': convert_date,
        'time': convert_time,
        'timedelta': convert_timedelta,
        'many2one': convert_many2one,
        }
    return converts.get(field['type'], lambda: value)()


def test_convert_boolean():
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
            (None, False),
            ):
        assert convert_value(field, value) == result


def test_convert_float():
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
        assert convert_value(field, value) == result


def test_convert_float_factor():
    field = {
        'type': 'float',
        'factor': '100',
        }
    assert convert_value(field, '42') == 0.42


def test_convert_integer():
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
        assert convert_value(field, value) == result


def test_convert_integer_factor():
    field = {
        'type': 'integer',
        'factor': '2',
        }
    assert convert_value(field, '6') == 3


def test_convert_numeric():
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
        assert convert_value(field, value) == result


def test_convert_numeric_factor():
    field = {
        'type': 'numeric',
        'factor': '5',
        }
    assert convert_value(field, '1') == Decimal('0.2')


def test_convert_selection():
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
        assert convert_value(field, value) == result
        assert convert_value(field_with_empty, value) == result


def test_convert_datetime():
    field = {
        'type': 'datetime',
        'format': '"%H:%M:%S"',
        }
    for value, result in (
            ('12/04/2002', untimezoned_date(datetime.datetime(2002, 12, 4))),
            ('12/04/2002 12:30:00', untimezoned_date(
                    datetime.datetime(2002, 12, 4, 12, 30))),
            ('02/03/04', untimezoned_date(datetime.datetime(2004, 2, 3))),
            ('02/03/04 05:06:07', untimezoned_date(
                    datetime.datetime(2004, 2, 3, 5, 6, 7))),
            ('test', None),
            (None, None),
            ):
        assert convert_value(field, value) == result, (value,
            convert_value(field, value), result)


def test_convert_date():
    field = {
        'type': 'date',
        }
    for value, result in (
            ('12/04/2002', datetime.date(2002, 12, 4)),
            ('test', None),
            (None, None),
            ):
        assert convert_value(field, value) == result


def test_convert_time():
    field = {
        'type': 'time',
        'format': '"%H:%M:%S"',
        }
    for value, result in (
            ('12:30:00', datetime.time(12, 30, 0)),
            ('test', None),
            (None, None),
            ):
        assert convert_value(field, value) == result


def test_convert_timedelta():
    field = {
        'type': 'timedelta',
        }
    for value, result in [
            ('1d 2:00', datetime.timedelta(days=1, hours=2)),
            ('foo', datetime.timedelta()),
            (None, None),
            ]:
        assert convert_value(field, value) == result


def format_value(field, value, target=None, context=None):
    "Format value for field"
    if context is None:
        context = {}

    def format_boolean():
        return _('True') if value else _('False')

    def format_integer():
        factor = float(field.get('factor', 1))
        if value or value is 0 or isinstance(value, float):
            return str(int(value * factor))
        return ''

    def format_float():
        if (not value
                and value is not 0
                and not isinstance(value, (float, Decimal))):
            return ''
        digit = 0
        if isinstance(value, Decimal):
            cast = Decimal
        else:
            cast = float
        factor = cast(field.get('factor', 1))
        string_ = str(value * factor)
        if 'e' in string_:
            string_, exp = string_.split('e')
            digit -= int(exp)
        if '.' in string_:
            digit += len(string_.rstrip('0').split('.')[1])
        return locale.localize(
            '{0:.{1}f}'.format(value * factor or 0, digit), True)

    def format_selection():
        if isinstance(field['selection'], (tuple, list)):
            selections = dict(field['selection'])
        else:
            selections = {}
        return selections.get(value, value) or ''

    def format_reference():
        if not target:
            return format_selection()
        selections = dict(field['selection'])
        return '%s,%s' % (selections.get(target, target), value)

    def format_datetime():
        if not value:
            return ''
        if not isinstance(value, datetime.datetime):
            time = datetime.datetime.combine(value, datetime.time.min)
        else:
            time = timezoned_date(value)
        format_ = date_format(context.get('date_format'))
        if time.time() != datetime.time.min:
            format_ += ' ' + time_format(field)
        return datetime_strftime(time, format_)

    def format_date():
        if not value:
            return ''
        format_ = date_format(context.get('date_format'))
        return datetime_strftime(value, format_)

    def format_time():
        if not value:
            return ''
        return datetime.time.strftime(value, time_format(field))

    def format_timedelta():
        if not value:
            return ''
        return timedelta_format(value, context.get(field.get('converter')))

    def format_many2one():
        if value is None:
            return ''
        return value

    converts = {
        'boolean': format_boolean,
        'integer': format_integer,
        'float': format_float,
        'numeric': format_float,
        'selection': format_selection,
        'reference': format_reference,
        'datetime': format_datetime,
        'date': format_date,
        'time': format_time,
        'timedelta': format_timedelta,
        'many2one': format_many2one,
        }
    if isinstance(value, (list, tuple)):
        return ';'.join(format_value(field, x, context=context) for x in value)
    return quote(converts.get(field['type'],
            lambda: value if value is not None else '')())


def test_format_boolean():
    field = {
        'type': 'boolean',
        }
    for value, result in (
            (True, 'True'),
            (False, 'False'),
            (None, 'False'),
            ):
        assert format_value(field, value) == result


def test_format_integer():
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
        assert format_value(field, value) == result


def test_format_integer_factor():
    field = {
        'type': 'integer',
        'factor': '2',
        }
    assert format_value(field, 3) == '6'


def test_format_float():
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
            ):
        assert format_value(field, value) == result


def test_format_float_factor():
    field = {
        'type': 'float',
        'factor': '100',
        }
    assert format_value(field, 0.42) == '42'


def test_format_numeric():
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
        assert format_value(field, value) == result


def test_format_numeric_factor():
    field = {
        'type': 'numeric',
        'factor': '5',
        }
    assert format_value(field, Decimal('0.2')) == '1'


def test_format_selection():
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
        assert format_value(field, value) == result
        assert format_value(field_with_empty, value) == result


def test_format_datetime():
    field = {
        'type': 'datetime',
        'format': '"%H:%M:%S"',
        }
    for value, result in (
            (datetime.date(2002, 12, 4), '12/04/2002'),
            (untimezoned_date(datetime.datetime(2002, 12, 4)), '12/04/2002'),
            (untimezoned_date(datetime.datetime(2002, 12, 4, 12, 30)),
                '"12/04/2002 12:30:00"'),
            (False, ''),
            (None, ''),
            ):
        assert format_value(field, value) == result


def test_format_date():
    field = {
        'type': 'date',
        }
    for value, result in (
            (datetime.date(2002, 12, 4), '12/04/2002'),
            (False, ''),
            (None, ''),
            ):
        assert format_value(field, value) == result


def test_format_time():
    field = {
        'type': 'time',
        'format': '"%H:%M:%S"',
        }
    for value, result in (
            (datetime.time(12, 30, 0), '"12:30:00"'),
            (False, ''),
            (None, ''),
            ):
        assert format_value(field, value) == result


def test_format_timedelta():
    field = {
        'type': 'timedelta',
        }
    for value, result in [
            (datetime.timedelta(days=1, hours=2), '"1d 02:00"'),
            (datetime.timedelta(), ''),
            (None, ''),
            ('', ''),
            ]:
        assert format_value(field, value) == result


def complete_value(field, value):
    "Complete value for field"

    def complete_boolean():
        if value:
            yield False
        else:
            yield True

    def complete_selection():
        test_value = value if value is not None else ''
        if isinstance(value, list):
            test_value = value[-1] or ''
        test_value = test_value.strip('%')
        for svalue, test in field['selection']:
            if test.lower().startswith(test_value.lower()):
                if isinstance(value, list):
                    yield value[:-1] + [svalue]
                else:
                    yield svalue

    def complete_reference():
        test_value = value if value is not None else ''
        if isinstance(value, list):
            test_value = value[-1]
        test_value = test_value.strip('%')
        for svalue, test in field['selection']:
            if test.lower().startswith(test_value.lower()):
                if isinstance(value, list):
                    yield value[:-1] + [svalue]
                else:
                    yield likify(svalue)

    def complete_datetime():
        yield datetime.date.today()
        yield datetime.datetime.utcnow()

    def complete_date():
        yield datetime.date.today()

    def complete_time():
        yield datetime.datetime.now().time()

    completes = {
        'boolean': complete_boolean,
        'selection': complete_selection,
        'reference': complete_reference,
        'datetime': complete_datetime,
        'date': complete_date,
        'time': complete_time,
        }
    return completes.get(field['type'], lambda: [])()


def test_complete_selection():
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
        assert list(complete_value(field, value)) == result

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
        assert list(complete_value(field_with_empty, value)) == result


def test_complete_reference():
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
        assert list(complete_value(field, value)) == result


def parenthesize(tokens):
    "Nest tokens according to parenthesis"
    for token in tokens:
        if token == '(':
            yield iter(list(parenthesize(tokens)))
        elif token == ')':
            break
        else:
            yield token


def test_parenthesize():
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
        assert rlist(parenthesize(iter(value))) == result


def operatorize(tokens, operator='or'):
    "Convert operators"
    test = (operator, (operator,))
    try:
        cur = next(tokens)
        while cur in test:
            cur = next(tokens)
    except StopIteration:
        return
    if isgenerator(cur):
        cur = operatorize(cur, operator)
    nex = None
    for nex in tokens:
        if isgenerator(nex):
            nex = operatorize(nex, operator)
        if nex in test:
            try:
                nex = next(tokens)
                while nex in test:
                    nex = next(tokens)
                if isgenerator(nex):
                    nex = operatorize(nex, operator)
                cur = iter([operator.upper(), cur, nex])
            except StopIteration:
                if cur not in test:
                    yield iter([operator.upper(), cur])
                    cur = None
            nex = None
        else:
            if cur not in test:
                yield cur
            cur = nex
    else:
        if nex is not None and nex not in test:
            yield nex
        elif cur is not None and cur not in test:
            yield cur


def test_operatorize():
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
        assert rlist(operatorize(iter(value))) == result


class DomainParser(object):
    "A parser for domain"

    def __init__(self, fields, context=None):
        self.fields = OrderedDict((name, f)
            for name, f in fields.items()
            if f.get('searchable', True))
        self.strings = dict((f['string'].lower(), f)
            for f in fields.values()
            if f.get('searchable', True))
        self.context = context

    def parse(self, input_):
        "Return domain for the input string"
        try:
            tokens = udlex(input_)
            tokens = group_operator(tokens)
            tokens = parenthesize(tokens)
            tokens = self.group(tokens)
            tokens = operatorize(tokens, 'or')
            tokens = operatorize(tokens, 'and')
            tokens = self.parse_clause(tokens)
            return simplify(rlist(tokens))
        except ValueError as exception:
            if str(exception) == 'No closing quotation':
                return self.parse(input_ + '"')

    def stringable(self, domain):

        def stringable_(clause):
            if not clause:
                return True
            if (((clause[0] in ('AND', 'OR'))
                        or isinstance(clause[0], (list, tuple)))
                    and all(isinstance(c, (list, tuple)) for c in clause[1:])):
                return self.stringable(clause)
            name, _, value = clause[:3]
            if name.endswith('.rec_name'):
                name = name[:-len('.rec_name')]
            if name in self.fields:
                field = self.fields[name]
                if field['type'] in {
                        'many2one', 'one2one', 'one2many', 'many2many'}:
                    if field['type'] == 'many2one':
                        types = (str, type(None))
                    else:
                        types = str
                    if isinstance(value, (list, tuple)):
                        return all(isinstance(v, types) for v in value)
                    else:
                        return isinstance(value, types)
                else:
                    return True
            elif name == 'rec_name':
                return True
            return False

        if not domain:
            return True
        if domain[0] in ('AND', 'OR'):
            domain = domain[1:]
        return all(stringable_(clause) for clause in domain)

    def string(self, domain):
        "Return string for the domain"

        def string_(clause):
            if not clause:
                return ''
            if (not isinstance(clause[0], str)
                    or clause[0] in ('AND', 'OR')):
                return '(%s)' % self.string(clause)
            name, operator, value = clause[:3]
            if name.endswith('.rec_name'):
                name = name[:-9]
            if name not in self.fields:
                if is_full_text(value):
                    value = value[1:-1]
                return quote(value)
            field = self.fields[name]

            if len(clause) > 3:
                target = clause[3]
            else:
                target = None

            if 'ilike' in operator:
                if is_full_text(value):
                    value = value[1:-1]
                elif not is_like(value):
                    if operator == 'ilike':
                        operator = '='
                    else:
                        operator = '!'
                    value = unescape(value)
            def_operator = default_operator(field)
            if def_operator == operator.strip():
                operator = ''
                if value in OPERATORS:
                    # As the value could be interpreted as an operator,
                    # the default operator must be forced
                    operator = '"" '
            elif (def_operator in operator
                    and ('not' in operator or '!' in operator)):
                operator = operator.rstrip(def_operator
                    ).replace('not', '!').strip()
            if operator.endswith('in'):
                if operator == 'not in':
                    operator = '!'
                else:
                    operator = ''
            formatted_value = format_value(field, value, target, self.context)
            if (operator in OPERATORS and
                    field['type'] in ('char', 'text', 'selection')
                    and value == ''):
                formatted_value = '""'
            return '%s: %s%s' % (quote(field['string']), operator,
                formatted_value)

        if not domain:
            return ''
        if domain[0] in ('AND', 'OR'):
            nary = ' ' if domain[0] == 'AND' else ' or '
            domain = domain[1:]
        else:
            nary = ' '
        return nary.join(string_(clause) for clause in domain)

    def completion(self, input_):
        "Return completion for the input string"
        domain = self.parse(input_)
        closing = 0
        for i in range(1, len(input_)):
            if input_[-i] not in (')', ' '):
                break
            if input_[-i] == ')':
                closing += 1
        ending, deep_ending = ending_clause(domain)
        deep = deep_ending - closing
        if deep:
            pslice = slice(-deep)
        else:
            pslice = slice(None)
        if self.string(domain)[pslice] != input_:
            yield self.string(domain)[pslice]
        complete = None
        if ending is not None and closing == 0:
            for complete in self.complete(ending):
                yield self.string(rlist(
                        replace_ending_clause(domain, complete)))[pslice]
        if input_:
            if input_[-1] != ' ':
                return
            if len(input_) >= 2 and input_[-2] == ':':
                return
        for field in self.strings.values():
            operator = default_operator(field)
            value = ''
            if 'ilike' in operator:
                value = likify(value)
            yield self.string(rlist(append_ending_clause(domain,
                        (field['name'], operator, value),
                        deep)))[pslice]

    def complete(self, clause):
        "Return all completion for the clause"
        if len(clause) == 1:
            name, = clause
        elif len(clause) == 3:
            name, operator, value = clause
        else:
            name, operator, value, target = clause
            if name.endswith('.rec_name'):
                name = name[:-9]
            value = target
        if name == 'rec_name':
            if operator == 'ilike':
                escaped = value.replace('%%', '__')
                if escaped.startswith('%') and escaped.endswith('%'):
                    value = value[1:-1]
                elif '%' not in escaped:
                    value = value.replace('%%', '%')
                operator = None
            name = value
            value = ''
        if not name:
            name = ''
        if (name.lower() not in self.strings
                and name not in self.fields):
            for field in self.strings.values():
                if field['string'].lower().startswith(name.lower()):
                    operator = default_operator(field)
                    value = ''
                    if 'ilike' in operator:
                        value = likify(value)
                    yield (field['name'], operator, value)
            return
        if name in self.fields:
            field = self.fields[name]
        else:
            field = self.strings[name.lower()]
        if not operator:
            operator = default_operator(field)
            value = ''
            if 'ilike' in operator:
                value = likify(value)
            yield (field['name'], operator, value)
        else:
            for comp in complete_value(field, value):
                yield (field['name'], operator, comp)

    def group(self, tokens):
        "Group tokens by clause"

        def _group(parts):
            try:
                i = parts.index(':')
            except ValueError:
                for part in parts:
                    yield (part,)
                return
            for j in range(i):
                name = ' '.join(parts[j:i])
                if name.lower() in self.strings:
                    if parts[:j]:
                        for part in parts[:j]:
                            yield (part,)
                    else:
                        yield (None,)
                    name = (name,)
                    # empty string is also the default operator
                    if (i + 1 < len(parts)
                            and parts[i + 1] in OPERATORS + ('',)):
                        name += (parts[i + 1],)
                        i += 1
                    else:
                        name += (None,)
                    lvalue = []
                    while i + 2 < len(parts):
                        if parts[i + 2] == ';':
                            lvalue.append(parts[i + 1])
                            i += 2
                        else:
                            break
                    for part in _group(parts[i + 1:]):
                        if name:
                            if lvalue:
                                if part[0] is not None:
                                    lvalue.append(part[0])
                                yield name + (lvalue,)
                            else:
                                yield name + part
                            name = None
                        else:
                            yield part
                    if name:
                        if lvalue:
                            yield name + (lvalue,)
                        else:
                            yield name + (None,)
                    break

        parts = []
        for token in tokens:
            if isgenerator(token):
                for group in _group(parts):
                    if group != (None,):
                        yield group
                parts = []
                yield self.group(token)
            else:
                parts.append(token)
        for group in _group(parts):
            if group != (None,):
                yield group

    def parse_clause(self, tokens):
        "Parse clause"
        for clause in tokens:
            if isgenerator(clause):
                yield self.parse_clause(clause)
            elif clause in ('OR', 'AND'):
                yield clause
            else:
                if len(clause) == 1:
                    yield ('rec_name', 'ilike', likify(clause[0]))
                else:
                    name, operator, value = clause
                    field = self.strings[name.lower()]
                    field_name = field['name']

                    target = None
                    if field['type'] == 'reference':
                        target, value = split_target_value(field, value)
                        if target:
                            field_name += '.rec_name'

                    if not operator:
                        operator = default_operator(field)
                    if isinstance(value, list):
                        if operator == '!':
                            operator = 'not in'
                        else:
                            operator = 'in'
                    if operator == '!':
                        operator = negate_operator(default_operator(field))
                    if field['type'] in ('integer', 'float', 'numeric',
                            'datetime', 'date', 'time'):
                        if isinstance(value, str) and '..' in value:
                            lvalue, rvalue = value.split('..', 1)
                            lvalue = convert_value(field, lvalue, self.context)
                            rvalue = convert_value(field, rvalue, self.context)
                            yield iter([
                                    (field_name, '>=', lvalue),
                                    (field_name, '<=', rvalue),
                                    ])
                            continue
                    if isinstance(value, list):
                        value = [convert_value(field, v, self.context)
                            for v in value]
                        if field['type'] in ('many2one', 'one2many',
                                'many2many', 'one2one'):
                            field_name += '.rec_name'
                    else:
                        value = convert_value(field, value, self.context)
                    if 'like' in operator:
                        value = likify(value)
                    if target:
                        yield (field_name, operator, value, target)
                    else:
                        yield field_name, operator, value


def test_stringable():
    dom = DomainParser({
            'name': {
                'string': 'Name',
                'type': 'char',
                },
            'relation': {
                'string': 'Relation',
                'type': 'many2one',
                },
            'relations': {
                'string': 'Relations',
                'type': 'many2many',
                },
            })
    valid = ('name', '=', 'Doe')
    invalid = ('surname', '=', 'John')
    assert dom.stringable([valid])
    assert not dom.stringable([invalid])
    assert dom.stringable(['AND', valid])
    assert not dom.stringable(['AND', valid, invalid])
    assert dom.stringable([[valid]])
    assert not dom.stringable([[valid], [invalid]])
    assert dom.stringable([('relation', '=', None)])
    assert dom.stringable([('relation', '=', "Foo")])
    assert dom.stringable([('relation.rec_name', '=', "Foo")])
    assert not dom.stringable([('relation', '=', 1)])
    assert dom.stringable([('relations', '=', "Foo")])
    assert dom.stringable([('relations', 'in', ["Foo"])])
    assert not dom.stringable([('relations', 'in', [42])])


def test_string():
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
                },
            })
    assert dom.string([('name', '=', 'Doe')]) == 'Name: =Doe'
    assert dom.string([('name', '=', None)]) == 'Name: ='
    assert dom.string([('name', '=', '')]) == 'Name: =""'
    assert dom.string([('name', 'ilike', '%')]) == 'Name: '
    assert dom.string([('name', 'ilike', '%Doe%')]) == 'Name: Doe'
    assert dom.string([('name', 'ilike', '%<%')]) == 'Name: "" "<"'
    assert dom.string([('name', 'ilike', 'Doe')]) == 'Name: =Doe'
    assert dom.string([('name', 'ilike', 'Doe%')]) == 'Name: Doe%'
    assert dom.string([('name', 'ilike', 'Doe\\%')]) == 'Name: =Doe%'
    assert dom.string([('name', 'not ilike', '%Doe%')]) == 'Name: !Doe'
    assert dom.string([('name', 'in', ['John', 'Jane'])]) == 'Name: John;Jane'
    assert dom.string([('name', 'not in', ['John', 'Jane'])]) == \
        'Name: !John;Jane'
    assert dom.string([
            ('name', 'ilike', '%Doe%'),
            ('name', 'ilike', '%Jane%')]) == 'Name: Doe Name: Jane'
    assert dom.string(['AND',
            ('name', 'ilike', '%Doe%'),
            ('name', 'ilike', '%Jane%')]) == 'Name: Doe Name: Jane'
    assert dom.string(['OR',
            ('name', 'ilike', '%Doe%'),
            ('name', 'ilike', '%Jane%')]) == 'Name: Doe or Name: Jane'
    assert dom.string([
            ('name', 'ilike', '%Doe%'),
            ['OR',
                ('name', 'ilike', '%John%'),
                ('name', 'ilike', '%Jane%')]]) == \
        'Name: Doe (Name: John or Name: Jane)'
    assert dom.string([]) == ''
    assert dom.string([('surname', 'ilike', '%Doe%')]) == '"(Sur)Name": Doe'
    assert dom.string([('date', '>=', datetime.date(2012, 10, 24))]) == \
        'Date: >=10/24/2012'
    assert dom.string([('selection', '=', '')]) == 'Selection: '
    assert dom.string([('selection', '=', None)]) == 'Selection: '
    assert dom.string([('selection', '!=', '')]) == 'Selection: !""'
    assert dom.string([('selection', '=', 'male')]) == 'Selection: Male'
    assert dom.string([('selection', '!=', 'male')]) == 'Selection: !Male'
    assert dom.string([('reference', 'ilike', '%foo%')]) == \
        'Reference: foo'
    assert dom.string([('reference.rec_name', 'ilike', '%bar%', 'spam')]) == \
        'Reference: Spam,bar'
    assert dom.string([('reference', 'in', ['foo', 'bar'])]) == \
        'Reference: foo;bar'
    assert dom.string([('many2one', 'ilike', '%John%')]) == 'Many2One: John'
    assert dom.string([('many2one.rec_name', 'in', ['John', 'Jane'])]) == \
        'Many2One: John;Jane'


def test_group():
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
            })
    assert rlist(dom.group(udlex('Name: Doe'))) == [('Name', None, 'Doe')]
    assert rlist(dom.group(udlex('"(Sur)Name": Doe'))) == [
        ('(Sur)Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex('Name: Doe Name: John'))) == [
        ('Name', None, 'Doe'),
        ('Name', None, 'John')]
    assert rlist(dom.group(udlex('Name: Name: John'))) == [
        ('Name', None, None),
        ('Name', None, 'John')]
    assert rlist(dom.group(udlex('First Name: John'))) == [
        ('First Name', None, 'John'),
        ]
    assert rlist(dom.group(udlex('Name: Doe First Name: John'))) == [
        ('Name', None, 'Doe'),
        ('First Name', None, 'John'),
        ]
    assert rlist(dom.group(udlex('First Name: John Name: Doe'))) == [
        ('First Name', None, 'John'),
        ('Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex('First Name: John First Name: Jane'))) == [
        ('First Name', None, 'John'),
        ('First Name', None, 'Jane'),
        ]
    assert rlist(dom.group(udlex('Name: John Doe'))) == [
        ('Name', None, 'John'),
        ('Doe',),
        ]
    assert rlist(dom.group(udlex('Name: "John Doe"'))) == [
        ('Name', None, 'John Doe'),
        ]
    assert rlist(dom.group(udlex('Name: =Doe'))) == [('Name', '=', 'Doe')]
    assert rlist(dom.group(udlex('Name: =Doe Name: >John'))) == [
        ('Name', '=', 'Doe'),
        ('Name', '>', 'John'),
        ]
    assert rlist(dom.group(udlex('First Name: =John First Name: =Jane'))) == [
        ('First Name', '=', 'John'),
        ('First Name', '=', 'Jane'),
        ]
    assert rlist(dom.group(udlex('Name: John;Jane'))) == [
        ('Name', None, ['John', 'Jane'])
        ]
    assert rlist(dom.group(udlex('Name: John;'))) == [
        ('Name', None, ['John'])
        ]
    assert rlist(dom.group(udlex('Name: John;Jane Name: Doe'))) == [
        ('Name', None, ['John', 'Jane']),
        ('Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex('Name: John; Name: Doe'))) == [
        ('Name', None, ['John']),
        ('Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex('Name:'))) == [
        ('Name', None, None),
        ]
    assert rlist(dom.group(udlex('Name: ='))) == [
        ('Name', '=', None),
        ]
    assert rlist(dom.group(udlex('Name: =""'))) == [
        ('Name', '=', ''),
        ]
    assert rlist(dom.group(udlex('Name: = ""'))) == [
        ('Name', '=', ''),
        ]
    assert rlist(dom.group(udlex('Name: = Name: Doe'))) == [
        ('Name', '=', None),
        ('Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex('Name: \\"foo\\"'))) == [
        ('Name', None, '"foo"'),
        ]
    assert rlist(dom.group(udlex('Name: "" <'))) == [
        ('Name', '', '<'),
        ]


def test_parse_clause():
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
            })
    assert rlist(dom.parse_clause([('John',)])) == [
        ('rec_name', 'ilike', '%John%')]
    assert rlist(dom.parse_clause([('Name', None, None)])) == [
        ('name', 'ilike', '%')]
    assert rlist(dom.parse_clause([('Name', '', None)])) == [
        ('name', 'ilike', '%')]
    assert rlist(dom.parse_clause([('Name', '=', None)])) == [
        ('name', '=', None)]
    assert rlist(dom.parse_clause([('Name', '=', '')])) == [
        ('name', '=', '')]
    assert rlist(dom.parse_clause([('Name', None, 'Doe')])) == [
        ('name', 'ilike', '%Doe%')]
    assert rlist(dom.parse_clause([('Name', '!', 'Doe')])) == [
        ('name', 'not ilike', '%Doe%')]
    assert rlist(dom.parse_clause([('Name', None, ['John', 'Jane'])])) == [
        ('name', 'in', ['John', 'Jane']),
        ]
    assert rlist(dom.parse_clause([('Name', '!', ['John', 'Jane'])])) == [
        ('name', 'not in', ['John', 'Jane']),
        ]
    assert rlist(dom.parse_clause([('Selection', None, None)])) == [
        ('selection', '=', None),
        ]
    assert rlist(dom.parse_clause([('Selection', None, '')])) == [
        ('selection', '=', ''),
        ]
    assert rlist(dom.parse_clause([('Selection', None, ['Male', 'Female'])])) \
        == [
            ('selection', 'in', ['male', 'female'])
            ]
    assert rlist(dom.parse_clause([('Integer', None, None)])) == [
        ('integer', '=', None),
        ]
    assert rlist(dom.parse_clause([('Integer', None, '3..5')])) == [[
            ('integer', '>=', 3),
            ('integer', '<=', 5),
            ]]
    assert rlist(dom.parse_clause([('Reference', None, 'foo')])) == [
        ('reference', 'ilike', '%foo%'),
        ]
    assert rlist(dom.parse_clause([('Reference', None, 'Spam')])) == [
        ('reference', 'ilike', '%spam%'),
        ]
    assert rlist(dom.parse_clause([('Reference', None, 'Spam,bar')])) == [
        ('reference.rec_name', 'ilike', '%bar%', 'spam'),
        ]
    assert rlist(dom.parse_clause([('Reference', None, ['foo', 'bar'])])) == [
        ('reference', 'in', ['foo', 'bar']),
        ]
    assert rlist(dom.parse_clause(['OR',
                ('Name', None, 'John'), ('Name', None, 'Jane')])) == ['OR',
        ('name', 'ilike', '%John%'),
        ('name', 'ilike', '%Jane%'),
        ]
    assert rlist(dom.parse_clause([('Many2One', None, 'John')])) == [
        ('many2one', 'ilike', '%John%'),
        ]
    assert rlist(dom.parse_clause([('Many2One', None, ['John', 'Jane'])])) == [
        ('many2one.rec_name', 'in', ['John', 'Jane']),
        ]
    assert rlist(dom.parse_clause(iter([iter([['John']])]))) == [
        [('rec_name', 'ilike', '%John%')]]


def test_completion():
    dom = DomainParser({
            'name': {
                'string': 'Name',
                'name': 'name',
                'type': 'char',
                },
            })
    assert list(dom.completion('Nam')) == ['Name: ']
    assert list(dom.completion('Name:')) == ['Name: ']
    assert list(dom.completion('Name: foo')) == []
    assert list(dom.completion('Name: !=')) == []
    assert list(dom.completion('Name: !=foo')) == []
    assert list(dom.completion('')) == ['Name: ']
    assert list(dom.completion(' ')) == ['', 'Name: ']


if __name__ == '__main__':
    for name in list(globals()):
        if name.startswith('test_'):
            func = globals()[name]
            func()

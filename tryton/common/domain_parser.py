#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from shlex import shlex
from types import GeneratorType
import gettext
import locale
import decimal
from decimal import Decimal
import datetime
import time
import io

from tryton.translate import date_format
from tryton.common import HM_FORMAT, untimezoned_date, datetime_strftime

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
                return item not in (u':', u'>', u'<', u'=', u'!', u'"', u';',
                    u'(', u')')

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
    cur = next(tokens)
    nex = None
    for nex in tokens:
        if nex == '=' and cur and cur + nex in OPERATORS:
            yield cur + nex
            cur = None
        else:
            if cur:
                yield cur
            cur = nex
    if cur:
        yield cur


def test_group_operator():
    assert list(group_operator(iter(['a', '>', '=']))) == ['a', '>=']
    assert list(group_operator(iter(['>', '=', 'b']))) == ['>=', 'b']
    assert list(group_operator(iter(['a', '=', 'b']))) == ['a', '=', 'b']
    assert list(group_operator(iter(['a', '>', '=', 'b']))) == ['a', '>=', 'b']
    assert list(group_operator(iter(['a', '>', '=', '=']))) == ['a', '>=', '=']


def likify(value):
    "Add % if needed"
    if not value:
        return '%'
    escaped = value.replace('%%', '__')
    if '%' in escaped:
        return value
    else:
        return '%' + value + '%'


def quote(value):
    "Quote string if needed"
    if not isinstance(value, basestring):
        return value
    for test in (':', ' ', '(', ')') + OPERATORS:
        if test in value:
            return '"%s"' % value
    return value


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
        raise StopIteration
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
    if field['type'] in ('char', 'text', 'many2one'):
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


def convert_value(field, value):
    "Convert value for field"

    def convert_boolean():
        if isinstance(value, basestring):
            return any(test.lower().startswith(value.lower())
                for test in (_('y'), _('yes'), _('true'), _('t'), '1'))
        else:
            return bool(value)

    def convert_float():
        try:
            return locale.atof(value)
        except (ValueError, AttributeError):
            return

    def convert_integer():
        try:
            return int(locale.atof(value))
        except (ValueError, AttributeError):
            return

    def convert_numeric():
        try:
            return locale.atof(value, Decimal)
        except (decimal.InvalidOperation, AttributeError):
            return

    def convert_selection():
        if isinstance(value, basestring):
            for key, text in field['selection']:
                if value.lower() == text.lower():
                    return key
        return value

    def convert_datetime():
        try:
            return untimezoned_date(datetime.datetime(*time.strptime(value,
                        date_format() + ' ' + HM_FORMAT)[:6]))
        except ValueError:
            try:
                return untimezoned_date(datetime.datetime(*time.strptime(value,
                            date_format())[:6]))
            except ValueError:
                return
        except TypeError:
            return

    def convert_date():
        try:
            return datetime.date(*time.strptime(value, date_format())[:3])
        except (ValueError, TypeError):
            return

    def convert_time():
        try:
            return datetime.time(*time.strptime(value, HM_FORMAT)[3:6])
        except (ValueError, TypeError):
            return

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


def test_convert_selection():
    field = {
        'type': 'selection',
        'selection': [
            ('male', 'Male'),
            ('female', 'Female'),
            ],
        }
    for value, result in (
            ('Male', 'male'),
            ('male', 'male'),
            ('test', 'test'),
            (None, None),
            ):
        assert convert_value(field, value) == result


def test_convert_datetime():
    field = {
        'type': 'datetime',
        }
    for value, result in (
            ('12/04/2002', datetime.datetime(2002, 12, 4)),
            ('12/04/2002 12:30:00', datetime.datetime(2002, 12, 4, 12, 30)),
            ('test', None),
            (None, None),
            ):
        assert convert_value(field, value) == result


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
        }
    for value, result in (
            ('12:30:00', datetime.time(12, 30, 0)),
            ('test', None),
            (None, None),
            ):
        assert convert_value(field, value) == result


def format_value(field, value):
    "Format value for field"

    def format_boolean():
        return _('True') if value else _('False')

    def format_integer():
        if value or value is 0 or isinstance(value, float):
            return str(int(value))
        return ''

    def format_float():
        if (not value
                and value is not 0
                and not isinstance(value, (float, Decimal))):
            return ''
        try:
            digit = int(field.get('digits', (16, 2))[1])
        except ValueError:
            digit = 2
        return locale.format('%.' + str(digit) + 'f', value or 0.0, True)

    def format_selection():
        selections = dict(field['selection'])
        return selections.get(value, value) or ''

    def format_datetime():
        if not value:
            return ''
        format_ = date_format() + ' ' + HM_FORMAT
        if (not isinstance(value, datetime.datetime)
                or value.time() == datetime.time.min):
            format_ = date_format()
        return datetime_strftime(value, format_)

    def format_time():
        if not value:
            return ''
        return datetime.time.strftime(value, HM_FORMAT)

    converts = {
        'boolean': format_boolean,
        'integer': format_integer,
        'float': format_float,
        'numeric': format_float,
        'selection': format_selection,
        'reference': format_selection,
        'datetime': format_datetime,
        'date': format_datetime,
        'time': format_time,
        }
    if isinstance(value, (list, tuple)):
        return ';'.join(format_value(field, x) for x in value)
    return quote(converts.get(field['type'], lambda: value)())


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


def test_format_float():
    field = {
        'type': 'float',
        'digits': (16, 2),
        }
    for value, result in (
            (1, '1.00'),
            (1.5, '1.50'),
            (0, '0.00'),
            (0.0, '0.00'),
            (False, ''),
            (None, ''),
            ):
        assert format_value(field, value) == result


def test_format_numeric():
    field = {
        'type': 'numeric',
        'digits': (16, 2),
        }
    for value, result in (
            (Decimal(1), '1.00'),
            (Decimal('1.5'), '1.50'),
            (Decimal(0), '0.00'),
            (Decimal('0.0'), '0.00'),
            (False, ''),
            (None, ''),
            ):
        assert format_value(field, value) == result


def test_format_selection():
    field = {
        'type': 'selection',
        'selection': [
            ('male', 'Male'),
            ('female', 'Female'),
            ],
        }
    for value, result in (
            ('male', 'Male'),
            ('test', 'test'),
            (False, ''),
            (None, ''),
            ):
        assert format_value(field, value) == result


def test_format_datetime():
    field = {
        'type': 'datetime',
        }
    for value, result in (
            (datetime.date(2002, 12, 4), '12/04/2002'),
            (datetime.datetime(2002, 12, 4), '12/04/2002'),
            (datetime.datetime(2002, 12, 4, 12, 30), '"12/04/2002 12:30:00"'),
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
        }
    for value, result in (
            (datetime.time(12, 30, 0), '"12:30:00"'),
            (False, ''),
            (None, ''),
            ):
        assert format_value(field, value) == result


def complete_value(field, value):
    "Complete value for field"

    def complete_boolean():
        if value:
            yield False
        else:
            yield True

    def complete_selection():
        for svalue, test in field['selection']:
            if test.lower().startswith(value.lower()):
                yield svalue

    def complete_datetime():
        yield datetime.date.today()
        yield datetime.datetime.now()

    def complete_date():
        yield datetime.date.today()

    def complete_time():
        yield datetime.time()

    completes = {
        'boolean': complete_boolean,
        'selection': complete_selection,
        'reference': complete_selection,
        'datetime': complete_datetime,
        'date': complete_date,
        'time': complete_time,
        }
    return completes.get(field['type'], lambda: [])()


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
    cur = next(tokens)
    while cur in test:
        cur = next(tokens)
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
            (['a', iter(['b', 'c']),  'or', 'd'],
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
            ):
        assert rlist(operatorize(iter(value))) == result


class DomainParser(object):
    "A parser for domain"

    def __init__(self, fields):
        self.fields = dict((name, f)
            for name, f in fields.iteritems()
            if f.get('searchable', True))
        self.strings = dict((f['string'].lower(), f)
            for f in fields.itervalues()
            if f.get('searchable', True))

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
        except ValueError, exception:
            if exception.message == 'No closing quotation':
                return self.parse(input_ + '"')

    def string(self, domain):
        "Return string for the domain"

        def string_(clause):
            if not clause:
                return ''
            if (isinstance(clause[0], basestring)
                    and (clause[0] in self.fields
                    or clause[0] == 'rec_name')):
                name, operator, value = clause
                if name not in self.fields:
                    escaped = value.replace('%%', '__')
                    if escaped.startswith('%') and escaped.endswith('%'):
                        value = value[1:-1]
                    return quote(value)
                field = self.fields[name]
                if 'ilike' in operator:
                    escaped = value.replace('%%', '__')
                    if escaped.startswith('%') and escaped.endswith('%'):
                        value = value[1:-1]
                    elif '%' not in escaped:
                        if operator == 'ilike':
                            operator = '='
                        else:
                            operator = '!'
                        value = value.replace('%%', '%')
                def_operator = default_operator(field)
                if (def_operator == operator.strip()
                        or (def_operator in operator
                            and 'not' in operator)):
                    operator = operator.rstrip(def_operator
                        ).replace('not', '!').strip()
                if operator.endswith('in'):
                    if operator == 'not in':
                        operator = '!'
                    else:
                        operator = ''
                return '%s: %s%s' % (quote(field['string']), operator,
                    format_value(field, value))
            else:
                return '(%s)' % self.string(clause)

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
        for i in xrange(1, len(input_)):
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
        for field in self.strings.itervalues():
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
        else:
            name, operator, value = clause
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
        if (name.lower() not in self.strings
                and name not in self.fields):
            for field in self.strings.itervalues():
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
        if operator is None:
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
                raise StopIteration
            for j in range(i):
                name = ' '.join(parts[j:i])
                if name.lower() in self.strings:
                    if parts[:j]:
                        for part in parts[:j]:
                            yield (part,)
                    else:
                        yield (None,)
                    name = (name,)
                    if i + 1 < len(parts) and parts[i + 1] in OPERATORS:
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
                            yield name + ('',)
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
                    if operator is None:
                        operator = default_operator(field)
                    if isinstance(value, list):
                        if operator == '!':
                            operator = 'not in'
                        else:
                            operator = 'in'
                    if operator == '!':
                        operator = negate_operator(default_operator(field))
                    if 'like' in operator:
                        value = likify(value)
                    if field['type'] in ('integer', 'float', 'numeric'):
                        if '..' in value:
                            lvalue, rvalue = value.split('..', 1)
                            lvalue = convert_value(field, lvalue)
                            rvalue = convert_value(field, rvalue)
                            yield iter([
                                    (field['name'], '>=', lvalue),
                                    (field['name'], '<', rvalue),
                                    ])
                            continue
                    value = convert_value(field, value)
                    yield field['name'], operator, value


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
            })
    assert dom.string([('name', '=', 'Doe')]) == 'Name: =Doe'
    assert dom.string([('name', 'ilike', '%Doe%')]) == 'Name: Doe'
    assert dom.string([('name', 'ilike', 'Doe')]) == 'Name: =Doe'
    assert dom.string([('name', 'ilike', 'Doe%')]) == 'Name: Doe%'
    assert dom.string([('name', 'ilike', 'Doe%%')]) == 'Name: =Doe%'
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
    assert rlist(dom.group(udlex(u'Name: Doe'))) == [('Name', None, 'Doe')]
    assert rlist(dom.group(udlex(u'"(Sur)Name": Doe'))) == [
        ('(Sur)Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex(u'Name: Doe Name: John'))) == [
        ('Name', None, 'Doe'),
        ('Name', None, 'John')]
    assert rlist(dom.group(udlex(u'Name: Name: John'))) == [
        ('Name', None, None),
        ('Name', None, 'John')]
    assert rlist(dom.group(udlex(u'First Name: John'))) == [
        ('First Name', None, 'John'),
        ]
    assert rlist(dom.group(udlex(u'Name: Doe First Name: John'))) == [
        ('Name', None, 'Doe'),
        ('First Name', None, 'John'),
        ]
    assert rlist(dom.group(udlex(u'First Name: John Name: Doe'))) == [
        ('First Name', None, 'John'),
        ('Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex(u'First Name: John First Name: Jane'))) == [
        ('First Name', None, 'John'),
        ('First Name', None, 'Jane'),
        ]
    assert rlist(dom.group(udlex(u'Name: John Doe'))) == [
        ('Name', None, 'John'),
        ('Doe',),
        ]
    assert rlist(dom.group(udlex(u'Name: "John Doe"'))) == [
        ('Name', None, 'John Doe'),
        ]
    assert rlist(dom.group(udlex(u'Name: =Doe'))) == [('Name', '=', 'Doe')]
    assert rlist(dom.group(udlex(u'Name: =Doe Name: >John'))) == [
        ('Name', '=', 'Doe'),
        ('Name', '>', 'John'),
        ]
    assert rlist(dom.group(udlex(u'First Name: =John First Name: =Jane'))) == [
        ('First Name', '=', 'John'),
        ('First Name', '=', 'Jane'),
        ]
    assert rlist(dom.group(udlex(u'Name: John;Jane'))) == [
        ('Name', None, ['John', 'Jane'])
        ]
    assert rlist(dom.group(udlex(u'Name: John;'))) == [
        ('Name', None, ['John'])
        ]
    assert rlist(dom.group(udlex(u'Name: John;Jane Name: Doe'))) == [
        ('Name', None, ['John', 'Jane']),
        ('Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex(u'Name: John; Name: Doe'))) == [
        ('Name', None, ['John']),
        ('Name', None, 'Doe'),
        ]
    assert rlist(dom.group(udlex(u'Name:'))) == [
        ('Name', None, ''),
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
            })
    assert rlist(dom.parse_clause([('John',)])) == [
        ('rec_name', 'ilike', '%John%')]
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
    assert rlist(dom.parse_clause([('Integer', None, '3..5')])) == [[
            ('integer', '>=', 3),
            ('integer', '<', 5),
            ]]

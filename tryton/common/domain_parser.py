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

from tryton.common import untimezoned_date, timezoned_date, date_format
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


def likify(value, escape='\\'):
    "Add % if needed"
    if not value:
        return '%'
    escaped = value.replace(escape + '%', '').replace(escape + '_', '')
    if '%' in escaped or '_' in escaped:
        return value
    else:
        return '%' + value + '%'


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
    elif field['type'] == 'multiselection':
        return 'in'
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


def convert_value(field, value, context=None):
    "Convert value for field"
    if context is None:
        context = {}

    def convert_boolean():
        if isinstance(value, str):
            return any(test.lower().startswith(value.lower())
                for test in (
                    _('y'), _('Yes'), _('True'), _('t'), '1'))

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
            return Decimal(locale.delocalize(value)) / factor
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
        'multiselection': convert_selection,
        'reference': convert_selection,
        'datetime': convert_datetime,
        'date': convert_date,
        'time': convert_time,
        'timedelta': convert_timedelta,
        'many2one': convert_many2one,
        }
    return converts.get(field['type'], lambda: value)()


def format_value(field, value, target=None, context=None):
    "Format value for field"
    if context is None:
        context = {}

    def format_boolean():
        if value is False:
            return _("False")
        elif value:
            return _("True")
        else:
            return ''

    def format_integer():
        factor = float(field.get('factor', 1))
        if (value
                or (isinstance(value, (int, float))
                    and not isinstance(value, bool))):
            return str(int(value * factor))
        return ''

    def format_float():
        if (not value
                and (not isinstance(value, (int, float, Decimal))
                    or isinstance(value, bool))):
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
        return time.strftime(format_)

    def format_date():
        if not value:
            return ''
        format_ = date_format(context.get('date_format'))
        return value.strftime(format_)

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
        'multiselection': format_selection,
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


def complete_value(field, value):
    "Complete value for field"

    def complete_boolean():
        if value is None:
            yield True
            yield False
        elif value:
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
        'multiselection': complete_selection,
        'reference': complete_reference,
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


class DomainParser(object):
    "A parser for domain"

    def __init__(self, fields, context=None):
        self.fields = OrderedDict()
        self.strings = OrderedDict()
        self.context = context

        def update_fields(fields, prefix='', string_prefix=''):
            for name, field in fields.items():
                if not field.get('searchable', True) or name == 'rec_name':
                    continue
                field = field.copy()
                fullname = '.'.join(filter(None, [prefix, name]))
                string = '.'.join(
                    filter(None, [string_prefix, field['string']]))
                field['string'] = string
                field['name'] = fullname
                self.fields[fullname] = field
                self.strings[string.lower()] = field
                rfields = field.get('relation_fields')
                if rfields:
                    update_fields(rfields, fullname, string)
        update_fields(fields)

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
            if ((
                        (clause[0] in ('AND', 'OR'))
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
                elif field['type'] == 'multiselection':
                    return not value or isinstance(value, list)
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
                escaped = value.replace('%%', '__')
                if escaped.startswith('%') and escaped.endswith('%'):
                    value = value[1:-1]
                return quote(value)
            field = self.fields[name]

            if len(clause) > 3:
                target = clause[3]
            else:
                target = None

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
            if (operator in OPERATORS
                    and field['type'] in ('char', 'text', 'selection')
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
                    elif field['type'] == 'multiselection':
                        if value is not None and not isinstance(value, list):
                            value = [value]

                    if not operator:
                        operator = default_operator(field)
                    if (isinstance(value, list)
                            and field['type'] != 'multiselection'):
                        if operator == '!':
                            operator = 'not in'
                        else:
                            operator = 'in'
                    if operator == '!':
                        operator = negate_operator(default_operator(field))
                    if value is None and operator.endswith('in'):
                        if operator.startswith('not'):
                            operator = '!='
                        else:
                            operator = '='
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

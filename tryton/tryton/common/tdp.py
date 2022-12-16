# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

# For explanation of this parser see
# http://effbot.org/zone/simple-top-down-parsing.htm

import datetime
import gettext
import re
import time
from decimal import Decimal
import decimal
import locale
import gtk

from tryton.translate import date_format
from tryton.common import datetime_strftime, HM_FORMAT, timezoned_date
from tryton.common.date_widget import DateEntry

_ = gettext.gettext

OPERATORS = set((
        '=',
        '>',
        '<',
        '<=',
        '>=',
        '!=',
        'in',
        'not in',
        'ilike',
        'not ilike'))

def operator(field):
    type_ = field['type'] if field else ''
    if type_ in ('char', 'text', 'many2one') or not field:
        return 'ilike'
    else:
        return '='


def cast(field, value):
    type_ = field['type'] if field else ''
    if type_ == 'boolean':
        return any(test.lower().startswith(value.lower()) for test in (_('y'),
                _('yes'), _('true'), '1'))
    elif type_ == 'integer':
        for conv in (int, float):
            try:
                return conv(value)
            except ValueError:
                continue
        return 0
    elif type_ == 'float':
        try:
            return float(value)
        except ValueError:
            return 0.0
    elif type_ == 'numeric':
        try:
            return Decimal(value)
        except decimal.InvalidOperation:
            return Decimal(0)
    elif type_ in ('selection', 'reference'):
        for key, text in field['selection']:
            if text == value:
                return key
        return value
    elif type_ == 'datetime':
        value = value.replace(' : ', ':') # Parser add spaces arround :
        try:
            value = datetime.datetime(*time.strptime(value,
                    date_format() + ' ' + HM_FORMAT)[:6])
        except ValueError:
            try:
                value = datetime.datetime(*time.strptime(value,
                        date_format())[:6])
            except ValueError:
                return False
        return timezoned_date(value)
    elif type_ == 'date':
        try:
            return datetime.date(*time.strptime(value, date_format())[:3])
        except ValueError:
            return False
    else:
        return value

def quote(value):
    for test in (':', ' '):
        if test in value:
            return '"%s"' % value
    return value


class Base(object):
    value = None

    fmt = '%s %s %s'

    def __init__(self, parser):
        self.parser = parser
        self.pos = None
        self.parent = None
        self._left = None
        self._right = None

    def _get_left(self):
        return self._left

    def _set_left(self, value):
        self._left = value
        value.pos = 'left'
        value.parent = self

    left = property(_get_left, _set_left)

    def _get_right(self):
        return self._right

    def _set_right(self, value):
        self._right = value
        value.pos = 'right'
        value.parent = self

    right = property(_get_right, _set_right)

    def domain(self, parent_field=None):
        raise NotImplementedError("domain method is missing on %s" % \
                self.__class__)

    def complete_fmt(self, left, value, right):
        return (self.fmt % (left, value, right)).strip()

    def complete(self, parent_field=None):
        left = self.left and tuple(self.left.complete()) or ('',)
        right = self.right and tuple(self.right.complete(parent_field)) or ('',)

        for lvalue in left:
            for rvalue in right:
                yield self.complete_fmt(lvalue, self.value, rvalue)

    def split(self, words=""):
        field, value = None, ' '.join(words)
        for i in xrange(len(words)):
            candidate = ' '.join(words[-i-1:])
            if candidate.lower() in self.parser.dom_fields:
                field = self.parser.dom_fields[candidate.lower()]
                value = ' '.join(words[:-i-1])

        return field, value

    def __str__(self, prefix=''):
        res = '%s[%s] %s'% (prefix, self.pos or 'root', self.value)
        res = res.ljust(30) + str(type(self))
        if self.left:
            res += "\n" + self.left.__str__(' ' + prefix)
        if self.right:
            res += "\n" + self.right.__str__(' ' + prefix)
        return res


class Literal(Base):
    lbp = 80

    def __init__(self, parser, value):
        super(Literal, self).__init__(parser)
        self.value = value

    def nud(self):
        return self

    def led(self, left):
        self.left = left
        return self

    def flatten(self):
        words = [self.value]
        node = self.left
        while node:
            if not isinstance(node, Literal):
                break
            words.insert(0, node.value)
            node = node.left
        return words

    def split(self, words=""):
        words = self.flatten()
        return super(Literal, self).split(words)

    def domain(self, parent_field=None):
        value = ' '.join(self.flatten())
        return [('rec_name', 'ilike', value + '%')]

    def suggest(self, words, suggestions):
        candidate = ''
        # Traking previous suggestion avoid duplicates when several
        # fields have the same ending (ex: "Menu" and "Parent Menu"):
        previous = set()
        for pos, word in enumerate(words):
            candidate = word + candidate
            for field in suggestions:
                if field.lower().startswith(candidate.lower()):
                    if words[pos+1:]:
                        new_item = ' '.join(reversed(words[pos+1:]))
                        new_item += ' ' + field
                    else:
                        new_item = field
                    if new_item not in previous:
                        previous.add(new_item)
                        yield new_item
            candidate = ' ' + candidate

    def suggest_ltr(self, words, suggestions):
        words = list(reversed(words))

        for field in suggestions:
            for i in xrange(len(words), 0, -1):
                candidate = ' '.join(words[:i])

                if field.lower().startswith(candidate.lower()):
                    new_item = quote(field)
                    if (i-len(words) < 0) and words[i-len(words):]:
                        find = False
                        for item in self.suggest(words[i - len(words):],
                                self.parser.sugg_fields):
                            yield new_item + ' ' + item + (':'
                                if self.pos == 'right' else '')
                            find = True
                        if find:
                            break
                        new_item += ' ' + ' '.join(words[i-len(words):])
                    yield new_item
                    break

    def complete(self, parent_field=None):
        item = self
        words = []
        while item:
            words.append(item.value)
            item = item.left

        orig = ' '.join(reversed(words)).lower()
        extra = values = []
        if parent_field:
            if parent_field['type'] in ('selection', 'reference', 'boolean'):
                if parent_field['type'] in ('selection', 'reference'):
                    suggestions = tuple(x[1] for x in parent_field['selection'])
                else:
                    suggestions = (_('Y'), _('Yes'), _('True'), '1', _('N'),
                        _('No'), _('False'), '0')
                for suggestion in self.suggest_ltr(words, suggestions):
                    if suggestion != orig:
                        extra.append(suggestion)
            elif parent_field['type'] in ('date', 'datetime'):
                format_ = date_format()
                if parent_field['type'] == 'datetime':
                    format_ += ' ' + HM_FORMAT
                entry = DateEntry(format_)
                entry.set_text(entry.initial_value)
                gtk.Entry.insert_text(entry, orig, 0)
                default = datetime_strftime(datetime.datetime.combine(
                        datetime.date.today(), datetime.time.min), format_)
                value = entry.compute_date(entry.get_text(), default) or ''
                if value:
                    if value.endswith(' 00:00:00'):
                        value = value[:-9]
                    if len(value) > len(orig):
                        extra.append(quote(value))

        if not extra:
            values = tuple(self.suggest(words, self.parser.sugg_fields))

        if not values and not extra:
            values = (quote(' '.join(reversed(words))),)
        elif (not self.parent) or self.pos == 'right':
            values = extra or tuple(v + ':' for v in values)

        right = self.right and tuple(self.right.complete())

        if not self.right:
            for value in values:
                yield value
        else:
            for value in values:
                for rvalue in right:
                    yield '%s %s' % (value, rvalue)


class InfixMixin:

    def nud(self):
        self.right = self.parser.expression(self.lbp)
        return self

    def led(self, left):
        self.left = left
        self.right = self.parser.expression(self.lbp)
        return self


class Colon(Base, InfixMixin):
    value = ':'
    lbp = 50
    fmt = '%s%s %s'

    def __init__(self, parser):
        self.extra_domain = []
        super(Colon, self).__init__(parser)

    def led(self, left):
        self.left = left
        # decreasing lbp makes Colon right-associative
        self.right = self.parser.expression(self.lbp - 1)
        return self

    def complete(self, parent_field=None):
        assert parent_field is None, parent_field

        if self.left:
            field, _ = self.left.split()
            left = self.left and tuple(self.left.complete(field)) or ('',)
        else:
            field = None
            left = ['']
        if not isinstance(self.right, Colon):
            right = tuple(self.right.complete(parent_field=field))
        else:
            right = self.right and tuple(self.right.complete()) or ('',)

        for lvalue in left:
            for rvalue in right:
                yield self.complete_fmt(lvalue, self.value, rvalue)

    def domain(self, parent_field=None):
        if self.left:
            field, value = self.left.split()
        else:
            field, value = None, ''

        #Recurse left
        if isinstance(self.left, Literal):
            if parent_field:
                value = cast(parent_field, value)
                if parent_field['type'] in ('char', 'text', 'many2one'):
                    value += '%'
                domain = [(parent_field['name'], operator(parent_field),
                        value)]
            elif value:
                domain = [('rec_name', 'ilike', value + '%')]
            else:
                domain = []
                node = self.left
                while node:
                    if not isinstance(node, Literal):
                        if node.domain():
                            domain = node.domain()
                        break
                    node = node.left
        elif self.left:
            domain = self.left.domain(parent_field)
        else:
            domain = []

        #Recurse right
        if isinstance(self.right, Literal) and field:
            value = cast(field, ' '.join(self.right.flatten()))
            if field['type'] in ('char', 'text', 'many2one'):
                value += '%'

            domain.append((field['name'] , operator(field), value))
        else:
            domain.extend(self.right.domain(field))

        return domain

class DoubleDot(Base, InfixMixin):
    value = '..'
    lbp = 70
    fmt = '%s%s%s'

    def split(self):
        assert isinstance(self.right, Literal)
        return self.right.split()

    def domain(self, parent_field=None):
        res = []
        if parent_field is not None:
            field_name = parent_field['name']
        else:
            field_name = 'rec_name'
        if self.left:
            value = cast(parent_field, ' '.join(self.left.flatten()))
            res.append((field_name, '>=', value))
        if self.right:
            _, value = self.right.split()
            value = cast(parent_field, value)
            res.append((field_name, '<', value))
        return res


class Comma(Base, InfixMixin):
    value = ';'
    lbp = 70
    fmt = '%s%s %s'

    def split(self, words=""):
        return self.right.split()

    def domain(self, parent_field=None):
        if parent_field is not None:
            field_name = parent_field['name']
        else:
            field_name = 'rec_name'

        _, value = self.right.split()
        values = [cast(parent_field, value)]
        if isinstance(self.right, Comma):
            values.append(cast(parent_field, ''))

        def walk(node, values):
            while node:
                if node.right:
                    if isinstance(node.right, Literal):
                        values.append(cast(parent_field,
                                ' '.join(node.right.flatten())))
                    else:
                        walk(node.right, values)
                if isinstance(node, Literal):
                    values.append(cast(parent_field,
                            ' '.join(node.flatten())))
                    break
                if not node.left:
                    values.append(cast(parent_field, ''))
                node = node.left
        walk(self.left, values)

        return [(field_name, 'in' , list(reversed(values)))]


class Comparator(Base, InfixMixin):
    value = ''
    lbp = 60
    fmt = '%s %s%s'

    def split(self):
        assert isinstance(self.right, Literal)
        return self.right.split()

    def domain(self, parent_field=None):
        res = []
        if parent_field is not None:
            field_name = parent_field['name']
        else:
            field_name = 'rec_name'

        if self.left:
            res.extend(self.left.domain(parent_field=parent_field))

        if self.right:
            _, value = self.right.split()
            value = cast(parent_field, value)
            res.append((field_name, self.value, value))
        return res

class LessThan(Comparator):
    value = '<'

class LessThanOrEqual(Comparator):
    value = '<='

class BiggerThan(Comparator):
    value = '>'

class BiggerThanOrEqual(Comparator):
    value = '>='


class Equal(Comparator):
    value = '='
    fmt = '%s%s%s'

    def domain(self, parent_field=None):
        assert not self.left, 'Unexpected left child %s' % self.left
        return super(Equal, self).domain(parent_field)


class Not(Base, InfixMixin):
    value = '!'
    lbp = 60
    fmt = '%s%s%s'

    def split(self):
        assert isinstance(self.right, (Literal, Comma))
        return self.right.split()

    def domain(self, parent_field=None):
        assert not self.left, 'Unexpected left child %s' % self.left
        res = []
        if parent_field is not None:
            field_name = parent_field['name']
        else:
            field_name = 'rec_name'

        if isinstance(self.right, Comma):
            (field_name, oper, value), = self.right.domain(parent_field)
            res.append((field_name, 'not %s' % oper, value))
        elif self.right:
            _, value = self.right.split()
            if parent_field:
                value = cast(parent_field, value)
            oper = operator(parent_field)
            if oper == 'ilike':
                oper = 'not ilike'
                value += '%'
            else:
                oper = '!='
            res.append((field_name, oper, value))
        return res

class NotEqual(Equal):
    value = '!='
    fmt = '%s%s%s'


class And(Base, InfixMixin):
    value = 'and'
    lbp = 40
    fmt = '%s %s %s'

    def domain(self, parent_field=None):
        result = []
        for token in (self.left, self.right):
            if token:
                dom = token.domain()
                if (isinstance(token, And)
                        and token.value == self.value):
                    result.extend(dom)
                else:
                    if len(dom) == 1:
                        dom, = dom
                    result.append(dom)
        return result


class Or(And):
    value = 'or'
    lbp = 30
    fmt = '%s %s %s'

    def domain(self, parent_field=None):
        result = super(Or, self).domain(parent_field)
        if result[0] != 'OR':
            return ['OR'] + result
        else:
            return result


class CloseParenthesis(Base):
    value = ')'
    lbp = 10
    fmt = '%s%s %s'

    def nud(self):
        return self

    def led(self, left):
        self.left = left
        return self

    def domain(self, parent_field=None):
        if self.left:
            return self.left.domain()
        return []

class OpenParenthesis(Base):
    value = '('
    lbp = 10
    fmt = '%s %s%s'

    def nud(self):
        expr = self.parser.expression(self.lbp)
        self.right = expr
        return self

    def led(self, left):
        expr = self.parser.expression(self.lbp)
        self.right = expr
        self.left = left
        return self

    def domain(self, parent_field=None):
        domain = []
        if self.left:
            domain = self.left.domain()

        if self.right:
            domain.append(self.right.domain())

        return domain


class End(Base):
    value = None
    lbp = 0

    def __init__(self, parser):
        super(End, self).__init__(parser)
        self.value = ''

    def nud(self):
        return self

    def domain(self, parent_field=None):
        return []

    def complete(self, parent_field=None):
        if parent_field:
            if parent_field['type'] in ('selection', 'reference'):
                return (x[1] for x in parent_field['selection'])
            elif parent_field['type'] in ('date', 'datetime'):
                format_ = date_format()
                return (datetime_strftime(datetime.date.today(), format_),)
            elif parent_field['type'] == 'boolean':
                return (_('True'), _('False'))
        return []

SPLIT_REGEXP = re.compile(
    r'("[^"]*"?)'
    '|(\bor\b)'
    '|(\band\b)'
    '|(\.\.)'
    '|(\()'
    '|(\))'
    '|(;)'
    '|([0-9]{1,2}:[0-9]{1,2}:[0-9]{1,2})'
    '|([0-9]{1,2}:[0-9]{1,2}:)'
    '|([0-9]{1,2}:)'
    '|(:)'
    '|(<)(?!=)'
    '|(<=)'
    '|(>)(?!=)'
    '|(>=)'
    '|(=)'
    '|(!)(?!=)'
    '|(!=)'
    '|(\s)'
    )

TOKENS = dict((t.value, t) for t in [
        And,
        Or,
        DoubleDot,
        Literal,
        Colon,
        OpenParenthesis,
        CloseParenthesis,
        Comma,
        LessThan,
        LessThanOrEqual,
        BiggerThan,
        BiggerThanOrEqual,
        Equal,
        Not,
        NotEqual,
        End] if t.value is not None)


class DomainParser:

    def __init__(self, fields):
        self.token_flow = None
        self.token = None
        self.fields = fields
        strings = {}
        for field in fields.itervalues():
            if not field.get('searchable', True):
                continue
            strings[field['string']] = field
        self.sugg_fields = tuple(strings)
        self.dom_fields = dict((key.lower(), value)
            for key, value in strings.iteritems())

    def tokenize(self, query):
        for token in SPLIT_REGEXP.split(query):
            if token:
                token = token.strip()
            if not token:
                continue
            yield token

    def expression(self, rbp=0):
        token = self.token
        self.token = self.next_token()
        left = token.nud()
        while self.token.lbp > rbp:
            token = self.token
            self.token = self.next_token()
            left = token.led(left)
        return left

    def next_token(self):
        try :
            new_tk = self.token_flow.next()
        except StopIteration:
            return End(self)

        if new_tk.startswith('"') or new_tk.endswith('"'):
            new_tk = new_tk.strip('"')

        if new_tk in TOKENS:
            return TOKENS[new_tk](self)

        return Literal(self, new_tk)

    def parse(self, input_string):
        self.token_flow = self.tokenize(input_string)
        self.token = self.next_token()
        return self.expression()

    def _string_char(self, field, operator, value):
        if not operator and isinstance(value, basestring):
            if value.endswith('%'):
                value = value[:-1]
            return '%s: %s' % (field['string'], quote(value))
        elif operator in ('not ilike', 'not'):
            operator = '!'
            if value.endswith('%'):
                value = value[:-1]
        if isinstance(value, (list, tuple)):
            value = '; '.join(map(quote, value))
        else:
            value = quote(value)
        return '%s: %s%s' % (field['string'], operator, value)

    _string_text = _string_char
    _string_many2one = _string_char

    def _string_integer(self, field, operator, value):
        if value is False:
            value = ''
        if isinstance(value, (list, tuple)):
            value = '; '.join(map(str, value))
        return '%s: %s%s' % (field['string'], operator, value)

    def _string_float(self, field, operator, value):
        digits = field.get('digits', (16, 2))
        format_ = lambda x: locale.format(
            '%.' + str(digits[1]) + 'f', x or 0.0, True)
        if isinstance(value, (list, tuple)):
            value = '; '.join(map(format_, value))
        else:
            value = format_(value)
        return '%s: %s%s' % (field['string'], operator, value)

    _string_numeric = _string_float

    def _string_selection(self, field, operator, value):
        selections = dict(field['selection'])
        if isinstance(value, (list, tuple)):
            value = '; '.join(quote(selections.get(x, x)) for x in value)
        else:
            value = quote(selections.get(value, value))
        return '%s: %s%s' % (field['string'], operator, value)

    _string_reference = _string_selection

    def _string_boolean(self, field, operator, value):
        format_ = lambda x: _('True') if x else _('False')
        if isinstance(value, (list, tuple)):
            value = '; '.join(format_(x) for x in value)
        else:
            value = format_(value)
        return '%s: %s' % (field['string'], value)

    def _string_datetime(self, field, operator, value):
        def format_(value):
            if not value:
                return ''
            else:
                if (not isinstance(value, datetime.datetime)
                        or value.time() == datetime.time.min):
                    format_ = date_format()
                else:
                    format_ = date_format() + ' ' + HM_FORMAT
                return quote(datetime_strftime(value, format_))
        if isinstance(value, (list, tuple)):
            value = '; '.join(map(format_, value))
        else:
            value = format_(value)
        return '%s: %s%s' % (field['string'], operator, value)

    def _string_date(self, field, operator, value):
        format_ = (lambda x: quote(datetime_strftime(x, date_format()))
            if x else '')
        if isinstance(value, (list, tuple)):
            value = '; '.join(map(format_, value))
        else:
            value = format_(value)
        return '%s: %s%s' % (field['string'], operator, value)

    def string(self, domain):
        if not domain:
            return ''
        if domain[0] in ('AND', 'OR'):
            nary = ' ' if domain[0] == 'AND' else ' or '
            domain = domain[1:]
        else:
            nary = ' '
        def format(expression):
            if (isinstance(expression, (list, tuple))
                    and len(expression) > 2
                    and isinstance(expression[1], basestring)
                    and expression[1] in OPERATORS):
                field_name, oper, value = expression
                if field_name == 'rec_name' and field_name not in self.fields:
                    if oper == 'ilike':
                        if value.endswith('%'):
                            value = value[:-1]
                    return quote(value)
                else:
                    field = self.fields[field_name]
                    def_op = operator(field)
                    if oper in (def_op, '!' + def_op) and value:
                        oper = oper.rstrip(def_op)
                    elif oper.endswith('in'):
                        if oper == 'not in':
                            oper = '!'
                        else:
                            oper = ''
                    return getattr(self, '_string_%s' % field['type'])(field,
                        oper, value)
            else:
                return '(' + self.string(expression) + ')'
        return nary.join(format(x) for x in domain)


def test_parser():
    fields = {
        'boolean': {
            'string': 'Boolean',
            'name': 'boolean',
            'type': 'boolean',
            },
        'selection': {
            'string': 'Selection',
            'name': 'selection',
            'type': 'selection',
            'selection': [
                ('spam', 'Spam'),
                ('ham', 'Ham'),
                ('spamham', 'Spamham'),
                ],
            },
        'date': {
            'string': 'Date',
            'name': 'date',
            'type': 'date',
            },
        'datetime': {
            'string': 'Date Time',
            'name': 'datetime',
            'type': 'datetime',
            },
        'char': {
            'string': 'Char',
            'name': 'char',
            'type': 'char',
            },
        'numeric': {
            'string': 'Numeric',
            'name': 'numeric',
            'type': 'numeric',
            },
        'integer': {
            'string': 'Integer',
            'name': 'integer',
            'type': 'integer',
            },
        'float': {
            'string': 'Float',
            'name': 'float',
            'type': 'float',
            },
        'notsearchable': {
            'string': 'Not Searchable',
            'name': 'notsearchable',
            'type': 'char',
            'searchable': False,
            },
        }
    return DomainParser(fields)

def test_selection_complete():
    parser = test_parser()
    assert list(parser.parse('S').complete()) == ['Selection:']
    assert list(parser.parse('Selection:').complete()) == ['Selection: Spam',
        'Selection: Ham', 'Selection: Spamham']
    assert list(parser.parse('Selection: H').complete()) == ['Selection: Ham']
    assert list(parser.parse('Selection: h').complete()) == ['Selection: Ham']
    assert list(parser.parse('Selection: =H').complete()) == [
        'Selection: =Ham']
    assert list(parser.parse('Selection: Ham').complete()) == [
        'Selection: Ham']
    assert list(parser.parse('Selection: S').complete()) == [
        'Selection: Spam',
        'Selection: Spamham',
        ]
    assert list(parser.parse('Selection: foo').complete()) == [
        'Selection: foo']
    assert list(parser.parse('Selection: Ham foo').complete()) == [
        'Selection: Ham foo']

def test_selection_domain():
    parser = test_parser()
    assert parser.parse('S').domain() == [('rec_name', 'ilike', 'S%')]
    assert parser.parse('Selection:').domain() == []
    assert parser.parse('Selection: H').domain() == [('selection', '=', 'H')]
    assert parser.parse('Selection: =H').domain() == [('selection', '=', 'H')]
    assert parser.parse('Selection: Ham').domain() == [
        ('selection', '=', 'ham')]
    assert parser.parse('Selection: Ham; Spam').domain() == [
        ('selection', 'in', ['ham', 'spam'])]

def test_selection_string():
    parser = test_parser()
    assert parser.string([]) == ''
    assert parser.string([('rec_name', 'ilike', 'S%')]) == 'S'
    assert parser.string([('selection', '=', 'H')]) == 'Selection: H'
    assert parser.string([('selection', '=', 'ham')]) == 'Selection: Ham'
    assert parser.string([('selection', '!=', 'ham')]) == 'Selection: !Ham'
    assert parser.string([('selection', 'in', ['ham', 'spam'])]) == \
        'Selection: Ham; Spam'

def test_boolean_complete():
    parser = test_parser()
    assert list(parser.parse('b').complete()) == ['Boolean:']
    assert list(parser.parse('boolean:').complete()) == ['Boolean: True',
        'Boolean: False']
    assert list(parser.parse('boolean: true').complete()) == ['Boolean: True']
    assert list(parser.parse('boolean: t').complete()) == ['Boolean: True']
    assert list(parser.parse('boolean: y').complete()) == ['Boolean: Y',
        'Boolean: Yes']
    assert list(parser.parse('boolean: 1').complete()) == ['Boolean: 1']
    assert list(parser.parse('boolean: false').complete()) == ['Boolean: False']
    assert list(parser.parse('boolean: f').complete()) == ['Boolean: False']
    assert list(parser.parse('boolean: n').complete()) == ['Boolean: N',
        'Boolean: No']
    assert list(parser.parse('boolean: 0').complete()) == ['Boolean: 0']
    assert list(parser.parse('boolean: =1').complete()) == ['Boolean: =1']

def test_boolean_domain():
    parser = test_parser()
    assert parser.parse('B').domain() == [('rec_name', 'ilike', 'B%')]
    assert parser.parse('Boolean:').domain() == []
    assert parser.parse('Boolean: true').domain() == [('boolean', '=', True)]
    assert parser.parse('Boolean: t').domain() == [('boolean', '=', True)]
    assert parser.parse('Boolean: y').domain() == [('boolean', '=', True)]
    assert parser.parse('Boolean: 1').domain() == [('boolean', '=', True)]
    assert parser.parse('Boolean: true; false').domain() == [
        ('boolean', 'in', [True, False])]

def test_boolean_string():
    parser = test_parser()
    assert parser.string([('boolean', '=', True)]) == 'Boolean: True'
    assert parser.string([('boolean', '=', False)]) == 'Boolean: False'
    assert parser.string([('boolean', 'in', [True, False])]) == \
        'Boolean: True; False'

def test_char_complete():
    parser = test_parser()
    assert list(parser.parse('c').complete()) == ['Char:']
    assert list(parser.parse('char:').complete()) == []
    assert list(parser.parse('char: bar').complete()) == ['Char: bar']
    assert list(parser.parse('Char: foo bar').complete()) == [
        'Char: "foo bar"']
    assert list(parser.parse('char: =foo').complete()) == ['Char: =foo']

def test_char_domain():
    parser = test_parser()
    assert parser.parse('c').domain() == [('rec_name', 'ilike', 'c%')]
    assert parser.parse('Char:').domain() == []
    assert parser.parse('Char: foo bar').domain() == [
        ('char', 'ilike', 'foo bar%')]
    assert parser.parse('Char: =foo').domain() == [('char', '=', 'foo')]
    assert parser.parse('Char: !foo').domain() == [
        ('char', 'not ilike', 'foo%')]
    assert parser.parse('Char: !=foo').domain() == [('char', '!=', 'foo')]
    assert parser.parse('Char: != foo').domain() == [('char', '!=', 'foo')]
    assert parser.parse('Char: 2; 3').domain() == [('char', 'in', ['2', '3'])]
    assert parser.parse('Char:! 2; 3').domain() == [('char', 'not in', ['2', '3'])]

def test_char_string():
    parser = test_parser()
    assert parser.string([('char', 'ilike', 'bar%')]) == 'Char: bar'
    assert parser.string([('char', 'ilike', 'foo bar%')]) == 'Char: "foo bar"'
    assert parser.string([('char', '=', 'foo')]) == 'Char: =foo'
    assert parser.string([('char', 'not ilike', 'foo%')]) == 'Char: !foo'
    assert parser.string([('char', '!=', 'foo')]) == 'Char: !=foo'
    assert parser.string([('char', 'in', ['2', '3'])]) == 'Char: 2; 3'
    assert parser.string([('char', 'not in', ['2', '3'])]) == 'Char: !2; 3'


def test_numeric_complete():
    parser = test_parser()
    assert list(parser.parse('numeric: 100').complete()) == [
        'Numeric: 100']

def test_numeric_domain():
    parser = test_parser()
    assert parser.parse('Numeric: >100').domain() == [
        ('numeric', '>', Decimal(100))]
    assert parser.parse('Numeric:>=100').domain() == [
        ('numeric', '>=', Decimal(100))]
    assert parser.parse('Numeric: =100').domain() == [
        ('numeric', '=', Decimal(100))]
    assert parser.parse('Numeric: 100').domain() == [
        ('numeric', '=', Decimal(100))]
    assert parser.parse('Numeric: foo').domain() == [
        ('numeric', '=', False)]
    assert parser.parse('Numeric: 2; 3').domain() == [
        ('numeric', 'in', [Decimal(2), Decimal(3)])]

def test_numeric_string():
    parser = test_parser()
    assert parser.string([('numeric', '=', Decimal(100))]) == 'Numeric: 100.00'
    assert parser.string([('numeric', 'in', [Decimal(2), Decimal(3)])]) == \
        'Numeric: 2.00; 3.00'

def test_integer_complete():
    parser = test_parser()
    assert list(parser.parse('integer: 42').complete()) == ['Integer: 42']
    assert list(parser.parse('integer: 2;3').complete()) == ['Integer: 2; 3']

def test_integer_domain():
    parser = test_parser()
    assert parser.parse('Integer: >42').domain() == [
        ('integer', '>', 42)]
    assert parser.parse('Integer: >=42').domain() == [
        ('integer', '>=', 42)]
    assert parser.parse('Integer: =42').domain() == [
        ('integer', '=', 42)]
    assert parser.parse('Integer: 42').domain() == [
        ('integer', '=', 42)]
    assert parser.parse('Integer: 3.14').domain() == [
        ('integer', '=', 3.14)]
    assert parser.parse('Integer: foo').domain() == [
        ('integer', '=', False)]
    assert parser.parse('Integer: 2; 3').domain() == [
        ('integer', 'in', [2, 3])]

def test_integer_string():
    parser = test_parser()
    assert parser.string([('integer', '=', 42)]) == 'Integer: 42'
    assert parser.string([('integer', '=', False)]) == 'Integer: ='
    assert parser.string([('integer', 'in', [2, 3])]) == 'Integer: 2; 3'


def test_float_complete():
    parser = test_parser()
    assert list(parser.parse('float: 3.14').complete()) == ['Float: 3.14']

def test_float_domain():
    parser = test_parser()
    assert parser.parse('Float: >3.14').domain() == [
        ('float', '>', 3.14)]
    assert parser.parse('Float: >=3.14').domain() == [
        ('float', '>=', 3.14)]
    assert parser.parse('Float: =3.14').domain() == [
        ('float', '=', 3.14)]
    assert parser.parse('Float: 3.14').domain() == [
        ('float', '=', 3.14)]
    assert parser.parse('Float: 42').domain() == [
        ('float', '=', 42.0)]
    assert parser.parse('Float: foo').domain() == [
        ('float', '=', False)]

def test_float_string():
    parser = test_parser()
    assert parser.string([('float', '=', 3.14)]) == 'Float: 3.14'
    assert parser.string([('float', '=', 42)]) == 'Float: 42.00'
    assert parser.string([('float', '>', 42)]) == 'Float: >42.00'
    assert parser.string([('float', 'not in', [3.14, 42])]) == \
        'Float: !3.14; 42.00'

def test_date_complete():
    today = datetime.date.today()
    today_str = datetime_strftime(today, date_format())
    parser = test_parser()
    assert list(parser.parse('Date:').complete()) == [
        'Date Time: ' + today_str,
        'Date: ' + today_str,
        ]
    assert list(parser.parse('Date: ' + today_str[0:2]).complete()) == [
        'Date Time: ' + today_str,
        'Date: ' + today_str,
        ]
    assert list(parser.parse('Date: 12').complete()) == [
        'Date Time: 12' + today_str[2:],
        'Date: 12' + today_str[2:],
        ]
    assert list(parser.parse('Date: 12/04').complete()) == [
        'Date Time: 12/04' + today_str[5:],
        'Date: 12/04' + today_str[5:],
        ]
    assert list(parser.parse('Date: 12/4').complete()) == [
        'Date Time: 12/04' + today_str[5:],
        'Date: 12/04' + today_str[5:],
        ]
    assert list(parser.parse('Date: 12/4/2002').complete()) == [
        'Date Time: 12/04/2002',
        'Date: 12/04/2002',
        ]

def test_date_domain():
    today = datetime.date.today()
    today_str = datetime_strftime(today, date_format())
    parser = test_parser()
    assert parser.parse('Date:').domain() == []
    assert parser.parse('Date: ' + today_str[0]).domain() == [
        ('date', '=', False)]
    assert parser.parse('Date: >' + today_str[0]).domain() == [
        ('date', '>', False)]
    assert parser.parse('Date: 12/04/2002').domain() == [
        ('date', '=', datetime.date(2002, 12, 4))]
    assert parser.parse('Date: 12/4/2002').domain() == [
        ('date', '=', datetime.date(2002, 12, 4))]
    assert parser.parse('Date: 12/4/2002; 1/1/1970').domain() == [
        ('date', 'in', [datetime.date(2002, 12, 4), datetime.date(1970, 1, 1)])]

def test_date_string():
    parser = test_parser()
    assert parser.string([('date', '=', False)]) == 'Date: ='
    assert parser.string([('date', '>=', datetime.date(2002, 12, 4))]) == \
        'Date: >=12/04/2002'
    assert parser.string([('date', 'in', [datetime.date(2002, 12, 4),
                    datetime.date(1970, 1, 1)])]) == \
                        'Date: 12/04/2002; 01/01/1970'

def test_datetime_complete():
    today = datetime.date.today()
    today_str = datetime_strftime(today, date_format())
    parser = test_parser()
    assert list(parser.parse('Date Time: ' + today_str).complete()) == [
        'Date Time: ' + today_str]
    assert list(parser.parse('Date Time: "' + today_str + ' 12:30:00"'
            ).complete()) == ['Date Time: "' + today_str + ' 12:30:00"']
    assert list(parser.parse('Date Time: ' + today_str + ' 12:30:00'
            ).complete()) == ['Date Time: "' + today_str + ' 12:30:00"']

def test_datetime_domain():
    today = datetime.date.today()
    today_str = datetime_strftime(today, date_format())
    parser = test_parser()
    assert parser.parse('Date Time: ' + today_str).domain() == [
        ('datetime', '=', datetime.datetime.combine(today, datetime.time.min))]
    assert parser.parse('Date Time: "' + today_str + ' 12:30:00"').domain() ==\
        [('datetime', '=', datetime.datetime.combine(today,
                    datetime.time(12, 30)))]
    assert parser.parse('Date Time: ' + today_str + ' 12:30:00').domain() == [
        ('datetime', '=', datetime.datetime.combine(today,
                    datetime.time(12, 30)))]
    assert parser.parse('Date Time: foo').domain() == [
        ('datetime', '=', False)]
    assert parser.parse('Date Time: 12/4/2002; 1/1/1970').domain() == [
        ('datetime', 'in', [
                datetime.datetime.combine(datetime.date(2002, 12, 4),
                    datetime.time.min),
                datetime.datetime.combine(datetime.date(1970, 1, 1),
                    datetime.time.min)])]

def test_datetime_string():
    parser = test_parser()
    assert parser.string([('datetime', '=', False)]) == 'Date Time: ='
    assert parser.string([('datetime', '=', datetime.datetime(2002, 12, 4, 12,
                    30))]) == 'Date Time: "12/04/2002 12:30:00"'
    assert parser.string([('datetime', '=', datetime.datetime(2002, 12, 4, 0,
                    0))]) == 'Date Time: 12/04/2002'
    assert parser.string([('datetime', 'in', [
                    datetime.datetime.combine(datetime.date(2002, 12, 4),
                        datetime.time.min),
                    datetime.datetime.combine(datetime.date(1970, 1, 1),
                        datetime.time.min)])]) == \
                            'Date Time: 12/04/2002; 01/01/1970'

def test_composite_complete():
    today = datetime.date.today()
    today_str = datetime_strftime(today, date_format())
    parser = test_parser()
    assert list(parser.parse(': foo').complete()) == [': foo']
    assert list(parser.parse(': foo b').complete()) == [': foo Boolean:']
    assert list(parser.parse('char: foo boolean: false').complete()) == [
        'Char: foo Boolean: False']
    assert list(parser.parse('char: foo or char: bar').complete()) == [
        'Char: foo or Char: bar']
    assert list(parser.parse('char: foo b').complete()) == [
        'Char: foo Boolean:']
    assert list(parser.parse('(char: foo b').complete()) == [
        '(Char: foo Boolean:']
    assert list(parser.parse('char: foo and b').complete()) == [
        'Char: foo and Boolean:']
    assert list(parser.parse('(char: foo and b').complete()) == [
        '(Char: foo and Boolean:']
    assert list(parser.parse('selection: Ham c').complete()) == [
        'Selection: Ham Char:']
    assert list(parser.parse('selection: ham c').complete()) == [
        'Selection: Ham Char:']
    assert list(parser.parse('date: ' + today_str + ' c').complete()) == [
        'Date Time: ' + today_str + ' Char:',
        'Date: ' + today_str + ' Char:']
    assert list(parser.parse('Selection: H Selection').complete()) == [
        'Selection: Ham Selection:']
    assert list(parser.parse('Selection: H or Selection').complete()) == [
        'Selection: Ham or Selection:']
    assert list(parser.parse('Selection: H Selection:').complete()) == [
        'Selection: Ham Selection: Spam',
        'Selection: Ham Selection: Ham',
        'Selection: Ham Selection: Spamham']
    assert list(parser.parse('Selection: H or Selection:').complete()) == [
        'Selection: Ham or Selection: Spam',
        'Selection: Ham or Selection: Ham',
        'Selection: Ham or Selection: Spamham']
    assert list(parser.parse('Selection: H Selection: S').complete()) == [
        'Selection: Ham Selection: Spam',
        'Selection: Ham Selection: Spamham',
        ]
    assert list(parser.parse('Selection: H or Selection: S').complete()) == [
        'Selection: Ham or Selection: Spam',
        'Selection: Ham or Selection: Spamham',
        ]

def test_composite_domain():
    parser = test_parser()
    assert parser.parse('char: foo boolean: false').domain() == [
        ('char', 'ilike', 'foo%'), ('boolean', '=', False)]
    assert parser.parse('char: foo and char: bar').domain() == [
        ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')]
    assert parser.parse('char: foo or char: bar').domain() == [
        'OR', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')]
    assert parser.parse('char: foo or char: bar and boolean: 1').domain() == [
        'OR', ('char', 'ilike', 'foo%'), [
            ('char', 'ilike', 'bar%'), ('boolean', '=', True)]]
    assert parser.parse('char: foo and char: bar or boolean: 0').domain() == [
        'OR', [('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')],
        ('boolean', '=', False)]
    assert parser.parse('char: foo and char: bar and boolean: 0').domain() == [
        ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%'),
        ('boolean', '=', False)]
    assert parser.parse('char: foo or char: bar or boolean: 0').domain() == [
        'OR', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%'),
        ('boolean', '=', False)]
    assert parser.parse('(char: foo or char: bar) and boolean: 1').domain() == [
        ['OR', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')],
        ('boolean', '=', True)]
    assert parser.parse('(char: foo or char: bar) boolean: 1').domain() == [
        ['OR', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')],
        ('boolean', '=', True)]
    assert parser.parse('(char: foo or char: bar) and Date Time: 12/4/2002'
        ).domain() == [
            ['OR', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')],
            ('datetime', '=', datetime.datetime(2002, 12, 4, 0, 0))]
    assert parser.parse('(char: foo or char: bar) Date Time: 12/4/2002').domain() == [
        ['OR', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')],
        ('datetime', '=', datetime.datetime(2002, 12, 4, 0, 0))]
    assert parser.parse('char: foo or (char: bar and boolean: 1)').domain() == [
        'OR', ('char', 'ilike', 'foo%'), [
            ('char', 'ilike', 'bar%'), ('boolean', '=', True)]]
    assert parser.parse('char: foo and (char: bar or boolean: 0)').domain() == [
        ('char', 'ilike', 'foo%'),
        ['OR', ('char', 'ilike', 'bar%'), ('boolean', '=', False)]]
    assert parser.parse('char: foo (char: bar or boolean: 0)').domain() == [
        ('char', 'ilike', 'foo%'),
        ['OR', ('char', 'ilike', 'bar%'), ('boolean', '=', False)]]
    assert parser.parse('char: foo and ((char: bar or boolean: 0))'
        ).domain() == [('char', 'ilike', 'foo%'),
                       [['OR', ('char', 'ilike', 'bar%'),
                         ('boolean', '=', False)]]]
    assert parser.parse('char: foo ((char: bar or boolean: 0))'
        ).domain() == [
            ('char', 'ilike', 'foo%'),
            [['OR', ('char', 'ilike', 'bar%'), ('boolean', '=', False)]]]
    assert parser.parse('char: foo (char: test (char: bar or boolean: 0))'
        ).domain() == [
            ('char', 'ilike', 'foo%'),
            [('char', 'ilike', 'test%')],
                ['OR', ('char', 'ilike', 'bar%'), ('boolean', '=', False)]]
    assert parser.parse('char: foo and (').domain() == [
        ('char', 'ilike', 'foo%'), []]
    assert parser.parse('char: foo and ()').domain() == [
        ('char', 'ilike', 'foo%'), []]
    assert parser.parse('char: foo and (char: bar or boolean: 0').domain() == [
        ('char', 'ilike', 'foo%'),
        ['OR', ('char', 'ilike', 'bar%'), ('boolean', '=', False)]]
    assert parser.parse('Selection: Ham Selection: Spam').domain() == [
        ('selection', '=', 'ham'), ('selection', '=', 'spam')]
    assert parser.parse('Selection: =Ham Selection: =Spam').domain() == [
        ('selection', '=', 'ham'), ('selection', '=', 'spam')]
    assert parser.parse('Selection: !Ham Selection: !Spam').domain() == [
        ('selection', '!=', 'ham'), ('selection', '!=', 'spam')]
    assert parser.parse('Selection: !Ham; Spam Char: bar').domain() == [
        ('selection', 'not in', ['ham', 'spam']), ('char', 'ilike', 'bar%')]


def test_composite_string():
    parser = test_parser()
    assert parser.string([
            ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')]) == \
                'Char: foo Char: bar'
    assert parser.string([
            'AND', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')]) == \
                'Char: foo Char: bar'
    assert parser.string([
            'OR', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')]) == \
                'Char: foo or Char: bar'
    assert parser.string([
            'OR', ('char', 'ilike', 'foo%'), [
                ('char', 'ilike', 'bar%'), ('boolean', '=', True)]]) == \
                    'Char: foo or (Char: bar Boolean: True)'
    assert parser.string([
            'OR', [('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%')],
            ('boolean', '=', False)]) == \
                '(Char: foo Char: bar) or Boolean: False'
    assert parser.string([
            ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%'),
            ('boolean', '=', False)]) == \
                'Char: foo Char: bar Boolean: False'
    assert parser.string([
            'OR', ('char', 'ilike', 'foo%'), ('char', 'ilike', 'bar%'),
            ('boolean', '=', False)]) == \
                'Char: foo or Char: bar or Boolean: False'
    assert parser.string([
            'OR', ('char', 'ilike', 'foo%'), [
                ('char', 'ilike', 'bar%'), ('boolean', '=', True)]]) == \
                    'Char: foo or (Char: bar Boolean: True)'
    assert parser.string([
            ('char', 'ilike', 'foo%'),
            ['OR', ('char', 'ilike', 'bar%'), ('boolean', '=', False)]]) == \
                'Char: foo (Char: bar or Boolean: False)'

def test_quote_complete():
    parser = test_parser()
    assert list(parser.parse('"char"').complete()) == ['Char:']
    assert list(parser.parse('"char:"').complete()) == ['"char:"']
    assert list(parser.parse('"Char:"').complete()) == ['"Char:"']
    assert list(parser.parse('char: "foo bar"').complete()) == [
        'Char: "foo bar"']
    assert list(parser.parse('Char: "Boolean: false"').complete()) == [
        'Char: "Boolean: false"']

def test_quote_domain():
    parser = test_parser()
    assert parser.parse('"char"').domain() == [('rec_name', 'ilike', 'char%')]
    assert parser.parse('char: "foo bar"').domain() == [
        ('char', 'ilike', 'foo bar%')]

def test_quote_string():
    parser = test_parser()
    assert parser.string([('rec_name', 'ilike', 'char:%')]) == '"char:"'
    assert parser.string([('char', 'ilike', 'foo bar%')]) == 'Char: "foo bar"'
    assert parser.string([('char', 'ilike', 'Boolean: false%')]) == \
        'Char: "Boolean: false"'

def test_column():
    parser = test_parser()
    assert parser.parse(':').domain() == []
    assert parser.parse('::').domain() == []
    assert parser.parse(': foo').domain() == [('rec_name', 'ilike', 'foo%')]
    assert parser.parse('foo :').domain() == [('rec_name', 'ilike', 'foo%')]
    assert parser.parse(': foo b').domain() == [('rec_name', 'ilike', 'foo b%')]
    assert parser.parse('": foo b"').domain() == [
        ('rec_name', 'ilike', ': foo b%')]

def test_double_dot():
    parser = test_parser()
    assert parser.parse('Integer: 0..42').domain() == [
        ('integer', '>=', 0), ('integer', '<', 42)]
    assert parser.parse('Numeric: 0..42').domain() == [
        ('numeric', '>=', Decimal(0)), ('numeric', '<', Decimal(42))]
    assert parser.parse('a..z').domain() == [
        ('rec_name', '>=', 'a'), ('rec_name', '<', 'z')]
    assert parser.parse('Char: a..z').domain() == [
        ('char', '>=', 'a'), ('char', '<', 'z')]
    assert parser.parse('Integer: 0..42 Char: foo').domain() == [
        ('integer', '>=', 0), ('integer', '<', 42), ('char', 'ilike', 'foo%')]

def test_comma():
    parser = test_parser()
    assert parser.parse('Char: foo; bar').domain() == [
        ('char', 'in', ['foo', 'bar'])]
    assert parser.parse('foo; bar').domain() == [
        ('rec_name', 'in', ['foo', 'bar'])]
    assert parser.parse('Char: foo; bar Selection: Ham').domain() == [
        ('char', 'in', ['foo', 'bar']), ('selection', '=', 'ham')]
    assert parser.parse('Char: foo bar; test').domain() == [
        ('char', 'in', ['foo bar', 'test'])]
    assert parser.parse('Char: foo; bar; Selection: Ham').domain() == [
        ('char', 'in', ['foo', 'bar', '']), ('selection', '=', 'ham')]
    assert parser.parse('Char: ;foo; bar').domain() == [
        ('char', 'in', ['', 'foo', 'bar'])]
    assert parser.parse('Char: foo;; bar').domain() == [
        ('char', 'in', ['foo', '', 'bar'])]
    assert parser.parse('Char: foo;;; bar').domain() == [
        ('char', 'in', ['foo', '', 'bar'])]
    assert parser.parse('Char: ;;foo;; bar;;').domain() == [
        ('char', 'in', ['', '', 'foo', '', 'bar', '', ''])]
    assert parser.parse('Integer: 0; 1; 1; 2; 3; 5').domain() == [
        ('integer', 'in', [0, 1, 1, 2, 3, 5])]
    assert parser.parse('Integer: 0; 1;; 2; 3').domain() == [
        ('integer', 'in', [0, 1, 0, 2, 3])]

def test_comparator():
    parser = test_parser()
    assert parser.parse('< foo').domain() == [
        ('rec_name', '<', 'foo')]
    assert parser.parse('=foo').domain() == [
        ('rec_name', '=', 'foo')]
    assert parser.parse('!foo').domain() == [
        ('rec_name', 'not ilike', 'foo%')]
    assert parser.parse('!=foo').domain() == [
        ('rec_name', '!=', 'foo')]
    assert parser.parse('Integer:< Selection: Ham').domain() == [
        ('integer', '<', 0), ('selection', '=', 'ham')]
    assert parser.parse('Integer: << 10').domain() == [
        ('integer', '<', 10)]
    assert parser.parse('Integer: <> 10').domain() == [
        ('integer', '<', 10)]
    assert parser.parse('Integer: !10').domain() == [
        ('integer', '!=', 10)]
    assert parser.parse('foo <').domain() == [
        ('rec_name', 'ilike', 'foo%'), ('rec_name', '<', '')]

def test_str():
    parser = test_parser()
    assert str(parser.parse('foo bar spam ham =')) == '''\
[root] =                      <class 'tryton.common.tdp.Equal'>
 [left] ham                   <class 'tryton.common.tdp.Literal'>
  [left] spam                 <class 'tryton.common.tdp.Literal'>
   [left] bar                 <class 'tryton.common.tdp.Literal'>
    [left] foo                <class 'tryton.common.tdp.Literal'>
 [right]                      <class 'tryton.common.tdp.End'>'''

if __name__ == '__main__':
    test_comparator()
    test_comma()
    test_double_dot()
    test_column()
    test_selection_complete()
    test_selection_domain()
    test_selection_string()
    test_boolean_complete()
    test_boolean_domain()
    test_boolean_string()
    test_char_complete()
    test_char_domain()
    test_char_string()
    test_numeric_complete()
    test_numeric_domain()
    test_numeric_string()
    test_integer_complete()
    test_integer_domain()
    test_integer_string()
    test_float_complete()
    test_float_domain()
    test_float_string()
    test_date_complete()
    test_date_domain()
    test_date_string()
    test_datetime_complete()
    test_datetime_domain()
    test_datetime_string()
    test_composite_complete()
    test_composite_domain()
    test_composite_string()
    test_quote_complete()
    test_quote_domain()
    test_quote_string()

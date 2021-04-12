# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import re
import operator
import datetime
from collections import defaultdict
from functools import reduce, partial


def sql_like(value, pattern, ignore_case=True):
    flag = re.IGNORECASE if ignore_case else 0

    escape = False
    chars = []
    for char in re.split(r'(\\|.)', pattern)[1::2]:
        if escape:
            if char in ('%', '_'):
                chars.append(char)
            else:
                chars.extend(['\\', char])
            escape = False
        elif char == '\\':
            escape = True
        elif char == '_':
            chars.append('.')
        elif char == '%':
            chars.append('.*')
        else:
            chars.append(re.escape(char))

    regexp = re.compile(''.join(chars), flag)
    return bool(regexp.fullmatch(value))


like = partial(sql_like, ignore_case=False)
ilike = partial(sql_like, ignore_case=True)


def in_(a, b):
    if isinstance(a, (list, tuple)):
        if isinstance(b, (list, tuple)):
            return any(operator.contains(b, x) for x in a)
        else:
            return operator.contains(a, b)
    else:
        return operator.contains(b, a)


OPERATORS = defaultdict(lambda: lambda a, b: True)
OPERATORS.update({
        '=': operator.eq,
        '>': operator.gt,
        '<': operator.lt,
        '<=': operator.le,
        '>=': operator.ge,
        '!=': operator.ne,
        'in': in_,
        'not in': lambda a, b: not in_(a, b),
        'ilike': ilike,
        'not ilike': lambda a, b: not ilike(a, b),
        'like': like,
        'not like': lambda a, b: not like(a, b),
        })


def locale_part(expression, field_name, locale_name='id'):
    if expression == field_name:
        return locale_name
    if '.' in expression:
        fieldname, local = expression.split('.', 1)
        return local
    return expression


def is_leaf(expression):
    return (isinstance(expression, (list, tuple))
        and len(expression) > 2
        and isinstance(expression[1], str))


def constrained_leaf(part, boolop=operator.and_):
    field, operand, value = part[:3]
    if operand == '=' and boolop == operator.and_:
        # We should consider that other domain inversion will set a correct
        # value to this field
        return True
    return False


def eval_leaf(part, context, boolop=operator.and_):
    field, operand, value = part[:3]
    if '.' in field:
        # In the case where the leaf concerns a m2o then having a value in the
        # evaluation context is deemed suffisant
        return bool(context.get(field.split('.')[0]))
    context_field = context.get(field)
    if isinstance(context_field, datetime.date) and not value:
        if isinstance(context_field, datetime.datetime):
            value = datetime.datetime.min
        else:
            value = datetime.date.min
    if isinstance(value, datetime.date) and not context_field:
        if isinstance(value, datetime.datetime):
            context_field = datetime.datetime.min
        else:
            context_field = datetime.date.min
    if isinstance(context_field, (list, tuple)) and value is None:
        value = type(context_field)()
    if (isinstance(context_field, str)
            and isinstance(value, (list, tuple))):
        try:
            value = '%s,%s' % tuple(value)
        except TypeError:
            pass
    elif (isinstance(context_field, (list, tuple))
            and isinstance(value, str)):
        try:
            context_field = '%s,%s' % tuple(context_field)
        except TypeError:
            pass
    elif ((isinstance(context_field, list) and isinstance(value, tuple))
            or (isinstance(context_field, tuple) and isinstance(value, list))):
        context_field = list(context_field)
        value = list(value)
    if (operand in ('=', '!=')
            and isinstance(context_field, (list, tuple))
            and isinstance(value, int)):
        operand = {
            '=': 'in',
            '!=': 'not in',
            }[operand]
    try:
        return OPERATORS[operand](context_field, value)
    except TypeError:
        return False


def inverse_leaf(domain):
    if domain in ('AND', 'OR'):
        return domain
    elif is_leaf(domain):
        if 'child_of' in domain[1] and '.' not in domain[0]:
            if len(domain) == 3:
                return domain
            else:
                return [domain[3]] + list(domain[1:])
        return domain
    else:
        return list(map(inverse_leaf, domain))


def filter_leaf(domain, field, model):
    if domain in ('AND', 'OR'):
        return domain
    elif is_leaf(domain):
        if domain[0].startswith(field) and len(domain) > 3:
            if domain[3] != model:
                return ('id', '=', None)
        return domain
    else:
        return [filter_leaf(d, field, model) for d in domain]


def prepare_reference_domain(domain, reference):
    "convert domain to replace reference fields by their local part"

    def value2reference(value):
        model, ref_id = None, None
        if isinstance(value, str) and ',' in value:
            model, ref_id = value.split(',', 1)
            if ref_id != '%':
                try:
                    ref_id = int(ref_id)
                except ValueError:
                    model, ref_id = None, value
        elif (isinstance(value, (list, tuple))
                and len(value) == 2
                and isinstance(value[0], str)
                and (isinstance(value[1], int) or value[1] == '%')):
            model, ref_id = value
        else:
            ref_id = value
        return model, ref_id

    if domain in ('AND', 'OR'):
        return domain
    elif is_leaf(domain):
        if domain[0] == reference:
            if domain[1] in {'=', '!='}:
                model, ref_id = value2reference(domain[2])
                if model is not None:
                    if ref_id == '%':
                        if domain[1] == '=':
                            return [reference + '.id', '!=', None, model]
                        else:
                            return [reference, 'not like', domain[2]]
                    return [reference + '.id', domain[1], ref_id, model]
            elif domain[1] in {'in', 'not in'}:
                model_values = {}
                for value in domain[2]:
                    model, ref_id = value2reference(value)
                    if model is None:
                        break
                    model_values.setdefault(model, []).append(ref_id)
                else:
                    new_domain = ['OR'] if domain[1] == 'in' else ['AND']
                    for model, ref_ids in model_values.items():
                        if '%' in ref_ids:
                            if domain[1] == 'in':
                                new_domain.append(
                                    [reference + '.id', '!=', None, model])
                            else:
                                new_domain.append(
                                    [reference, 'not like', model + ',%'])
                        else:
                            new_domain.append(
                                [reference + '.id', domain[1], ref_ids, model])
                    return new_domain
            return []
        return domain
    else:
        return [prepare_reference_domain(d, reference) for d in domain]


def extract_reference_models(domain, field_name):
    "returns the set of the models available for field_name"
    if domain in ('AND', 'OR'):
        return set()
    elif is_leaf(domain):
        local_part = domain[0].split('.', 1)[0]
        if local_part == field_name and len(domain) > 3:
            return {domain[3]}
        return set()
    else:
        return reduce(operator.or_,
            (extract_reference_models(d, field_name) for d in domain))


def eval_domain(domain, context, boolop=operator.and_):
    "compute domain boolean value according to the context"
    if is_leaf(domain):
        return eval_leaf(domain, context, boolop=boolop)
    elif not domain and boolop is operator.and_:
        return True
    elif not domain and boolop is operator.or_:
        return False
    elif domain[0] == 'AND':
        return eval_domain(domain[1:], context)
    elif domain[0] == 'OR':
        return eval_domain(domain[1:], context, operator.or_)
    else:
        return boolop(eval_domain(domain[0], context),
            eval_domain(domain[1:], context, boolop))


def localize_domain(domain, field_name=None, strip_target=False):
    "returns only locale part of domain. eg: langage.code -> code"
    if domain in ('AND', 'OR', True, False):
        return domain
    elif is_leaf(domain):
        if 'child_of' in domain[1]:
            if domain[0].count('.'):
                _, target_part = domain[0].split('.', 1)
                return [target_part] + list(domain[1:])
            if len(domain) == 3:
                return domain
            else:
                return [domain[3]] + list(domain[1:-1])
        locale_name = 'id'
        if isinstance(domain[2], str):
            locale_name = 'rec_name'
        n = 3 if strip_target else 4
        return [locale_part(domain[0], field_name, locale_name)] \
            + list(domain[1:n]) + list(domain[4:])
    else:
        return [localize_domain(part, field_name, strip_target)
            for part in domain]


def simplify(domain):
    "remove unused domain delimiter"
    if is_leaf(domain):
        return domain
    elif domain in ('OR', 'AND'):
        return domain
    elif domain in (['OR'], ['AND']):
        return []
    elif (isinstance(domain, list) and len(domain) == 1
            and not is_leaf(domain[0])):
        return simplify(domain[0])
    elif (isinstance(domain, list) and len(domain) == 2
            and domain[0] in ('AND', 'OR')):
        return [simplify(domain[1])]
    else:
        return [simplify(branch) for branch in domain]


def merge(domain, domoperator=None):
    if not domain or domain in ('AND', 'OR'):
        return []
    domain_type = 'OR' if domain[0] == 'OR' else 'AND'
    if is_leaf(domain):
        return [domain]
    elif domoperator is None:
        return [domain_type] + reduce(operator.add,
                [merge(e, domain_type) for e in domain])
    elif domain_type == domoperator:
        return reduce(operator.add, [merge(e, domain_type) for e in domain])
    else:
        # without setting the domoperator
        return [merge(domain)]


def concat(*domains, **kwargs):
    domoperator = kwargs.get('domoperator')
    result = []
    if domoperator:
        result.append(domoperator)
    for domain in domains:
        if domain:
            result.append(domain)
    return simplify(merge(result))


def unique_value(domain):
    "Return if unique, the field and the value"
    if (isinstance(domain, list)
            and len(domain) == 1
            and '.' not in domain[0][0]
            and domain[0][1] == '='):
        return True, domain[0][1], domain[0][2]
    else:
        return False, None, None


def parse(domain):
    if is_leaf(domain):
        return domain
    elif not domain:
        return And([])
    elif domain[0] == 'OR':
        return Or(domain[1:])
    else:
        return And(domain[1:] if domain[0] == 'AND' else domain)


def domain_inversion(domain, symbol, context=None):
    """compute an inversion of the domain eventually the context is used to
    simplify the expression"""
    if context is None:
        context = {}
    expression = parse(domain)
    if symbol not in expression.variables:
        return True
    return expression.inverse(symbol, context)


class And(object):

    def __init__(self, expressions):
        self.branches = list(map(parse, expressions))
        self.variables = set()
        for expression in self.branches:
            if is_leaf(expression):
                self.variables.add(self.base(expression[0]))
            elif isinstance(expression, And):
                self.variables |= expression.variables

    def base(self, expression):
        if '.' not in expression:
            return expression
        else:
            return expression.split('.')[0]

    def inverse(self, symbol, context):
        result = []
        for part in self.branches:
            if isinstance(part, And):
                part_inversion = part.inverse(symbol, context)
                evaluated = isinstance(part_inversion, bool)
                if symbol not in part.variables:
                    continue
                if not evaluated:
                    result.append(part_inversion)
                elif part_inversion:
                    continue
                else:
                    return False
            elif is_leaf(part) and self.base(part[0]) == symbol:
                result.append(part)
            else:
                field = part[0]
                if (field not in context
                        or field in context
                        and (eval_leaf(part, context, operator.and_)
                            or constrained_leaf(part, operator.and_))):
                    result.append(True)
                else:
                    return False

        result = [e for e in result if e is not True]
        if result == []:
            return True
        else:
            return simplify(result)


class Or(And):

    def inverse(self, symbol, context):
        result = []
        known_variables = set(context.keys())
        if not known_variables >= (self.variables - {symbol}):
            # In this case we don't know enough about this OR part, we
            # consider it to be True (because people will have the constraint
            # on this part later).
            return True
        for part in self.branches:
            if isinstance(part, And):
                part_inversion = part.inverse(symbol, context)
                evaluated = isinstance(part_inversion, bool)
                if symbol not in part.variables:
                    if evaluated and part_inversion:
                        return True
                    continue
                if not evaluated:
                    result.append(part_inversion)
                elif part_inversion:
                    return True
                else:
                    continue
            elif is_leaf(part) and self.base(part[0]) == symbol:
                result.append(part)
            else:
                field = part[0]
                field = self.base(field)
                if (field in context
                        and (eval_leaf(part, context, operator.or_)
                            or constrained_leaf(part, operator.or_))):
                    return True
                elif (field in context
                        and not eval_leaf(part, context, operator.or_)):
                    result.append(False)

        result = [e for e in result if e is not False]
        if result == []:
            return False
        else:
            return simplify(['OR'] + result)


# Test stuffs
def test_simple_inversion():
    domain = [['x', '=', 3]]
    assert domain_inversion(domain, 'x') == [['x', '=', 3]]

    domain = []
    assert domain_inversion(domain, 'x') is True
    assert domain_inversion(domain, 'y') is True
    assert domain_inversion(domain, 'x', {'x': 5}) is True
    assert domain_inversion(domain, 'z', {'x': 7}) is True

    domain = [['x.id', '>', 5]]
    assert domain_inversion(domain, 'x') == [['x.id', '>', 5]]


def test_and_inversion():
    domain = [['x', '=', 3], ['y', '>', 5]]
    assert domain_inversion(domain, 'x') == [['x', '=', 3]]
    assert domain_inversion(domain, 'x', {'y': 4}) is False
    assert domain_inversion(domain, 'x', {'y': 6}) == [['x', '=', 3]]

    domain = [['x', '=', 3], ['y', '=', 5]]
    assert domain_inversion(domain, 'z') is True
    assert domain_inversion(domain, 'z', {'x': 2, 'y': 7}) is True
    assert domain_inversion(domain, 'x', {'y': None}) == [['x', '=', 3]]

    domain = [['x.id', '>', 5], ['y', '<', 3]]
    assert domain_inversion(domain, 'y') == [['y', '<', 3]]
    assert domain_inversion(domain, 'y', {'x': 3}) == [['y', '<', 3]]
    assert domain_inversion(domain, 'x') == [['x.id', '>', 5]]


def test_or_inversion():
    domain = ['OR', ['x', '=', 3], ['y', '>', 5], ['z', '=', 'abc']]
    assert domain_inversion(domain, 'x') == [['x', '=', 3]]
    assert domain_inversion(domain, 'x', {'y': 4}) == [['x', '=', 3]]
    assert domain_inversion(domain, 'x', {'y': 4, 'z': 'ab'}) ==\
        [['x', '=', 3]]
    assert domain_inversion(domain, 'x', {'y': 7}) is True
    assert domain_inversion(domain, 'x', {'y': 7, 'z': 'b'}) is True
    assert domain_inversion(domain, 'x', {'z': 'abc'}) is True
    assert domain_inversion(domain, 'x', {'y': 4, 'z': 'abc'}) is True

    domain = ['OR', ['x', '=', 3], ['y', '=', 5]]
    assert domain_inversion(domain, 'x', {'y': None}) == [['x', '=', 3]]

    domain = ['OR', ['x', '=', 3], ['y', '>', 5]]
    assert domain_inversion(domain, 'z') is True

    domain = ['OR', ['x.id', '>', 5], ['y', '<', 3]]
    assert domain_inversion(domain, 'y') == [['y', '<', 3]]
    assert domain_inversion(domain, 'y', {'z': 4}) == [['y', '<', 3]]
    assert domain_inversion(domain, 'y', {'x': 3}) is True

    domain = ['OR', ['length', '>', 5], ['language.code', '=', 'de_DE']]
    assert domain_inversion(domain, 'length', {'length': 0, 'name': 'n'}) ==\
        [['length', '>', 5]]


def test_orand_inversion():
    domain = ['OR', [['x', '=', 3], ['y', '>', 5], ['z', '=', 'abc']],
        [['x', '=', 4]], [['y', '>', 6]]]
    assert domain_inversion(domain, 'x') is True
    assert domain_inversion(domain, 'x', {'y': 4}) == [[['x', '=', 4]]]
    assert domain_inversion(domain, 'x', {'z': 'abc', 'y': 7}) is True
    assert domain_inversion(domain, 'x', {'y': 7}) is True
    assert domain_inversion(domain, 'x', {'z': 'ab'}) is True


def test_andor_inversion():
    domain = [['OR', ['x', '=', 4], ['y', '>', 6]], ['z', '=', 3]]
    assert domain_inversion(domain, 'z') == [['z', '=', 3]]
    assert domain_inversion(domain, 'z', {'x': 5}) == [['z', '=', 3]]
    assert domain_inversion(domain, 'z', {'x': 5, 'y': 5}) is False
    assert domain_inversion(domain, 'z', {'x': 5, 'y': 7}) == [['z', '=', 3]]


def test_andand_inversion():
    domain = [[['x', '=', 4], ['y', '>', 6]], ['z', '=', 3]]
    assert domain_inversion(domain, 'z') == [['z', '=', 3]]
    assert domain_inversion(domain, 'z', {'x': 5}) == [['z', '=', 3]]
    assert domain_inversion(domain, 'z', {'y': 5}) is False
    assert domain_inversion(domain, 'z', {'x': 4, 'y': 7}) == [['z', '=', 3]]

    domain = [[['x', '=', 4], ['y', '>', 6], ['z', '=', 2]], [['w', '=', 2]]]
    assert domain_inversion(domain, 'z', {'x': 4}) == [['z', '=', 2]]


def test_oror_inversion():
    domain = ['OR', ['OR', ['x', '=', 3], ['y', '>', 5]],
        ['OR', ['x', '=', 2], ['z', '=', 'abc']],
        ['OR', ['y', '=', 8], ['z', '=', 'y']]]
    assert domain_inversion(domain, 'x') is True
    assert domain_inversion(domain, 'x', {'y': 4}) is True
    assert domain_inversion(domain, 'x', {'z': 'ab'}) is True
    assert domain_inversion(domain, 'x', {'y': 7}) is True
    assert domain_inversion(domain, 'x', {'z': 'abc'}) is True
    assert domain_inversion(domain, 'x', {'z': 'y'}) is True
    assert domain_inversion(domain, 'x', {'y': 8}) is True
    assert domain_inversion(domain, 'x', {'y': 8, 'z': 'b'}) is True
    assert domain_inversion(domain, 'x', {'y': 4, 'z': 'y'}) is True
    assert domain_inversion(domain, 'x', {'y': 7, 'z': 'abc'}) is True
    assert domain_inversion(domain, 'x', {'y': 4, 'z': 'b'}) == \
        ['OR', [['x', '=', 3]], [['x', '=', 2]]]


def test_parse():
    domain = parse([['x', '=', 5]])
    assert domain.variables == set('x')
    domain = parse(['OR', ['x', '=', 4], ['y', '>', 6]])
    assert domain.variables == set('xy')
    domain = parse([['OR', ['x', '=', 4], ['y', '>', 6]], ['z', '=', 3]])
    assert domain.variables == set('xyz')
    domain = parse([[['x', '=', 4], ['y', '>', 6]], ['z', '=', 3]])
    assert domain.variables == set('xyz')


def test_simplify():
    domain = [['x', '=', 3]]
    assert simplify(domain) == [['x', '=', 3]]
    domain = [[['x', '=', 3]]]
    assert simplify(domain) == [['x', '=', 3]]
    domain = ['OR', ['x', '=', 3]]
    assert simplify(domain) == [['x', '=', 3]]
    domain = ['OR', [['x', '=', 3]], [['y', '=', 5]]]
    assert simplify(domain) == ['OR', [['x', '=', 3]], [['y', '=', 5]]]
    domain = ['OR', ['x', '=', 3], ['AND', ['y', '=', 5]]]
    assert simplify(domain) == ['OR', ['x', '=', 3], [['y', '=', 5]]]
    domain = ['AND']
    assert simplify(domain) == []
    domain = ['OR']
    assert simplify(domain) == []


def test_merge():
    domain = [['x', '=', 6], ['y', '=', 7]]
    assert merge(domain) == ['AND', ['x', '=', 6], ['y', '=', 7]]
    domain = ['AND', ['x', '=', 6], ['y', '=', 7]]
    assert merge(domain) == ['AND', ['x', '=', 6], ['y', '=', 7]]
    domain = [['z', '=', 8], ['AND', ['x', '=', 6], ['y', '=', 7]]]
    assert merge(domain) == ['AND', ['z', '=', 8], ['x', '=', 6],
        ['y', '=', 7]]
    domain = ['OR', ['x', '=', 1], ['y', '=', 2], ['z', '=', 3]]
    assert merge(domain) == ['OR', ['x', '=', 1], ['y', '=', 2],
        ['z', '=', 3]]
    domain = ['OR', ['x', '=', 1], ['OR', ['y', '=', 2], ['z', '=', 3]]]
    assert merge(domain) == ['OR', ['x', '=', 1], ['y', '=', 2],
        ['z', '=', 3]]
    domain = ['OR', ['x', '=', 1], ['AND', ['y', '=', 2], ['z', '=', 3]]]
    assert merge(domain) == ['OR', ['x', '=', 1], ['AND', ['y', '=', 2],
        ['z', '=', 3]]]
    domain = [['z', '=', 8], ['OR', ['x', '=', 6], ['y', '=', 7]]]
    assert merge(domain) == ['AND', ['z', '=', 8], ['OR', ['x', '=', 6],
        ['y', '=', 7]]]
    domain = ['AND', ['OR', ['a', '=', 1], ['b', '=', 2]],
        ['OR', ['c', '=', 3], ['AND', ['d', '=', 4], ['d2', '=', 6]]],
        ['AND', ['d', '=', 5], ['e', '=', 6]], ['f', '=', 7]]
    assert merge(domain) == ['AND', ['OR', ['a', '=', 1], ['b', '=', 2]],
        ['OR', ['c', '=', 3], ['AND', ['d', '=', 4], ['d2', '=', 6]]],
        ['d', '=', 5], ['e', '=', 6], ['f', '=', 7]]


def test_concat():
    domain1 = [['a', '=', 1]]
    domain2 = [['b', '=', 2]]
    assert concat(domain1, domain2) == ['AND', ['a', '=', 1], ['b', '=', 2]]
    assert concat([], domain1) == domain1
    assert concat(domain2, []) == domain2
    assert concat([], []) == []
    assert concat(domain1, domain2, domoperator='OR') == [
        'OR', [['a', '=', 1]], [['b', '=', 2]]]


def test_unique_value():
    domain = [['a', '=', 1]]
    assert unique_value(domain) == (True, '=', 1)
    domain = [['a', '!=', 1]]
    assert unique_value(domain)[0] is False
    domain = [['a', '=', 1], ['a', '=', 2]]
    assert unique_value(domain)[0] is False
    domain = [['a.b', '=', 1]]
    assert unique_value(domain)[0] is False


def test_evaldomain():
    domain = [['x', '>', 5]]
    assert eval_domain(domain, {'x': 6})
    assert not eval_domain(domain, {'x': 4})

    domain = [['x', '>', None]]
    assert eval_domain(domain, {'x': datetime.date.today()})
    assert eval_domain(domain, {'x': datetime.datetime.now()})

    domain = [['x', '<', datetime.date.today()]]
    assert eval_domain(domain, {'x': None})
    domain = [['x', '<', datetime.datetime.now()]]
    assert eval_domain(domain, {'x': None})

    domain = [['x', 'in', [3, 5]]]
    assert eval_domain(domain, {'x': 3})
    assert not eval_domain(domain, {'x': 4})
    assert eval_domain(domain, {'x': [3]})
    assert eval_domain(domain, {'x': [3, 4]})
    assert not eval_domain(domain, {'x': [1, 2]})

    domain = [['x', 'not in', [3, 5]]]
    assert not eval_domain(domain, {'x': 3})
    assert eval_domain(domain, {'x': 4})
    assert not eval_domain(domain, {'x': [3]})
    assert not eval_domain(domain, {'x': [3, 4]})
    assert eval_domain(domain, {'x': [1, 2]})

    domain = [['x', 'like', 'abc']]
    assert eval_domain(domain, {'x': 'abc'})
    assert not eval_domain(domain, {'x': ''})
    assert not eval_domain(domain, {'x': 'xyz'})
    assert not eval_domain(domain, {'x': 'abcd'})

    domain = [['x', 'not like', 'abc']]
    assert eval_domain(domain, {'x': 'xyz'})
    assert eval_domain(domain, {'x': 'ABC'})
    assert not eval_domain(domain, {'x': 'abc'})

    domain = [['x', 'not ilike', 'abc']]
    assert eval_domain(domain, {'x': 'xyz'})
    assert not eval_domain(domain, {'x': 'ABC'})
    assert not eval_domain(domain, {'x': 'abc'})

    domain = [['x', 'like', 'a%']]
    assert eval_domain(domain, {'x': 'a'})
    assert eval_domain(domain, {'x': 'abcde'})
    assert not eval_domain(domain, {'x': ''})
    assert not eval_domain(domain, {'x': 'ABCDE'})
    assert not eval_domain(domain, {'x': 'xyz'})

    domain = [['x', 'ilike', 'a%']]
    assert eval_domain(domain, {'x': 'a'})
    assert eval_domain(domain, {'x': 'A'})
    assert not eval_domain(domain, {'x': ''})
    assert not eval_domain(domain, {'x': 'xyz'})

    domain = [['x', 'like', 'a_']]
    assert eval_domain(domain, {'x': 'ab'})
    assert not eval_domain(domain, {'x': 'a'})
    assert not eval_domain(domain, {'x': 'abc'})

    domain = [['x', 'like', 'a\\%b']]
    assert eval_domain(domain, {'x': 'a%b'})
    assert not eval_domain(domain, {'x': 'ab'})
    assert not eval_domain(domain, {'x': 'a123b'})

    domain = [['x', 'like', '\\%b']]
    assert eval_domain(domain, {'x': '%b'})
    assert not eval_domain(domain, {'x': 'b'})
    assert not eval_domain(domain, {'x': '123b'})

    domain = [['x', 'like', 'a\\_c']]
    assert eval_domain(domain, {'x': 'a_c'})
    assert not eval_domain(domain, {'x': 'abc'})
    assert not eval_domain(domain, {'x': 'ac'})

    domain = [['x', 'like', 'a\\\\_c']]
    assert eval_domain(domain, {'x': 'a\\bc'})
    assert not eval_domain(domain, {'x': 'abc'})

    domain = ['OR', ['x', '>', 10], ['x', '<', 0]]
    assert eval_domain(domain, {'x': 11})
    assert eval_domain(domain, {'x': -4})
    assert not eval_domain(domain, {'x': 5})

    domain = ['OR', ['x', '>', 0], ['x', '=', None]]
    assert eval_domain(domain, {'x': 1})
    assert eval_domain(domain, {'x': None})
    assert not eval_domain(domain, {'x': -1})
    assert not eval_domain(domain, {'x': 0})

    domain = [['x', '>', 0], ['OR', ['x', '=', 3], ['x', '=', 2]]]
    assert not eval_domain(domain, {'x': 1})
    assert eval_domain(domain, {'x': 3})
    assert eval_domain(domain, {'x': 2})
    assert not eval_domain(domain, {'x': 4})
    assert not eval_domain(domain, {'x': 5})
    assert not eval_domain(domain, {'x': 6})

    domain = ['OR', ['x', '=', 4], [['x', '>', 6], ['x', '<', 10]]]
    assert eval_domain(domain, {'x': 4})
    assert eval_domain(domain, {'x': 7})
    assert not eval_domain(domain, {'x': 3})
    assert not eval_domain(domain, {'x': 5})
    assert not eval_domain(domain, {'x': 11})

    domain = [['x', '=', 'test,1']]
    assert eval_domain(domain, {'x': ('test', 1)})
    assert eval_domain(domain, {'x': 'test,1'})
    assert not eval_domain(domain, {'x': ('test', 2)})
    assert not eval_domain(domain, {'x': 'test,2'})

    domain = [['x', '=', ('test', 1)]]
    assert eval_domain(domain, {'x': ('test', 1)})
    assert eval_domain(domain, {'x': 'test,1'})
    assert not eval_domain(domain, {'x': ('test', 2)})
    assert not eval_domain(domain, {'x': 'test,2'})

    domain = [['x', '=', 1]]
    assert eval_domain(domain, {'x': [1, 2]})
    assert not eval_domain(domain, {'x': [2]})

    domain = [['x', '=', None]]
    assert eval_domain(domain, {'x': []})

    domain = [['x', '=', ['foo', 1]]]
    assert eval_domain(domain, {'x': 'foo,1'})
    assert eval_domain(domain, {'x': ('foo', 1)})
    assert eval_domain(domain, {'x': ['foo', 1]})
    domain = [['x', '=', ('foo', 1)]]
    assert eval_domain(domain, {'x': 'foo,1'})
    assert eval_domain(domain, {'x': ('foo', 1)})
    assert eval_domain(domain, {'x': ['foo', 1]})

    domain = [['x', '=', 'foo,1']]
    assert eval_domain(domain, {'x': ['foo', 1]})
    assert eval_domain(domain, {'x': ('foo', 1)})


def test_localize():
    domain = [['x', '=', 5]]
    assert localize_domain(domain) == [['x', '=', 5]]

    domain = [['x', '=', 5], ['x.code', '=', 7]]
    assert localize_domain(domain, 'x') == [['id', '=', 5], ['code', '=', 7]]

    domain = [['x', 'ilike', 'foo%'], ['x.code', '=', 'test']]
    assert localize_domain(domain, 'x') == \
        [['rec_name', 'ilike', 'foo%'], ['code', '=', 'test']]

    domain = ['OR', ['AND', ['x', '>', 7], ['x', '<', 15]], ['x.code', '=', 8]]
    assert localize_domain(domain, 'x') == \
        ['OR', ['AND', ['id', '>', 7], ['id', '<', 15]], ['code', '=', 8]]

    domain = [['x', 'child_of', [1]]]
    assert localize_domain(domain, 'x') == [['x', 'child_of', [1]]]

    domain = [['x', 'child_of', [1], 'y']]
    assert localize_domain(domain, 'x') == [['y', 'child_of', [1]]]

    domain = [['x.y', 'child_of', [1], 'parent']]
    assert localize_domain(domain, 'x') == [['y', 'child_of', [1], 'parent']]

    domain = [['x.y.z', 'child_of', [1], 'parent', 'model']]
    assert localize_domain(domain, 'x') == \
        [['y.z', 'child_of', [1], 'parent', 'model']]

    domain = [['x.id', '=', 1, 'y']]
    assert localize_domain(domain, 'x', False) == [['id', '=', 1, 'y']]
    assert localize_domain(domain, 'x', True) == [['id', '=', 1]]

    domain = [['a.b.c', '=', 1, 'y', 'z']]
    assert localize_domain(domain, 'x', False) == [['b.c', '=', 1, 'y', 'z']]
    assert localize_domain(domain, 'x', True) == [['b.c', '=', 1, 'z']]


def test_prepare_reference_domain():
    domain = [['x', 'like', 'A%']]
    assert prepare_reference_domain(domain, 'x') == [['x', 'like', 'A%']]

    domain = [['x.y', 'like', 'A%', 'model']]
    assert prepare_reference_domain(domain, 'x') == [['y', 'like', 'A%']]

    domain = [['x.y', 'child_of', [1], 'model', 'parent']]
    assert prepare_reference_domain(domain, 'x') == \
        [['y', 'child_of', [1], 'parent']]


def test_extract_models():
    domain = [['x', 'like', 'A%']]
    assert extract_reference_models(domain, 'x') == set()
    assert extract_reference_models(domain, 'y') == set()

    domain = [['x', 'like', 'A%', 'model']]
    assert extract_reference_models(domain, 'x') == {'model'}
    assert extract_reference_models(domain, 'y') == set()

    domain = ['OR',
        ['x.y', 'like', 'A%', 'model_A'],
        ['x.z', 'like', 'B%', 'model_B']]
    assert extract_reference_models(domain, 'x') == {'model_A', 'model_B'}
    assert extract_reference_models(domain, 'y') == set()


if __name__ == '__main__':
    test_simple_inversion()
    test_and_inversion()
    test_or_inversion()
    test_orand_inversion()
    test_andor_inversion()
    test_andand_inversion()
    test_oror_inversion()
    test_parse()
    test_simplify()
    test_evaldomain()
    test_localize()
    test_prepare_reference_domain()
    test_extract_models()

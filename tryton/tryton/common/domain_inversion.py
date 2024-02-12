# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
import operator
import re
from collections import defaultdict
from functools import partial, reduce


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
    if (operand not in {'=', '!='}
            and (context_field is None or value is None)
            and not (operand in {'in', 'not in'}
                and context_field is None
                and (isinstance(value, (list, tuple)) and None in value))):
        return
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
        return boolop(bool(eval_domain(domain[0], context)),
            bool(eval_domain(domain[1:], context, boolop)))


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


def _sort_key(domain):
    if not domain:
        return (0, tuple())
    elif is_leaf(domain):
        return (1, tuple((type(x).__name__, x) for x in domain))
    elif domain in ['AND', 'OR']:
        return (0, domain)
    else:
        content = tuple(_sort_key(e) for e in domain)
        nestedness = max(k[0] for k in content)
        return (nestedness + 1, content)


def sort(domain):
    "Sort a domain"
    if not domain:
        return domain
    elif is_leaf(domain):
        return domain
    elif domain in ['AND', 'OR']:
        return domain
    else:
        return sorted((sort(e) for e in domain), key=_sort_key)


def bool_operator(domain):
    "Returns the boolean operator used by a domain"
    bool_op = 'AND'
    if domain and domain[0] in ['AND', 'OR']:
        bool_op = domain[0]
    return bool_op


def simplify_nested(domain):
    """Simplify extra domain markers"""
    if not domain:
        return []
    elif is_leaf(domain):
        return [domain]
    elif domain in ['OR', 'AND']:
        return [domain]
    elif isinstance(domain, list) and len(domain) == 1:
        return simplify_nested(domain[0])
    else:
        simplified = []
        domain_op = bool_operator(domain)
        for branch in domain:
            simplified_branch = simplify_nested(branch)
            if (bool_operator(simplified_branch) == domain_op
                    or len(simplified_branch) == 1):
                if (simplified
                        and simplified_branch
                        and simplified_branch[0] in ['AND', 'OR']):
                    simplified.extend(simplified_branch[1:])
                else:
                    simplified.extend(simplified_branch)
            else:
                simplified.append(simplified_branch)
        return simplified


def simplify_duplicate(domain):
    """Remove duplicates subdomain from domain"""
    dedup_branches = []
    bool_op = None
    if domain[0] in ['AND', 'OR']:
        bool_op, *domain = domain
    for branch in domain:
        simplified_branch = simplify(branch)
        if not simplified_branch:
            if bool_op == 'OR':
                return []
            else:
                continue
        elif simplified_branch not in dedup_branches:
            dedup_branches.append(simplified_branch)
    if bool_op and len(dedup_branches) > 1:
        dedup_branches.insert(0, bool_op)
    return dedup_branches


def simplify_AND(domain):
    """Remove useless ANDs"""
    if is_leaf(domain):
        return domain
    elif domain == 'OR':
        return domain
    else:
        return [simplify_AND(e) for e in domain if e != 'AND']


def simplify(domain):
    """Remove duplicate expressions and useless OR/AND"""
    if is_leaf(domain):
        return [domain]
    elif not domain:
        return domain
    else:
        return simplify_nested(simplify_duplicate(domain))


def canonicalize(domain):
    """Returns the canonical version of a domain.

    The canonical version of a domain is one where the domain is both
    simplified and sorted
    """
    return simplify_AND(sort(simplify(domain)))


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


def unique_value(domain, single_value=True):
    "Return if unique, the field and the value"
    if (isinstance(domain, list)
            and len(domain) == 1):
        name, operator, value, *model = domain[0]
        count = name.count('.')
        if (
                (operator == '='
                    or (single_value
                        and operator == 'in' and len(value) == 1))
                and (not count
                    or (count == 1 and model and name.endswith('.id')))):
            value = value if operator == '=' and single_value else value[0]
            if model and name.endswith('.id'):
                model = model[0]
                value = [model, value]
            return True, name, value
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

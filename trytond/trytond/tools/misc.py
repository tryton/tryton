# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"""
Miscelleanous tools used by tryton
"""
import importlib
import io
import os
import re
import sys
import types
import unicodedata
import warnings
from array import array
from functools import wraps
from itertools import islice

from sql import Literal
from sql.conditionals import Case
from sql.operators import Or

from trytond.const import OPERATORS


def file_open(name, mode="r", subdir='modules', encoding=None):
    """Open a file from the root dir, using a subdir folder."""
    from trytond.modules import EGG_MODULES
    root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def secure_join(root, *paths):
        "Join paths and ensure it still below root"
        path = os.path.join(root, *paths)
        path = os.path.normpath(path)
        if not path.startswith(os.path.join(root, '')):
            raise IOError("Permission denied: %s" % name)
        return path

    egg_name = False
    if subdir == 'modules':
        module_name = name.split(os.sep)[0]
        if module_name in EGG_MODULES:
            epoint = EGG_MODULES[module_name]
            mod_path = os.path.join(epoint.dist.location,
                    *epoint.module_name.split('.')[:-1])
            mod_path = os.path.abspath(mod_path)
            egg_name = secure_join(mod_path, name)
            if not os.path.isfile(egg_name):
                # Find module in path
                for path in sys.path:
                    mod_path = os.path.join(path,
                            *epoint.module_name.split('.')[:-1])
                    mod_path = os.path.abspath(mod_path)
                    egg_name = secure_join(mod_path, name)
                    if os.path.isfile(egg_name):
                        break
                if not os.path.isfile(egg_name):
                    # When testing modules from setuptools location is the
                    # module directory
                    egg_name = secure_join(
                        os.path.dirname(epoint.dist.location), name)

    if subdir:
        if (subdir == 'modules'
                and (name.startswith('ir' + os.sep)
                    or name.startswith('res' + os.sep)
                    or name.startswith('tests' + os.sep))):
            name = secure_join(root_path, name)
        else:
            name = secure_join(root_path, subdir, name)
    else:
        name = secure_join(root_path, name)

    for i in (name, egg_name):
        if i and os.path.isfile(i):
            return io.open(i, mode, encoding=encoding)

    raise IOError('File not found : %s ' % name)


def get_smtp_server():
    """
    Instanciate, configure and return a SMTP or SMTP_SSL instance from
    smtplib.
    :return: A SMTP instance. The quit() method must be call when all
    the calls to sendmail() have been made.
    """
    from trytond.sendmail import get_smtp_server
    warnings.warn(
        'get_smtp_server is deprecated use trytond.sendmail',
        DeprecationWarning)
    return get_smtp_server()


def reduce_ids(field, ids):
    '''
    Return a small SQL expression for the list of ids and the sql column
    '''
    ids = list(ids)
    if not ids:
        return Literal(False)
    assert all(x.is_integer() for x in ids if isinstance(x, float)), \
        'ids must be integer'
    ids = list(map(int, ids))
    ids.sort()
    prev = ids.pop(0)
    continue_list = [prev, prev]
    discontinue_list = array('l')
    sql = Or()
    for i in ids:
        if i == prev:
            continue
        if i != prev + 1:
            if continue_list[-1] - continue_list[0] < 5:
                discontinue_list.extend([continue_list[0] + x for x in
                    range(continue_list[-1] - continue_list[0] + 1)])
            else:
                sql.append((field >= continue_list[0])
                    & (field <= continue_list[-1]))
            continue_list = []
        continue_list.append(i)
        prev = i
    if continue_list[-1] - continue_list[0] < 5:
        discontinue_list.extend([continue_list[0] + x for x in
            range(continue_list[-1] - continue_list[0] + 1)])
    else:
        sql.append((field >= continue_list[0]) & (field <= continue_list[-1]))
    if discontinue_list:
        sql.append(field.in_(discontinue_list))
    return sql


def reduce_domain(domain):
    '''
    Reduce domain
    '''
    if not domain:
        return []
    operator = 'AND'
    if isinstance(domain[0], str):
        operator = domain[0]
        domain = domain[1:]
    result = [operator]
    for arg in domain:
        if (isinstance(arg, tuple)
                or (isinstance(arg, list)
                    and len(arg) > 2
                    and arg[1] in OPERATORS)):
            # clause
            result.append(arg)
        elif isinstance(arg, list) and arg:
            # sub-domain
            sub_domain = reduce_domain(arg)
            sub_operator = sub_domain[0]
            if sub_operator == operator:
                result.extend(sub_domain[1:])
            else:
                result.append(sub_domain)
        else:
            result.append(arg)
    return result


def grouped_slice(records, count=None):
    'Grouped slice'
    from trytond.transaction import Transaction
    if count is None:
        count = Transaction().database.IN_MAX
    count = max(1, count)
    for i in range(0, len(records), count):
        yield islice(records, i, i + count)


def is_instance_method(cls, method):
    for klass in cls.__mro__:
        type_ = klass.__dict__.get(method)
        if type_ is not None:
            return isinstance(type_, types.FunctionType)


def resolve(name):
    "Resolve a dotted name to a global object."
    name = name.split('.')
    used = name.pop(0)
    found = importlib.import_module(used)
    for n in name:
        used = used + '.' + n
        try:
            found = getattr(found, n)
        except AttributeError:
            found = importlib.import_module(used)
    return found


def strip_wildcard(string, wildcard='%', escape='\\'):
    "Strip starting and ending wildcard from string"
    string = lstrip_wildcard(string, wildcard)
    return rstrip_wildcard(string, wildcard, escape)


def lstrip_wildcard(string, wildcard='%'):
    "Strip starting wildcard from string"
    if not string:
        return string
    return string.lstrip(wildcard)


def rstrip_wildcard(string, wildcard='%', escape='\\'):
    "Strip ending wildcard from string"
    if not string:
        return string
    new_string = string.rstrip(wildcard)
    if new_string[-1] == escape:
        return string
    return new_string


def escape_wildcard(string, wildcards='%_', escape='\\'):
    for wildcard in escape + wildcards:
        string = string.replace(wildcard, escape + wildcard)
    return string


def unescape_wildcard(string, wildcards='%_', escape='\\'):
    for wildcard in wildcards + escape:
        string = string.replace(escape + wildcard, wildcard)
    return string


def is_full_text(value, escape='\\'):
    escaped = value.strip('%')
    escaped = escaped.replace(escape + '%', '').replace(escape + '_', '')
    if '%' in escaped or '_' in escaped:
        return False
    return value.startswith('%') == value.endswith('%')


_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')


def slugify(value, hyphenate='-'):
    if not isinstance(value, str):
        value = str(value)
    value = unicodedata.normalize('NFKD', value)
    value = str(_slugify_strip_re.sub('', value).strip())
    return _slugify_hyphenate_re.sub(hyphenate, value)


def sortable_values(func):
    "Decorator that makes list of couple values sortable"
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = list(func(*args, **kwargs))
        for i, (name, value) in enumerate(list(result)):
            result[i] = (name, value is None, value)
        return result
    return wrapper


def sql_pairing(x, y):
    """Return SQL expression to pair x and y
    Pairing function from http://szudzik.com/ElegantPairing.pdf"""
    return Case(
        (x < y, (y * y) + x),
        else_=(x * x) + x + y)


def firstline(text):
    "Returns first non-empty line"
    try:
        return next((x for x in text.splitlines() if x.strip()))
    except StopIteration:
        return ''

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
import types
import unicodedata
import warnings
from array import array
from collections.abc import Iterable, Sized
from functools import wraps
from itertools import chain, islice, tee, zip_longest

from sql import Literal
from sql.conditionals import Case
from sql.operators import Or

from trytond.const import MODULES_GROUP, OPERATORS

try:
    from backports.entry_points_selectable import entry_points as _entry_points
except ImportError:
    from importlib.metadata import entry_points as _entry_points
_ENTRY_POINTS = None


def entry_points():
    global _ENTRY_POINTS
    if _ENTRY_POINTS is None:
        _ENTRY_POINTS = _entry_points()
    return _ENTRY_POINTS


def import_module(name):
    try:
        ep, = entry_points().select(group=MODULES_GROUP, name=name)
    except ValueError:
        return importlib.import_module(f'{MODULES_GROUP}.{name}')
    return ep.load()


def file_open(name, mode="r", subdir='modules', encoding=None):
    "Open a file from the root directory, using subdir folder"
    path = find_path(name, subdir, _test=None)
    return io.open(path, mode, encoding=encoding)


def find_path(name, subdir='modules', _test=os.path.isfile):
    "Return path from the root directory, using subdir folder"
    root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def secure_join(root, *paths):
        "Join paths and ensure it still below root"
        path = os.path.join(root, *paths)
        path = os.path.normpath(path)
        if not path.startswith(os.path.join(root, '')):
            raise IOError("Permission denied: %s" % name)
        return path

    if subdir:
        if subdir == 'modules':
            try:
                module_name, module_path = name.split(os.sep, 1)
            except ValueError:
                module_name, module_path = name, ''
            if module_name in {'ir', 'res', 'tests'}:
                path = secure_join(root_path, module_name, module_path)
            else:
                try:
                    module = import_module(module_name)
                except ModuleNotFoundError:
                    path = secure_join(root_path, subdir, name)
                else:
                    path = os.path.dirname(module.__file__)
                    if module_path:
                        path = secure_join(path, module_path)
        else:
            path = secure_join(root_path, subdir, name)
    else:
        path = secure_join(root_path, name)

    if not _test or _test(path):
        return path
    else:
        raise FileNotFoundError("No such file or directory: %r" % name)


def find_dir(name, subdir='modules'):
    "Return directory from the root directory, using subdir folder"
    return find_path(name, subdir=subdir, _test=os.path.isdir)


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
    if __debug__:
        def strict_int(value):
            assert not isinstance(value, float) or value.is_integer(), \
                "ids must be integer"
            return int(value)
    else:
        strict_int = int
    ids = list(map(strict_int, ids))
    if not ids:
        return Literal(False)
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
    if not isinstance(records, Sized):
        records = list(records)
    for i in range(0, len(records), count):
        yield islice(records, i, i + count)


def pairwise_longest(iterable):
    a, b = tee(iterable)
    next(b, None)
    return zip_longest(a, b)


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
    if string and string.startswith(wildcard):
        string = string[1:]
    return string


def rstrip_wildcard(string, wildcard='%', escape='\\'):
    "Strip ending wildcard from string"
    if (string
            and string.endswith(wildcard)
            and not string.endswith(escape + wildcard)):
        string = string[:-1]
    return string


def escape_wildcard(string, wildcards='%_', escape='\\'):
    for wildcard in escape + wildcards:
        string = string.replace(wildcard, escape + wildcard)
    return string


def unescape_wildcard(string, wildcards='%_', escape='\\'):
    for wildcard in wildcards + escape:
        string = string.replace(escape + wildcard, wildcard)
    return string


def is_full_text(value, escape='\\'):
    escaped = strip_wildcard(value, escape=escape)
    escaped = escaped.replace(escape + '%', '').replace(escape + '_', '')
    if '%' in escaped or '_' in escaped:
        return False
    return value.startswith('%') == value.endswith('%')


def likify(string, escape='\\'):
    if not string:
        return '%'
    escaped = string.replace(escape + '%', '').replace(escape + '_', '')
    if '%' in escaped or '_' in escaped:
        return string
    else:
        return '%' + string + '%'


_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')


def slugify(value, hyphenate='-'):
    if not isinstance(value, str):
        value = str(value)
    value = unicodedata.normalize('NFKD', value)
    value = str(_slugify_strip_re.sub('', value).strip())
    return _slugify_hyphenate_re.sub(hyphenate, value)


def sortable_values(func):
    "Decorator that makes list of values sortable"
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = list(func(*args, **kwargs))
        for i, value in enumerate(list(result)):
            if not isinstance(value, Iterable):
                value = [value]
            result[i] = tuple(chain((k is None, k) for k in value))
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


def remove_forbidden_chars(value):
    from trytond.model.fields import Char
    if value is None:
        return value
    for c in Char.forbidden_chars:
        if c in value:
            value = value.replace(c, ' ')
    return value.strip()

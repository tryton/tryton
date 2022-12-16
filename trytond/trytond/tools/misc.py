# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"""
Miscelleanous tools used by tryton
"""
import os
import sys
from array import array
from itertools import islice
import types
import io
import warnings
import importlib

from sql import Literal
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
    from ..sendmail import get_smtp_server
    warnings.warn(
        'get_smtp_server is deprecated use trytond.sendmail',
        DeprecationWarning)
    return get_smtp_server()


def memoize(maxsize):
    """
    Decorator to 'memoize' a function - caching its results with a
    near LRU implementation.

    The cache keeps a list of keys logicaly separated in 4 segment :

    segment 1 | ...        | segment4
    [k,k,k,k,k,k,k, .. ,k,k,k,k,k,k,k]

    For each segment there is a pointer that loops on it.  When a key
    is accessed from the cache it is promoted to the first segment (at
    the pointer place of segment one), the key under the pointer is
    moved to the next segment, the pointer is then incremented and so
    on. A key that is removed from the last segment is removed from
    the cache.

    :param: maxsize the size of the cache (must be greater than or
    equal to 4)
    """
    assert maxsize >= 4, "Memoize cannot work if maxsize is less than 4"

    def wrap(fct):
        cache = {}
        keys = [None for i in range(maxsize)]
        seg_size = maxsize // 4

        pointers = [i * seg_size for i in range(4)]
        max_pointers = [(i + 1) * seg_size for i in range(3)] + [maxsize]

        def wrapper(*args):
            key = repr(args)
            res = cache.get(key)
            if res:
                pos, res = res
                keys[pos] = None
            else:
                res = fct(*args)

            value = res
            for segment, pointer in enumerate(pointers):
                newkey = keys[pointer]
                keys[pointer] = key
                cache[key] = (pointer, value)

                pointers[segment] = pointer + 1
                if pointers[segment] == max_pointers[segment]:
                    pointers[segment] = segment * seg_size

                if newkey is None:
                    break
                segment, value = cache.pop(newkey)
                key = newkey

            return res

        wrapper.__doc__ = fct.__doc__
        wrapper.__name__ = fct.__name__

        return wrapper
    return wrap


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
        if (isinstance(arg, tuple) or
                (isinstance(arg, list) and
                    len(arg) > 2 and
                    arg[1] in OPERATORS)):
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

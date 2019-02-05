# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


def is_gevent_monkey_patched():
    try:
        from gevent import monkey
    except ImportError:
        return False
    else:
        return monkey.is_module_patched('__builtin__')

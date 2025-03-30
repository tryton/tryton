# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
from functools import partial

from proteus import Model, Wizard
from proteus import config as pconfig

from .test_tryton import backup_db_cache, drop_create, restore_db_cache

__all__ = ['activate_modules', 'set_user']


def _func_name(func):
    if isinstance(func, partial):
        return f'{func.func.__qualname__}(*{func.args}, **{func.keywords})'
    else:
        assert not hasattr(func, '__self__')
        return func.__qualname__


def activate_modules(modules, *setup):
    if isinstance(modules, str):
        modules = [modules]
    cache_name = '-'.join(sorted(modules))
    if setup_name := '|'.join(_func_name(f) for f in setup):
        cache_name += f'--{setup_name}'
    if restore_db_cache(cache_name):
        return _get_config()
    drop_create()

    cfg = _get_config()
    Module = Model.get('ir.module')
    records = Module.find([
            ('name', 'in', modules),
            ])
    assert len(records) == len(modules)
    Module.click(records, 'activate')
    Wizard('ir.module.activate_upgrade').execute('upgrade')

    for func in setup:
        func(config=cfg)

    backup_db_cache(cache_name)
    return cfg


def _get_config():
    return pconfig.set_trytond()


def set_user(user=1, config=None):
    if not config:
        config = pconfig.get_config()
    User = Model.get('res.user', config=config)
    config.user = int(user)
    config._context = User.get_preferences(True, {})


_dummy_test_case = unittest.TestCase()
_dummy_test_case.maxDiff = None


def __getattr__(name):
    return getattr(_dummy_test_case, name)

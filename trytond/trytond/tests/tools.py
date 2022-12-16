# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import config, Model, Wizard

from .test_tryton import restore_db_cache, backup_db_cache, drop_create


def activate_modules(modules):
    if isinstance(modules, basestring):
        modules = [modules]
    cache_name = '-'.join(modules)
    if restore_db_cache(cache_name):
        return _get_config()
    drop_create()

    cfg = _get_config()
    Module = Model.get('ir.module')
    modules = Module.find([
            ('name', 'in', modules),
            ])
    Module.click(modules, 'activate')
    Wizard('ir.module.activate_upgrade').execute('upgrade')

    backup_db_cache(cache_name)
    return cfg


def _get_config():
    cfg = config.set_trytond()
    cfg.pool.test = True
    return cfg

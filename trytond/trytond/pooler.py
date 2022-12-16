#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.sql_db import db_connect
import logging
from threading import RLock

_LOCK = RLock()
_DB = {}
_POOL = {}
_POOL_WIZARD = {}
_POOL_REPORT = {}

def get_db_and_pool(db_name, update_module=False, wizard=False, report=False,
        lang=None):

    restart = False
    _LOCK.acquire()
    try:
        if db_name in _DB:
            database = _DB[db_name]
        else:
            logging.getLogger('pooler').info(
                'Connecting to %s' % (db_name))
            database = db_connect(db_name)
            cursor = database.cursor()
            if not cursor.test():
                raise Exception('UserError', 'Invalid database!')
            cursor.close()
            _DB[db_name] = database

        if db_name in _POOL:
            pool = _POOL[db_name]
            pool_wizard = _POOL_WIZARD[db_name]
            pool_report = _POOL_REPORT[db_name]
        else:
            logging.getLogger('pooler').info(
                'Instanciate pooler for %s' % (db_name))
            from trytond.osv import OSVService
            pool = OSVService()
            _POOL[db_name] = pool

            from trytond.wizard import WizardService
            pool_wizard = WizardService()
            _POOL_WIZARD[db_name] = pool_wizard

            from trytond.report import ReportService
            pool_report = ReportService()
            _POOL_REPORT[db_name] = pool_report

            from trytond.modules import load_modules
            restart = not load_modules(database, pool, pool_wizard, pool_report,
                    update_module, lang)
    finally:
        _LOCK.release()
    if restart:
        restart_pool(db_name)

    if wizard:
        return database, pool_wizard
    if report:
        return database, pool_report
    return database, pool

def restart_pool(db_name, update_module=False, lang=None):
    _LOCK.acquire()
    try:
        del _POOL[db_name]
        del _POOL_WIZARD[db_name]
        del _POOL_REPORT[db_name]
    finally:
        _LOCK.release()
    return get_db_and_pool(db_name, update_module=update_module, lang=lang)

def close_db(db_name):
    _LOCK.acquire()
    try:
        if db_name in _DB:
            _DB[db_name].close()
            del _DB[db_name]
        if db_name in _POOL:
            del _POOL[db_name]
    finally:
        _LOCK.release()

def get_db_only(db_name, verbose=True):
    _LOCK.acquire()
    try:
        if db_name in _DB:
            database = _DB[db_name]
        else:
            if verbose:
                logging.getLogger('pooler').info(
                    'Connecting to %s' % (db_name))
            database = db_connect(db_name)
            _DB[db_name] = database
    finally:
        _LOCK.release()
    return database

def get_db(db_name):
    return get_db_and_pool(db_name)[0]

def get_db_list():
    return _POOL.keys()

def get_pool(db_name, update_module=False, lang=None):
    pool = get_db_and_pool(db_name, update_module, lang=lang)[1]
    return pool

def get_pool_wizard(db_name, update_module=False, lang=None):
    pool = get_db_and_pool(db_name, update_module, wizard=True,
            lang=lang)[1]
    return pool

def get_pool_report(db_name, update_module=False, lang=None):
    pool = get_db_and_pool(db_name, update_module, report=True, lang=lang)[1]
    return pool

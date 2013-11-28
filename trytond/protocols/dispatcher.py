# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import traceback
import logging
import time
import sys
try:
    import hashlib
except ImportError:
    hashlib = None
    import sha
import pydoc
from trytond.pool import Pool
from trytond import security
from trytond.backend import Database, DatabaseOperationalError
from trytond.config import CONFIG
from trytond.version import VERSION
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.exceptions import UserError, UserWarning, NotLogged, \
    ConcurrencyException
from trytond.rpc import RPC


def dispatch(host, port, protocol, database_name, user, session, object_type,
        object_name, method, *args, **kwargs):

    if object_type == 'common':
        if method == 'login':
            try:
                database = Database(database_name).connect()
                cursor = database.cursor()
                cursor.close()
            except Exception:
                return False
            res = security.login(database_name, user, session)
            Cache.clean(database_name)
            logger = logging.getLogger('dispatcher')
            msg = res and 'successful login' or 'bad login or password'
            logger.info('%s \'%s\' from %s:%d using %s on database \'%s\'' % \
                    (msg, user, host, port, protocol, database_name))
            Cache.resets(database_name)
            return res or False
        elif method == 'logout':
            name = security.logout(database_name, user, session)
            logger = logging.getLogger('dispatcher')
            logger.info('logout \'%s\' from %s:%d ' \
                    'using %s on database \'%s\'' %
                    (name, host, port, protocol, database_name))
            return True
        elif method == 'version':
            return VERSION
        elif method == 'timezone_get':
            return CONFIG['timezone']
        elif method == 'list_lang':
            return [
                ('bg_BG', 'Български'),
                ('ca_ES', 'Català'),
                ('cs_CZ', 'Čeština'),
                ('de_DE', 'Deutsch'),
                ('en_US', 'English'),
                ('es_AR', 'Español (Argentina)'),
                ('es_ES', 'Español (España)'),
                ('es_CO', 'Español (Colombia)'),
                ('fr_FR', 'Français'),
                ('nl_NL', 'Nederlands'),
                ('ru_RU', 'Russian'),
            ]
        elif method == 'db_exist':
            try:
                database = Database(*args, **kwargs).connect()
                cursor = database.cursor()
                cursor.close(close=True)
                return True
            except Exception:
                return False
        elif method == 'list':
            if CONFIG['prevent_dblist']:
                raise Exception('AccessDenied')
            database = Database().connect()
            try:
                cursor = database.cursor()
                try:
                    res = database.list(cursor)
                finally:
                    cursor.close(close=True)
            except Exception:
                res = []
            return res
        elif method == 'create':
            return create(*args, **kwargs)
        elif method == 'restore':
            return restore(*args, **kwargs)
        elif method == 'drop':
            return drop(*args, **kwargs)
        elif method == 'dump':
            return dump(*args, **kwargs)
        return
    elif object_type == 'system':
        database = Database(database_name).connect()
        database_list = Pool.database_list()
        pool = Pool(database_name)
        if not database_name in database_list:
            pool.init()
        if method == 'listMethods':
            res = []
            for type in ('model', 'wizard', 'report'):
                for object_name, obj in pool.iterobject(type=type):
                    for method in obj.__rpc__:
                        res.append(type + '.' + object_name + '.' + method)
                    if hasattr(obj, '_buttons'):
                        for button in obj._buttons:
                            res.append(type + '.' + object_name + '.' + button)
            return res
        elif method == 'methodSignature':
            return 'signatures not supported'
        elif method == 'methodHelp':
            res = []
            args_list = args[0].split('.')
            object_type = args_list[0]
            object_name = '.'.join(args_list[1:-1])
            method = args_list[-1]
            obj = pool.get(object_name, type=object_type)
            return pydoc.getdoc(getattr(obj, method))

    user = security.check(database_name, user, session)

    Cache.clean(database_name)
    database_list = Pool.database_list()
    pool = Pool(database_name)
    if not database_name in database_list:
        with Transaction().start(database_name, user,
                readonly=True) as transaction:
            pool.init()
    obj = pool.get(object_name, type=object_type)

    if method in obj.__rpc__:
        rpc = obj.__rpc__[method]
    elif method in getattr(obj, '_buttons', {}):
        rpc = RPC(readonly=False, instantiate=0)
    else:
        raise UserError('Calling method %s on %s %s is not allowed!'
            % (method, object_type, object_name))

    for count in range(int(CONFIG['retry']), -1, -1):
        with Transaction().start(database_name, user,
                readonly=rpc.readonly) as transaction:
            try:
                c_args, c_kwargs, transaction.context, transaction.timestamp \
                    = rpc.convert(obj, *args, **kwargs)
                meth = getattr(obj, method)
                if not hasattr(meth, 'im_self') or meth.im_self:
                    result = rpc.result(meth(*c_args, **c_kwargs))
                else:
                    assert rpc.instantiate == 0
                    inst = c_args.pop(0)
                    if hasattr(inst, method):
                        result = rpc.result(meth(inst, *c_args, **c_kwargs))
                    else:
                        result = [rpc.result(meth(i, *c_args, **c_kwargs))
                            for i in inst]
                if not rpc.readonly:
                    transaction.cursor.commit()
            except DatabaseOperationalError, exception:
                transaction.cursor.rollback()
                if count and not rpc.readonly:
                    continue
                raise
            except Exception, exception:
                if CONFIG['verbose'] and not isinstance(exception, (
                            NotLogged, ConcurrencyException, UserError,
                            UserWarning)):
                    tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
                    logger = logging.getLogger('dispatcher')
                    logger.error('Exception calling method %s on '
                        '%s %s from %s@%s:%d/%s:\n'
                        % (method, object_type, object_name, user, host, port,
                            database_name) + tb_s)
                transaction.cursor.rollback()
                raise
        if not (object_name == 'res.request' and method == 'request_get'):
            with Transaction().start(database_name, 0) as transaction:
                pool = Pool(database_name)
                Session = pool.get('ir.session')
                try:
                    Session.reset(session)
                except DatabaseOperationalError:
                    # Silently fail when reseting session
                    transaction.cursor.rollback()
                else:
                    transaction.cursor.commit()
        Cache.resets(database_name)
        return result


def create(database_name, password, lang, admin_password):
    '''
    Create a database

    :param database_name: the database name
    :param password: the server password
    :param lang: the default language for the database
    :param admin_password: the admin password
    :return: True if succeed
    '''
    security.check_super(password)
    res = False
    logger = logging.getLogger('database')

    try:
        database = Database().connect()
        cursor = database.cursor(autocommit=True)
        try:
            database.create(cursor, database_name)
            cursor.commit()
            cursor.close(close=True)
        except Exception:
            cursor.close()
            raise

        with Transaction().start(database_name, 0) as transaction:
            database.init(transaction.cursor)
            transaction.cursor.commit()

        pool = Pool(database_name)
        pool.init(update=True, lang=[lang])
        with Transaction().start(database_name, 0) as transaction:
            cursor = transaction.cursor
            #XXX replace with model write
            cursor.execute('UPDATE ir_lang ' \
                    'SET translatable = %s ' \
                    'WHERE code = %s', (True, lang))
            cursor.execute('UPDATE res_user ' \
                    'SET language = (' + \
                        cursor.limit_clause('SELECT id FROM ir_lang ' \
                        'WHERE code = %s', 1) + ')' \
                    'WHERE login <> \'root\'', (lang,))
            if hashlib:
                admin_password = hashlib.sha1(admin_password.encode('utf-8'))\
                    .hexdigest()
            else:
                admin_password = sha.new(admin_password.encode('utf-8'))\
                    .hexdigest()
            cursor.execute('UPDATE res_user ' \
                    'SET password = %s ' \
                    'WHERE login = \'admin\'', (admin_password,))
            Module = pool.get('ir.module.module')
            if Module:
                Module.update_list()
            cursor.commit()
            res = True
    except Exception:
        logger.error('CREATE DB: %s failed' % (database_name,))
        tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
        logger.error('Exception in call: \n' + tb_s)
        raise
    else:
        logger.info('CREATE DB: %s' % (database_name,))
    return res


def drop(database_name, password):
    security.check_super(password)
    Database(database_name).close()
    # Sleep to let connections close
    time.sleep(1)
    logger = logging.getLogger('database')

    database = Database().connect()
    cursor = database.cursor(autocommit=True)
    try:
        try:
            database.drop(cursor, database_name)
            cursor.commit()
        except Exception:
            logger.error('DROP DB: %s failed' % (database_name,))
            tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
            logger.error('Exception in call: \n' + tb_s)
            raise
        else:
            logger.info('DROP DB: %s' % (database_name))
            Pool.stop(database_name)
    finally:
        cursor.close(close=True)
    return True


def dump(database_name, password):
    security.check_super(password)
    Database(database_name).close()
    # Sleep to let connections close
    time.sleep(1)
    logger = logging.getLogger('database')

    data = Database.dump(database_name)
    logger.info('DUMP DB: %s' % (database_name))
    return buffer(data)


def restore(database_name, password, data, update=False):
    logger = logging.getLogger('database')
    security.check_super(password)
    try:
        database = Database().connect()
        cursor = database.cursor()
        cursor.close(close=True)
        raise Exception("Database already exists!")
    except Exception:
        pass
    Database.restore(database_name, data)
    logger.info('RESTORE DB: %s' % (database_name))
    if update:
        cursor = Database(database_name).connect().cursor()
        cursor.execute('SELECT code FROM ir_lang ' \
                'WHERE translatable')
        lang = [x[0] for x in cursor.fetchall()]
        cursor.execute('UPDATE ir_module_module SET ' \
                "state = 'to upgrade' " \
                "WHERE state = 'installed'")
        cursor.commit()
        cursor.close()
        Pool(database_name).init(update=update, lang=lang)
        logger.info('Update/Init succeed!')
    return True

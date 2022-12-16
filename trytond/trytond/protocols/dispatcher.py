# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import time
import pydoc

from sql import Table

from trytond.pool import Pool
from trytond import security
from trytond import backend
from trytond.config import config
from trytond import __version__
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.exceptions import UserError, UserWarning, NotLogged, \
    ConcurrencyException
from trytond.tools import is_instance_method

logger = logging.getLogger(__name__)

ir_configuration = Table('ir_configuration')
ir_lang = Table('ir_lang')
ir_module = Table('ir_module')
res_user = Table('res_user')


def dispatch(host, port, protocol, database_name, user, session, object_type,
        object_name, method, *args, **kwargs):
    Database = backend.get('Database')
    DatabaseOperationalError = backend.get('DatabaseOperationalError')
    if object_type == 'common':
        if method == 'login':
            try:
                database = Database(database_name).connect()
                cursor = database.cursor()
                cursor.close()
            except Exception:
                return False
            res = security.login(database_name, user, session)
            with Transaction().start(database_name, 0):
                Cache.clean(database_name)
                Cache.resets(database_name)
            msg = res and 'successful login' or 'bad login or password'
            logger.info('%s \'%s\' from %s:%d using %s on database \'%s\'',
                msg, user, host, port, protocol, database_name)
            return res or False
        elif method == 'logout':
            name = security.logout(database_name, user, session)
            logger.info('logout \'%s\' from %s:%d '
                'using %s on database \'%s\'',
                name, host, port, protocol, database_name)
            return True
        elif method == 'version':
            return __version__
        elif method == 'list_lang':
            return [
                ('bg_BG', 'Български'),
                ('ca_ES', 'Català'),
                ('cs_CZ', 'Čeština'),
                ('de_DE', 'Deutsch'),
                ('en_US', 'English'),
                ('es_AR', 'Español (Argentina)'),
                ('es_EC', 'Español (Ecuador)'),
                ('es_ES', 'Español (España)'),
                ('es_CO', 'Español (Colombia)'),
                ('es_MX', 'Español (México)'),
                ('fr_FR', 'Français'),
                ('hu_HU', 'Magyar'),
                ('it_IT', 'Italiano'),
                ('lt_LT', 'Lietuvių'),
                ('nl_NL', 'Nederlands'),
                ('pt_BR', 'Português (Brasil)'),
                ('ru_RU', 'Russian'),
                ('sl_SI', 'Slovenščina'),
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
            if not config.getboolean('database', 'list'):
                raise Exception('AccessDenied')
            with Transaction().start(None, 0, close=True) as transaction:
                return transaction.database.list(transaction.cursor)
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
        if database_name not in database_list:
            pool.init()
        if method == 'listMethods':
            res = []
            for type in ('model', 'wizard', 'report'):
                for object_name, obj in pool.iterobject(type=type):
                    for method in obj.__rpc__:
                        res.append(type + '.' + object_name + '.' + method)
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

    for count in range(config.getint('database', 'retry'), -1, -1):
        try:
            user = security.check(database_name, user, session)
        except DatabaseOperationalError:
            if count:
                continue
            raise
        break

    database_list = Pool.database_list()
    pool = Pool(database_name)
    if database_name not in database_list:
        with Transaction().start(database_name, user,
                readonly=True) as transaction:
            pool.init()
    obj = pool.get(object_name, type=object_type)

    if method in obj.__rpc__:
        rpc = obj.__rpc__[method]
    else:
        raise UserError('Calling method %s on %s %s is not allowed!'
            % (method, object_type, object_name))

    log_message = '%s.%s.%s(*%s, **%s) from %s@%s:%d/%s'
    log_args = (object_type, object_name, method, args, kwargs,
        user, host, port, database_name)

    logger.info(log_message, *log_args)
    for count in range(config.getint('database', 'retry'), -1, -1):
        with Transaction().start(database_name, user,
                readonly=rpc.readonly) as transaction:
            Cache.clean(database_name)
            try:
                c_args, c_kwargs, transaction.context, transaction.timestamp \
                    = rpc.convert(obj, *args, **kwargs)
                meth = getattr(obj, method)
                if (rpc.instantiate is None
                        or not is_instance_method(obj, method)):
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
            except DatabaseOperationalError:
                transaction.cursor.rollback()
                if count and not rpc.readonly:
                    continue
                raise
            except (NotLogged, ConcurrencyException, UserError, UserWarning):
                logger.debug(log_message, *log_args, exc_info=True)
                transaction.cursor.rollback()
                raise
            except Exception:
                logger.error(log_message, *log_args, exc_info=True)
                transaction.cursor.rollback()
                raise
            Cache.resets(database_name)
        with Transaction().start(database_name, 0) as transaction:
            pool = Pool(database_name)
            Session = pool.get('ir.session')
            try:
                Session.reset(session)
            except DatabaseOperationalError:
                logger.debug('Reset session failed', exc_info=True)
                # Silently fail when reseting session
                transaction.cursor.rollback()
            else:
                transaction.cursor.commit()
        logger.debug('Result: %s', result)
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
    Database = backend.get('Database')
    security.check_super(password)
    res = False

    try:
        with Transaction().start(None, 0, close=True, autocommit=True) \
                as transaction:
            transaction.database.create(transaction.cursor, database_name)
            transaction.cursor.commit()

        with Transaction().start(database_name, 0) as transaction:
            Database.init(transaction.cursor)
            transaction.cursor.execute(*ir_configuration.insert(
                    [ir_configuration.language], [[lang]]))
            transaction.cursor.commit()

        pool = Pool(database_name)
        pool.init(update=['res', 'ir'], lang=[lang])
        with Transaction().start(database_name, 0) as transaction:
            User = pool.get('res.user')
            Lang = pool.get('ir.lang')
            language, = Lang.search([('code', '=', lang)])
            language.translatable = True
            language.save()
            users = User.search([('login', '!=', 'root')])
            User.write(users, {
                    'language': language.id,
                    })
            admin, = User.search([('login', '=', 'admin')])
            User.write([admin], {
                    'password': admin_password,
                    })
            Module = pool.get('ir.module')
            if Module:
                Module.update_list()
            transaction.cursor.commit()
            res = True
    except Exception:
        logger.error('CREATE DB: %s failed', database_name, exc_info=True)
        raise
    else:
        logger.info('CREATE DB: %s', database_name)
    return res


def drop(database_name, password):
    Database = backend.get('Database')
    security.check_super(password)
    Database(database_name).close()
    # Sleep to let connections close
    time.sleep(1)

    with Transaction().start(None, 0, close=True, autocommit=True) \
            as transaction:
        cursor = transaction.cursor
        try:
            Database.drop(cursor, database_name)
            cursor.commit()
        except Exception:
            logger.error('DROP DB: %s failed', database_name, exc_info=True)
            raise
        else:
            logger.info('DROP DB: %s', database_name)
            Pool.stop(database_name)
            Cache.drop(database_name)
    return True


def dump(database_name, password):
    Database = backend.get('Database')
    security.check_super(password)
    Database(database_name).close()
    # Sleep to let connections close
    time.sleep(1)

    data = Database.dump(database_name)
    logger.info('DUMP DB: %s', database_name)
    if bytes == str:
        return bytearray(data)
    else:
        return bytes(data)


def restore(database_name, password, data, update=False):
    Database = backend.get('Database')
    security.check_super(password)
    try:
        database = Database(database_name).connect()
        cursor = database.cursor()
        cursor.close(close=True)
        existing = True
    except Exception:
        existing = False
    if existing:
        raise Exception('Database already exists!')
    Database.restore(database_name, data)
    logger.info('RESTORE DB: %s', database_name)
    if update:
        with Transaction().start(database_name, 0) as transaction:
            cursor = transaction.cursor
            cursor.execute(*ir_lang.select(ir_lang.code,
                    where=ir_lang.translatable))
            lang = [x[0] for x in cursor.fetchall()]
            cursor.execute(*ir_module.select(ir_module.name,
                    where=(ir_module.state == 'installed')))
            update = [x[0] for x in cursor.fetchall()]
        Pool(database_name).init(update=update, lang=lang)
        logger.info('Update/Init succeed!')
    return True

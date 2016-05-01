# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import time
import pydoc
from functools import wraps

from werkzeug.utils import redirect
from sql import Table

from trytond.pool import Pool
from trytond import security
from trytond import backend
from trytond.config import config
from trytond import __version__
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.exceptions import UserError, UserWarning, ConcurrencyException
from trytond.tools import is_instance_method
from trytond.wsgi import app

logger = logging.getLogger(__name__)

ir_configuration = Table('ir_configuration')
ir_lang = Table('ir_lang')
ir_module = Table('ir_module')
res_user = Table('res_user')


def with_pool(func):
    @wraps(func)
    def wrapper(request, database_name, *args, **kwargs):
        database_list = Pool.database_list()
        pool = Pool(database_name)
        if database_name not in database_list:
            with Transaction().start(
                    database_name, request.user_id, readonly=True):
                pool.init()
        return func(request, pool, *args, **kwargs)
    return wrapper


@app.route('/<string:database_name>/', methods=['POST'])
def rpc(request, database_name):
    methods = {
        'common.db.login': login,
        'common.db.logout': logout,
        'common.db.db_exist': db_exist,
        'common.db.create': create,
        'common.db.restore': restore,
        'common.db.drop': drop,
        'common.db.dump': dump,
        'system.listMethods': list_method,
        'system.methodHelp': help_method,
        'system.methodSignature': lambda *a: 'signatures not supported',
        }
    return methods.get(request.method, _dispatch)(
        request, database_name, *request.params)


def login(request, database_name, user, password):
    Database = backend.get('Database')
    DatabaseOperationalError = backend.get('DatabaseOperationalError')
    try:
        Database(database_name).connect()
    except DatabaseOperationalError:
        logger.error('fail to connect to %s', database_name, exc_info=True)
        return False
    session = security.login(database_name, user, password)
    with Transaction().start(database_name, 0):
        Cache.clean(database_name)
        Cache.resets(database_name)
    msg = 'successful login' if session else 'bad login or password'
    logger.info('%s \'%s\' from %s using %s on database \'%s\'',
        msg, user, request.remote_addr, request.scheme, database_name)
    return session


@app.auth_required
def logout(request, database_name):
    auth = request.authorization
    name = security.logout(
        database_name, auth.get('userid'), auth.get('session'))
    logger.info('logout \'%s\' from %s using %s on database \'%s\'',
        name, request.remote_addr, request.scheme, database_name)
    return True


@app.route('/', methods=['POST'])
def root(request, *args):
    methods = {
        'common.server.version': lambda *a: __version__,
        'common.db.list_lang': list_lang,
        'common.db.list': db_list,
        }
    return methods[request.method](request, *request.params)


@app.route('/', methods=['GET'])
def home(request):
    return redirect('/index.html')  # XXX find a better way


def list_lang(*args):
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
        ('lo_LA', 'ລາວ'),
        ('nl_NL', 'Nederlands'),
        ('pt_BR', 'Português (Brasil)'),
        ('ru_RU', 'Russian'),
        ('sl_SI', 'Slovenščina'),
        ('zh_CN', '中国（简体）'),
        ]


def db_exist(request, database_name):
    Database = backend.get('Database')
    try:
        Database(database_name).connect()
        return True
    except Exception:
        return False


def db_list(*args):
    if not config.getboolean('database', 'list'):
        raise Exception('AccessDenied')
    with Transaction().start(None, 0, close=True) as transaction:
        return transaction.database.list()


@app.auth_required
@with_pool
def list_method(request, pool):
    methods = []
    for type in ('model', 'wizard', 'report'):
        for object_name, obj in pool.iterobject(type=type):
            for method in obj.__rpc__:
                methods.append(type + '.' + object_name + '.' + method)
    return methods


def get_object_method(request, pool):
    method = request.method
    type, _ = method.split('.', 1)
    name = '.'.join(method.split('.')[1:-1])
    method = method.split('.')[-1]
    return pool.get(name, type=type), method


@app.auth_required
@with_pool
def help_method(request, pool):
    obj, method = get_object_method(request, pool)
    return pydoc.getdoc(getattr(obj, method))


@app.auth_required
@with_pool
def _dispatch(request, pool, *args, **kwargs):
    DatabaseOperationalError = backend.get('DatabaseOperationalError')

    obj, method = get_object_method(request, pool)
    if method in obj.__rpc__:
        rpc = obj.__rpc__[method]
    else:
        raise UserError('Calling method %s on %s is not allowed'
            % (method, obj))

    log_message = '%s.%s(*%s, **%s) from %s@%s/%s'
    log_args = (obj, method, args, kwargs,
        request.authorization.username, request.remote_addr, request.path)
    logger.info(log_message, *log_args)

    user = request.user_id

    for count in range(config.getint('database', 'retry'), -1, -1):
        with Transaction().start(pool.database_name, user,
                readonly=rpc.readonly) as transaction:
            Cache.clean(pool.database_name)
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
            except DatabaseOperationalError:
                if count and not rpc.readonly:
                    transaction.rollback()
                    continue
                logger.error(log_message, *log_args, exc_info=True)
                raise
            except (ConcurrencyException, UserError, UserWarning):
                logger.debug(log_message, *log_args, exc_info=True)
                raise
            except Exception:
                logger.error(log_message, *log_args, exc_info=True)
                raise
            # Need to commit to unlock SQLite database
            transaction.commit()
            Cache.resets(pool.database_name)
        if request.authorization.type == 'session':
            try:
                with Transaction().start(pool.database_name, 0) as transaction:
                    Session = pool.get('ir.session')
                    Session.reset(request.authorization.get('session'))
            except DatabaseOperationalError:
                logger.debug('Reset session failed', exc_info=True)
        logger.debug('Result: %s', result)
        return result


def create(request, database_name, password, lang, admin_password):
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
            transaction.database.create(transaction.connection, database_name)

        with Transaction().start(database_name, 0) as transaction,\
                transaction.connection.cursor() as cursor:
            Database(database_name).init()
            cursor.execute(*ir_configuration.insert(
                    [ir_configuration.language], [[lang]]))

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
            res = True
    except Exception:
        logger.error('CREATE DB: %s failed', database_name, exc_info=True)
        raise
    else:
        logger.info('CREATE DB: %s', database_name)
    return res


def drop(request, database_name, password):
    Database = backend.get('Database')
    security.check_super(password)
    database = Database(database_name)
    database.close()
    # Sleep to let connections close
    time.sleep(1)

    with Transaction().start(None, 0, close=True, autocommit=True) \
            as transaction:
        try:
            database.drop(transaction.connection, database_name)
        except Exception:
            logger.error('DROP DB: %s failed', database_name, exc_info=True)
            raise
        else:
            logger.info('DROP DB: %s', database_name)
            Pool.stop(database_name)
            Cache.drop(database_name)
    return True


def dump(request, database_name, password):
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


def restore(request, database_name, password, data, update=False):
    Database = backend.get('Database')
    security.check_super(password)
    try:
        Database(database_name).connect()
        existing = True
    except Exception:
        existing = False
    if existing:
        raise Exception('Database already exists!')
    Database.restore(database_name, data)
    logger.info('RESTORE DB: %s', database_name)
    if update:
        with Transaction().start(database_name, 0) as transaction,\
                transaction.connection.cursor() as cursor:
            cursor.execute(*ir_lang.select(ir_lang.code,
                    where=ir_lang.translatable))
            lang = [x[0] for x in cursor.fetchall()]
            cursor.execute(*ir_module.select(ir_module.name,
                    where=(ir_module.state == 'installed')))
            update = [x[0] for x in cursor.fetchall()]
        Pool(database_name).init(update=update, lang=lang)
        logger.info('Update/Init succeed!')
    return True

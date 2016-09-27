# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import pydoc

from werkzeug.utils import redirect
from werkzeug.exceptions import abort
from sql import Table

from trytond import security
from trytond import backend
from trytond.config import config
from trytond import __version__
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.exceptions import (
    UserError, UserWarning, ConcurrencyException, LoginException)
from trytond.tools import is_instance_method
from trytond.wsgi import app
from .wrappers import with_pool

logger = logging.getLogger(__name__)

ir_configuration = Table('ir_configuration')
ir_lang = Table('ir_lang')
ir_module = Table('ir_module')
res_user = Table('res_user')


@app.route('/<string:database_name>/', methods=['POST'])
def rpc(request, database_name):
    methods = {
        'common.db.login': login,
        'common.db.logout': logout,
        'system.listMethods': list_method,
        'system.methodHelp': help_method,
        'system.methodSignature': lambda *a: 'signatures not supported',
        }
    return methods.get(request.rpc_method, _dispatch)(
        request, database_name, *request.rpc_params)


def login(request, database_name, user, parameters, language=None):
    Database = backend.get('Database')
    DatabaseOperationalError = backend.get('DatabaseOperationalError')
    try:
        Database(database_name).connect()
    except DatabaseOperationalError:
        logger.error('fail to connect to %s', database_name, exc_info=True)
        abort(404)
    session = security.login(
        database_name, user, parameters, language=language)
    with Transaction().start(database_name, 0):
        Cache.clean(database_name)
        Cache.resets(database_name)
    msg = 'successful login' if session else 'bad login or password'
    logger.info('%s \'%s\' from %s using %s on database \'%s\'',
        msg, user, request.remote_addr, request.scheme, database_name)
    if not session:
        abort(403)
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
        'common.db.list': db_list,
        }
    return methods[request.rpc_method](request, *request.rpc_params)


@app.route('/', methods=['GET'])
def home(request):
    return redirect('/index.html')  # XXX find a better way


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
    method = request.rpc_method
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
            except (ConcurrencyException, UserError, UserWarning,
                    LoginException):
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

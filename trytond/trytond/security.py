# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import ipaddress
import logging
import random
import time
from secrets import compare_digest

try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from sql import Table
from sql.conditionals import Coalesce
from werkzeug.exceptions import abort

from trytond import backend, config
from trytond.exceptions import LoginException, RateLimitException
from trytond.pool import Pool
from trytond.tools import sqlite_apply_types
from trytond.transaction import Transaction

logger = logging.getLogger(__name__)


def _get_pool(dbname):
    database_list = Pool.database_list()
    if dbname not in database_list:
        db_list = Transaction().database.list()
        if dbname not in db_list:
            abort(HTTPStatus.NOT_FOUND)
    pool = Pool(dbname)
    if dbname not in database_list:
        pool.init()
    return pool


def _get_remote_addr(context):
    if context and '_request' in context:
        return context['_request'].get('remote_addr')


def login(dbname, loginname, parameters, cache=True, context=None):
    for count in range(config.getint('database', 'retry'), -1, -1):
        with Transaction().start(dbname, 0, context=context) as transaction:
            pool = _get_pool(dbname)
            User = pool.get('res.user')
            try:
                user_id = User.get_login(loginname, parameters)
                break
            except backend.DatabaseOperationalError:
                if count:
                    continue
                raise
            except (LoginException, RateLimitException):
                # Let's store any changes done
                transaction.commit()
                raise
    session = None
    if user_id:
        if not cache:
            session = user_id
        else:
            with Transaction().start(dbname, user_id, context=context):
                Session = pool.get('ir.session')
                session = user_id, Session.new()
        logger.info("login succeeded for '%s' from '%s' on database '%s'",
            loginname, _get_remote_addr(context), dbname)
    else:
        logger.error("login failed for '%s' from '%s' on database '%s'",
            loginname, _get_remote_addr(context), dbname)
    return session


def logout(dbname, user, session, context=None):
    for count in range(config.getint('database', 'retry'), -1, -1):
        with Transaction().start(dbname, 0, context=context):
            pool = _get_pool(dbname)
            Session = pool.get('ir.session')
            try:
                name = Session.remove(session)
                break
            except backend.DatabaseOperationalError:
                if count:
                    continue
                raise
    if name:
        logger.info("logout for '%s' from '%s' on database '%s'",
            name, _get_remote_addr(context), dbname)
    else:
        logger.error("logout failed for '%s' from '%s' on database '%s'",
            user, _get_remote_addr(context), dbname)


def reset_password(dbname, user, context=None):
    now = dt.datetime.now()
    # Prevent guessing code execution path
    time.sleep(random.random())
    for count in range(config.getint('database', 'retry'), -1, -1):
        with Transaction().start(dbname, 0, context=context):
            pool = _get_pool(dbname)
            User = pool.get('res.user')
            try:
                users = User.search([
                        ('login', '=', user),
                        ])
                if not users:
                    logger.info("Reset password for unknown user: %s", user)
                    break
                else:
                    user, = users
                if user.password_reset and user.password_reset_expire > now:
                    logger.info(
                        "Password reset already exists for user: %s", user)
                else:
                    user.reset_password()
                    logger.info("Password reset for user: %s", user)
                break
            except backend.DatabaseOperationalError:
                if count:
                    continue
                raise


def check(dbname, user, session, context=None):
    remote_addr = _get_remote_addr(context)

    database_list = Pool.database_list()
    if dbname in database_list:
        for count in range(config.getint('database', 'retry'), -1, -1):
            with Transaction().start(dbname, user, context=context) \
                    as transaction:
                pool = Pool(dbname)
                Session = pool.get('ir.session')
                try:
                    find = Session.check(user, session)
                    break
                except backend.DatabaseOperationalError:
                    if count:
                        continue
                    raise
                finally:
                    transaction.commit()
    else:
        if remote_addr:
            ip_addr = str(ipaddress.ip_address(remote_addr))
        else:
            ip_addr = None
        now = dt.datetime.now()
        timeout = dt.timedelta(config.getint('session', 'max_age'))
        database = backend.Database(dbname)
        conn = database.get_connection(readonly=True)
        try:
            ir_session = Table('ir_session')
            cursor = conn.cursor()
            session_query = ir_session.select(
                Coalesce(
                    ir_session.write_date, ir_session.create_date).as_('date'),
                ir_session.key,
                where=((ir_session.create_uid == user)
                    & (ir_session.ip_address == ip_addr)))
            if backend.name == 'sqlite':
                sqlite_apply_types(session_query, ['DATETIME', None])
            cursor.execute(*session_query)
            bad_session = False
            for session_date, session_key in cursor:
                if abs(session_date - now) < timeout:
                    if compare_digest(session_key, session):
                        find = session
                        break
                    else:
                        bad_session = True
            else:
                find = None if bad_session else ''
        finally:
            database.put_connection(conn)

    if find is None:
        logger.error("session failed for '%s' from '%s' on database '%s'",
            user, remote_addr, dbname)
        return
    elif not find:
        logger.info("session expired for '%s' from '%s' on database '%s'",
            user, remote_addr, dbname)
        return
    else:
        logger.debug("session valid for '%s' from '%s' on database '%s'",
            user, remote_addr, dbname)
        return user


def check_timeout(dbname, user, session, context=None):
    for count in range(config.getint('database', 'retry'), -1, -1):
        with Transaction().start(dbname, user, context=context) as transaction:
            pool = _get_pool(dbname)
            Session = pool.get('ir.session')
            try:
                valid = Session.check_timeout(user, session)
                break
            except backend.DatabaseOperationalError:
                if count:
                    continue
                raise
            finally:
                transaction.commit()
    if not valid:
        logger.info("session timeout for '%s' from '%s' on database '%s'",
            user, _get_remote_addr(context), dbname)
    return valid


def reset(dbname, session, context):
    try:
        with Transaction().start(dbname, 0, context=context, autocommit=True):
            pool = _get_pool(dbname)
            Session = pool.get('ir.session')
            Session.reset(session)
    except backend.DatabaseOperationalError:
        logger.debug('Reset session failed', exc_info=True)

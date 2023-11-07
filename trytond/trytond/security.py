# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import logging
import random
import time

from trytond import backend
from trytond.config import config
from trytond.exceptions import LoginException, RateLimitException
from trytond.pool import Pool
from trytond.transaction import Transaction

logger = logging.getLogger(__name__)


def _get_pool(dbname):
    database_list = Pool.database_list()
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
            with Transaction().start(dbname, user_id):
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
    for count in range(config.getint('database', 'retry'), -1, -1):
        with Transaction().start(dbname, user, context=context) as transaction:
            pool = _get_pool(dbname)
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
    if find is None:
        logger.error("session failed for '%s' from '%s' on database '%s'",
            user, _get_remote_addr(context), dbname)
        return
    elif not find:
        logger.info("session expired for '%s' from '%s' on database '%s'",
            user, _get_remote_addr(context), dbname)
        return
    else:
        logger.debug("session valid for '%s' from '%s' on database '%s'",
            user, _get_remote_addr(context), dbname)
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

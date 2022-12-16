# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import time
import random

from werkzeug.exceptions import abort

from trytond.config import config
from trytond.wsgi import app
from trytond.protocols.wrappers import (
    with_pool, with_transaction, allow_null_origin)
from trytond.transaction import Transaction

logger = logging.getLogger(__name__)


@app.route('/<database_name>/user/application/', methods=['POST', 'DELETE'])
@allow_null_origin
@with_pool
@with_transaction(readonly=False)
def user_application(request, pool):
    User = pool.get('res.user')
    UserApplication = pool.get('res.user.application')
    LoginAttempt = pool.get('res.user.login.attempt')
    data = request.parsed_data
    login = data.get('user')

    if request.method == 'POST':
        # Make time random to process and try to use the same path as much as
        # possible to prevent guessing between valid and invalid requests.
        Transaction().atexit(time.sleep, random.random())
        users = User.search([
                ('login', '=', login),
                ])
        if not users:
            logger.info('User Application not found: %s', data.get('user'))
            user_id = None
        else:
            user, = users
            user_id = user.id
        if UserApplication.count(user_id):
            logger.info('User Application has already a request: %s', login)
            user_id = None
        data['user'] = user_id
        data.pop('key', None)
        data.pop('state', None)
        application, = UserApplication.create([data])
        key = application.key
        UserApplication.delete(UserApplication.search([
                    ('user', '=', None),
                    ]))
        return key
    elif request.method == 'DELETE':
        count = LoginAttempt.count(login)
        if count > config.getint('session', 'max_attempt', default=5):
            LoginAttempt.add(login)
            abort(429)
        Transaction().atexit(time.sleep, 2 ** count - 1)
        applications = UserApplication.search([
                ('user.login', '=', login),
                ('key', '=', data.get('key')),
                ('application', '=', data.get('application')),
                ])
        if applications:
            UserApplication.delete(applications)
            LoginAttempt.remove(login)
        else:
            LoginAttempt.add(login)

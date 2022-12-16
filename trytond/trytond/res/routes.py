# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import time
import random

from trytond.wsgi import app
from trytond.protocols.wrappers import with_pool, with_transaction

logger = logging.getLogger(__name__)


@app.route('/<database_name>/user/application/', methods=['POST', 'DELETE'])
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
        time.sleep(random.random())
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
        time.sleep(2 ** LoginAttempt.count(login) - 1)
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

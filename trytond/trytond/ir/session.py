# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    import simplejson as json
except ImportError:
    import json
import uuid
import datetime

from trytond.model import ModelSQL, fields
from trytond.config import config
from .. import backend

__all__ = [
    'Session', 'SessionWizard',
    ]


class Session(ModelSQL):
    "Session"
    __name__ = 'ir.session'
    _rec_name = 'key'

    key = fields.Char('Key', required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(Session, cls).__setup__()
        cls.__rpc__ = {}

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        super(Session, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        table.index_action('create_uid', 'add')

    @staticmethod
    def default_key():
        return uuid.uuid4().hex

    @classmethod
    def check(cls, user, key):
        "Check user key and delete old one"
        now = datetime.datetime.now()
        timeout = datetime.timedelta(
            seconds=config.getint('session', 'timeout'))
        sessions = cls.search([
                ('create_uid', '=', user),
                ])
        find = False
        for session in sessions:
            timestamp = session.write_date or session.create_date
            if abs(timestamp - now) < timeout:
                if session.key == key:
                    find = True
            else:
                cls.delete([session])
        return find

    @classmethod
    def reset(cls, session):
        "Reset session timestamp"
        sessions = cls.search([
                ('key', '=', session),
                ])
        cls.write(sessions, {})


class SessionWizard(ModelSQL):
    "Session Wizard"
    __name__ = 'ir.session.wizard'

    data = fields.Text('Data')

    @classmethod
    def __setup__(cls):
        super(SessionWizard, cls).__setup__()
        cls.__rpc__ = {}

    @staticmethod
    def default_data():
        return json.dumps({})

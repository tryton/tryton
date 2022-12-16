#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
try:
    import simplejson as json
except ImportError:
    import json
import uuid
import datetime

from trytond.model import ModelSQL, fields
from trytond.config import CONFIG
from ..backend import TableHandler
from ..transaction import Transaction


class Session(ModelSQL):
    "Session"
    _name = 'ir.session'
    _description = __doc__
    _rec_name = 'key'

    key = fields.Char('Key', required=True, select=True)

    def __init__(self):
        super(Session, self).__init__()
        self._rpc = {}

    def init(self, module_name):
        super(Session, self).init(module_name)

        table = TableHandler(Transaction().cursor, self, module_name)
        table.index_action('create_uid', 'add')

    def default_key(self):
        return uuid.uuid4().hex

    def check(self, user, key):
        "Check user key and delete old one"
        now = datetime.datetime.now()
        timeout = int(CONFIG['session_timeout'])
        session_ids = self.search([
                ('create_uid', '=', user),
                ])
        sessions = self.browse(session_ids)
        find = False
        for session in sessions:
            timestamp = session.write_date or session.create_date
            delta = timestamp - now
            # total_seconds new in version 2.7
            if hasattr(delta, 'total_seconds'):
                delta = delta.total_seconds()
            else:
                delta = (delta.microseconds + (delta.seconds + delta.days * 24
                        * 3600) * 10 ** 6) / 10 ** 6
            if abs(delta) < timeout:
                if session.key == key:
                    find = True
            else:
                self.delete(session.id)
        return find

    def reset(self, session):
        "Reset session timestamp"
        session_id = self.search([
                ('key', '=', session),
                ])
        self.write(session_id, {})

Session()


class SessionWizard(ModelSQL):
    "Session Wizard"
    _name = 'ir.session.wizard'
    _description = __doc__

    data = fields.Text('Data')

    def __init__(self):
        super(SessionWizard, self).__init__()
        self._rpc = {}

    def default_data(self):
        return json.dumps({})

SessionWizard()

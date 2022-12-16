# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import binascii
import datetime
import json
import os
try:
    from secrets import token_hex
except ImportError:
    def token_hex(nbytes=None):
        if nbytes is None:
            nbytes = 32
        return binascii.hexlify(os.urandom(nbytes)).decode('ascii')

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

    @classmethod
    def default_key(cls, nbytes=None):
        return token_hex(nbytes)

    @classmethod
    def new(cls, values=None):
        "Create a new session for the transaction user and return the key."
        if values is None:
            values = {}
        session, = cls.create([values])
        return session.key

    @classmethod
    def remove(cls, key, domain=None):
        "Delete the key session and return the login."
        domain = [
            ('key', '=', key),
            domain or [],
            ]
        sessions = cls.search(domain)
        if not sessions:
            return
        session, = sessions
        name = session.create_uid.login
        cls.delete(sessions)
        return name

    @classmethod
    def check(cls, user, key, domain=None):
        """
        Check user key and delete old one.
        Return True if key is still valid, False if the key is expired and None
        if the key does not exist.
        """
        now = datetime.datetime.now()
        timeout = datetime.timedelta(
            seconds=config.getint('session', 'timeout'))
        sessions = cls.search([
                ('create_uid', '=', user),
                domain or [],
                ])
        find = None
        to_delete = []
        for session in sessions:
            timestamp = session.write_date or session.create_date
            if abs(timestamp - now) < timeout:
                if session.key == key:
                    find = True
            else:
                if find is None and session.key == key:
                    find = False
                to_delete.append(session)
        cls.delete(to_delete)
        return find

    @classmethod
    def reset(cls, key, domain=None):
        "Reset key session timestamp"
        sessions = cls.search([
                ('key', '=', key),
                domain or [],
                ])
        cls.write(sessions, {})

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            # Ensure to get a different key for each record
            # default methods are called only once
            values.setdefault('key', cls.default_key())
        return super(Session, cls).create(vlist)


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

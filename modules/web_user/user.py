# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging
import random
import time
import urllib.parse
from secrets import token_hex

try:
    import bcrypt
except ImportError:
    bcrypt = None
try:
    import html2text
except ImportError:
    html2text = None
from sql import Literal, Null
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp
from sql.operators import Equal

import trytond.config as config
from trytond.exceptions import RateLimitException
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Exclude, Index, ModelSQL, ModelView, Unique,
    avatar_mixin, fields)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.report import Report, get_email
from trytond.res.user import PASSWORD_HASH, LoginAttempt
from trytond.sendmail import send_message_transactional
from trytond.tools.email_ import (
    EmailNotValidError, normalize_email, set_from_header, validate_email)
from trytond.transaction import Transaction, without_check_access

from .exceptions import UserValidationError

logger = logging.getLogger(__name__)


def _send_email(from_, users, email_func):
    from_cfg = config.get('email', 'from')
    for user in users:
        msg, title = email_func(user)
        set_from_header(msg, from_cfg, from_ or from_cfg)
        msg['To'] = user.email
        msg['Subject'] = title
        send_message_transactional(msg)


def _add_params(url, **params):
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query)
    for key, value in sorted(params.items()):
        query.append((key, value))
    parts = list(parts)
    parts[3] = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit(parts)


def _extract_params(url):
    return urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query)


class User(avatar_mixin(100), DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'web.user'
    _rec_name = 'email'

    email = fields.Char(
        "Email",
        states={
            'required': Eval('active', True),
            })
    email_valid = fields.Boolean('Email Valid')
    email_token = fields.Char("Email Token", strip=False)
    password_hash = fields.Char('Password Hash')
    password = fields.Function(
        fields.Char('Password'), 'get_password', setter='set_password')
    reset_password_token = fields.Char("Reset Password Token", strip=False)
    reset_password_token_expire = fields.Timestamp(
        'Reset Password Token Expire')
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT')
    secondary_parties = fields.Many2Many(
        'web.user-party.party.secondary', 'user', 'party', "Secondary Parties")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('email_exclude',
                Exclude(table, (table.email, Equal),
                    where=table.active == Literal(True)),
                'web_user.msg_user_email_unique'),
            ]
        cls._sql_indexes.update({
                Index(
                    table, (table.email, Index.Equality(cardinality='high'))),
                Index(
                    table,
                    (table.email_token, Index.Equality(cardinality='high')),
                    where=table.email_token != Null),
                })
        cls._buttons.update({
                'validate_email': {
                    'readonly': Eval('email_valid', False),
                    'depends': ['email_valid'],
                    },
                'reset_password': {
                    'readonly': ~Eval('email_valid', False),
                    'depends': ['email_valid'],
                    },
                })

    @classmethod
    def default_email_valid(cls):
        return False

    def get_password(self, name):
        return 'x' * 10

    @classmethod
    def set_password(cls, users, name, value):
        pool = Pool()
        User = pool.get('res.user')

        if value == 'x' * 10:
            return

        if Transaction().user and value:
            User.validate_password(value, users)

        to_write = []
        for user in users:
            to_write.extend([[user], {
                        'password_hash': cls.hash_password(value),
                        }])
        cls.write(*to_write)

    @fields.depends('party', 'email')
    def on_change_party(self):
        if not self.email and self.party:
            self.email = self.party.email

    @classmethod
    def copy(cls, users, default=None):
        default = default.copy() if default is not None else {}
        default['password_hash'] = None
        default['reset_password_token'] = None
        return super().copy(users, default=default)

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if values.get('email'):
            values['email'] = normalize_email(values['email']).lower()
        return values

    @classmethod
    def validate_fields(cls, users, fields_names):
        super().validate_fields(users, fields_names)
        cls.check_valid_email(users, fields_names)

    @classmethod
    def check_valid_email(cls, users, fields_names=None):
        if fields_names and 'email' not in fields_names:
            return
        for user in users:
            if user.email:
                try:
                    validate_email(user.email)
                except EmailNotValidError as e:
                    raise UserValidationError(gettext(
                            'web_user.msg_user_email_invalid',
                            user=user.rec_name,
                            email=user.email),
                        str(e)) from e

    @classmethod
    def authenticate(cls, email, password):
        pool = Pool()
        Attempt = pool.get('web.user.authenticate.attempt')
        email = email.lower()

        count_ip = Attempt.count_ip()
        if count_ip > config.getint(
                'session', 'max_attempt_ip_network', default=300):
            # Do not add attempt as the goal is to prevent flooding
            raise RateLimitException()
        count = Attempt.count(email)
        if count > config.getint('session', 'max_attempt', default=5):
            Attempt.add(email)
            raise RateLimitException()
        # Prevent brute force attack
        Transaction().atexit(time.sleep, 2 ** count - 1)

        users = cls.search([('email', '=', email)])
        if users:
            user, = users
            valid, new_hash = cls.check_password(password, user.password_hash)
            if valid:
                if new_hash:
                    logger.info("Update password hash for %s", user.id)
                    with Transaction().new_transaction():
                        with without_check_access():
                            cls.write([cls(user.id)], {
                                    'password_hash': new_hash,
                                    })
                Attempt.remove(email)
                return user
        Attempt.add(email)

    @classmethod
    def hash_password(cls, password):
        '''Hash given password in the form
        <hash_method>$<password>$<salt>...'''
        if not password:
            return None
        return PASSWORD_HASH.hash(password)

    @classmethod
    def check_password(cls, password, hash_):
        return PASSWORD_HASH.verify_and_update(password, hash_)

    def new_session(self):
        pool = Pool()
        Session = pool.get('web.user.session')
        return Session.add(self)

    @classmethod
    def get_user(cls, session):
        pool = Pool()
        Session = pool.get('web.user.session')
        return Session.get_user(session)

    @classmethod
    @ModelView.button
    def validate_email(cls, users, from_=None):
        for user in users:
            user.set_email_token()
        cls.save(users)
        _send_email(from_, users, cls.get_email_validation)

    def set_email_token(self, nbytes=None):
        self.email_token = token_hex(nbytes)

    def get_email_validation(self):
        return get_email(
            'web.user.email_validation', self, self.languages)

    def get_email_validation_url(self, url=None):
        if url is None:
            url = config.get('web', 'email_validation_url')
        return _add_params(url, token=self.email_token)

    @classmethod
    def validate_email_url(cls, url):
        parts = urllib.parse.urlsplit(url)
        tokens = filter(
            None, urllib.parse.parse_qs(parts.query).get('token', [None]))
        return cls.validate_email_token(list(tokens))

    @classmethod
    def validate_email_token(cls, tokens):
        users = cls.search([
                ('email_token', 'in', tokens),
                ])
        cls.write(users, {
                'email_valid': True,
                'email_token': None,
                })
        return users

    @classmethod
    @ModelView.button
    def reset_password(cls, users, from_=None):
        now = datetime.datetime.now()

        # Prevent abusive reset
        def reset(user):
            return not (user.reset_password_token_expire
                and user.reset_password_token_expire > now)
        users = list(filter(reset, users))

        for user in users:
            user.set_reset_password_token()
        cls.save(users)
        _send_email(from_, users, cls.get_email_reset_password)

    def set_reset_password_token(self, nbytes=None):
        self.reset_password_token = token_hex(nbytes)
        self.reset_password_token_expire = (
            datetime.datetime.now() + datetime.timedelta(
                seconds=config.getint(
                    'session', 'web_timeout_reset', default=24 * 60 * 60)))

    def clear_reset_password_token(self):
        self.reset_password_token = None
        self.reset_password_token_expire = None

    def get_email_reset_password(self):
        return get_email(
            'web.user.email_reset_password', self, self.languages)

    def get_email_reset_password_url(self, url=None):
        if url is None:
            url = config.get('web', 'reset_password_url')
        return _add_params(
            url, token=self.reset_password_token, email=self.email)

    @classmethod
    def set_password_url(cls, url, password):
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parts.query)
        email = query.get('email', [None])[0]
        token = query.get('token', [None])[0]
        return cls.set_password_token(email, token, password)

    @classmethod
    def set_password_token(cls, email, token, password):
        pool = Pool()
        Attempt = pool.get('web.user.authenticate.attempt')
        email = email.lower()

        # Prevent brute force attack
        Transaction().atexit(
            time.sleep, random.randint(0, 2 ** Attempt.count(email) - 1))

        users = cls.search([
                ('email', '=', email),
                ])
        if users:
            user, = users
            if user.reset_password_token == token:
                now = datetime.datetime.now()
                expire = user.reset_password_token_expire
                user.clear_reset_password_token()
                if expire > now:
                    user.password = password
                    user.save()
                    Attempt.remove(email)
                    return True
        Attempt.add(email)
        return False

    @property
    def languages(self):
        pool = Pool()
        Language = pool.get('ir.lang')
        if self.party and self.party.lang:
            languages = [self.party.lang]
        else:
            languages = Language.search([
                    ('code', '=', Transaction().language),
                    ])
        return languages


class User_PartySecondary(ModelSQL):
    __name__ = 'web.user-party.party.secondary'

    user = fields.Many2One(
        'web.user', "User", required=True, ondelete='CASCADE')
    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE')


class UserAuthenticateAttempt(LoginAttempt):
    __name__ = 'web.user.authenticate.attempt'
    _table = None  # Needed to reset LoginAttempt._table


class UserSession(ModelSQL):
    __name__ = 'web.user.session'
    _rec_name = 'key'

    key = fields.Char("Key", required=True, strip=False)
    user = fields.Many2One(
        'web.user', "User", required=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()
        cls.__rpc__ = {}
        cls._sql_constraints += [
            ('key_unique', Unique(table, table.key),
                'web_user.msg_user_session_key_unique'),
            ]
        cls._sql_indexes.update({
                Index(
                    table,
                    (Coalesce(table.write_date, table.create_date),
                        Index.Range())),
                Index(table, (table.key, Index.Equality(cardinality='high'))),
                })

    @classmethod
    def default_key(cls, nbytes=None):
        return token_hex(nbytes)

    @classmethod
    def add(cls, user):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        cursor.execute(*table.delete(
                where=(
                    Coalesce(table.write_date, table.create_date)
                    < CurrentTimestamp() - cls.timeout())))

        session = cls(user=user)
        session.save()
        return session.key

    @classmethod
    def remove(cls, key):
        sessions = cls.search([
                ('key', '=', key),
                ])
        cls.delete(sessions)

    @classmethod
    def get_user(cls, session):
        transaction = Transaction()
        sessions = cls.search([
                ('key', '=', session),
                ])
        if not sessions:
            return
        session, = sessions
        if not session.expired:
            return session.user
        elif not transaction.readonly:
            cls.delete([session])

    @classmethod
    def timeout(cls):
        return datetime.timedelta(seconds=config.getint(
                'session', 'web_timeout', default=30 * 24 * 60 * 60))

    @property
    def expired(self):
        now = datetime.datetime.now()
        timestamp = self.write_date or self.create_date
        return abs(timestamp - now) > self.timeout()

    @classmethod
    def reset(cls, session):
        sessions = cls.search([
                ('key', '=', session),
                ])
        cls.write(sessions, {})

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create':
            # Ensure to get a different key for each record
            # default methods are called only once
            values.setdefault('key', cls.default_key())
        return values


class EmailValidation(Report):
    __name__ = 'web.user.email_validation'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['extract_params'] = _extract_params
        return context


class EmailResetPassword(Report):
    __name__ = 'web.user.email_reset_password'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['extract_params'] = _extract_params
        expire_delay = (
            records[0].reset_password_token_expire - datetime.datetime.now())
        # Use a precision of minutes
        expire_delay = datetime.timedelta(
            days=expire_delay.days,
            minutes=round(expire_delay.seconds / 60))
        context['expire_delay'] = expire_delay
        return context

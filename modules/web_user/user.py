# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import hashlib
import logging
import random
import string
import time
import urllib.parse
import warnings
from email.header import Header

try:
    import bcrypt
except ImportError:
    bcrypt = None
try:
    import html2text
except ImportError:
    html2text = None
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp
from sql.operators import Equal

from trytond.config import config
from trytond.exceptions import RateLimitException
from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, Unique, Exclude)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.report import Report, get_email
from trytond.transaction import Transaction
from trytond.sendmail import sendmail_transactional

from trytond.ir.session import token_hex
from trytond.res.user import LoginAttempt, CRYPT_CONTEXT

__all__ = ['User', 'UserAuthenticateAttempt', 'UserSession',
    'EmailValidation', 'EmailResetPassword']
logger = logging.getLogger(__name__)


def _send_email(from_, users, email_func):
    if from_ is None:
        from_ = config.get('email', 'from')
    for user in users:
        msg, title = email_func(user)
        msg['From'] = from_
        msg['To'] = user.email
        msg['Subject'] = Header(title, 'utf-8')
        sendmail_transactional(from_, [user.email], msg)


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


class User(DeactivableMixin, ModelSQL, ModelView):
    'Web User'
    __name__ = 'web.user'
    _rec_name = 'email'

    email = fields.Char('E-mail', select=True,
        states={
            'required': Eval('active', True),
            },
        depends=['active'])
    email_valid = fields.Boolean('E-mail Valid')
    email_token = fields.Char('E-mail Token', select=True)
    password_hash = fields.Char('Password Hash')
    password = fields.Function(
        fields.Char('Password'), 'get_password', setter='set_password')
    reset_password_token = fields.Char('Reset Password Token', select=True)
    reset_password_token_expire = fields.Timestamp(
        'Reset Password Token Expire')
    party = fields.Many2One('party.party', 'Party')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('email_exclude',
                Exclude(table, (table.email, Equal),
                    where=table.active == True),
                'web_user.msg_user_email_unique'),
            ]
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
    def __register__(cls, module_name):
        super(User, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 4.6
        table_h.not_null_action('email', 'remove')

        # Migration from 4.6: replace unique by exclude
        table_h.drop_constraint('email_unique')

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

    @classmethod
    def _format_email(cls, users):
        for user in users:
            email = user.email.lower()
            if email != user.email:
                user.email = email
        cls.save(users)

    @classmethod
    def create(cls, vlist):
        users = super(User, cls).create(vlist)
        cls._format_email(users)
        return users

    @classmethod
    def write(cls, *args):
        super(User, cls).write(*args)
        users = sum(args[0:None:2], [])
        cls._format_email(users)

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
                    with Transaction().new_transaction() as transaction:
                        with transaction.set_user(0):
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
            return ''
        return CRYPT_CONTEXT.hash(password)

    @classmethod
    def check_password(cls, password, hash_):
        if not hash_:
            return False, None
        try:
            return CRYPT_CONTEXT.verify_and_update(password, hash_)
        except ValueError:
            hash_method = hash_.split('$', 1)[0]
            warnings.warn(
                "Use deprecated hash method %s" % hash_method,
                DeprecationWarning)
            valid = getattr(cls, 'check_' + hash_method)(password, hash_)
            if valid:
                new_hash = CRYPT_CONTEXT.hash(password)
            else:
                new_hash = None
            return valid, new_hash

    @classmethod
    def hash_sha1(cls, password):
        salt = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        salted_password = password + salt
        if isinstance(salted_password, str):
            salted_password = salted_password.encode('utf-8')
        hash_ = hashlib.sha1(salted_password).hexdigest()
        return '$'.join(['sha1', hash_, salt])

    @classmethod
    def check_sha1(cls, password, hash_):
        if isinstance(password, str):
            password = password.encode('utf-8')
        hash_method, hash_, salt = hash_.split('$', 2)
        salt = salt or ''
        if isinstance(salt, str):
            salt = salt.encode('utf-8')
        assert hash_method == 'sha1'
        return hash_ == hashlib.sha1(password + salt).hexdigest()

    @classmethod
    def hash_bcrypt(cls, password):
        if isinstance(password, str):
            password = password.encode('utf-8')
        hash_ = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        return '$'.join(['bcrypt', hash_])

    @classmethod
    def check_bcrypt(cls, password, hash_):
        if isinstance(password, str):
            password = password.encode('utf-8')
        hash_method, hash_ = hash_.split('$', 1)
        if isinstance(hash_, str):
            hash_ = hash_.encode('utf-8')
        assert hash_method == 'bcrypt'
        return hash_ == bcrypt.hashpw(password, hash_)

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
        return bool(users)

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
        Transaction().atexit(time.sleep, 2 ** Attempt.count(email) - 1)

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


class UserAuthenticateAttempt(LoginAttempt):
    'Web User Authenticate Attempt'
    __name__ = 'web.user.authenticate.attempt'
    _table = None  # Needed to reset LoginAttempt._table


class UserSession(ModelSQL):
    'Web User Session'
    __name__ = 'web.user.session'
    _rec_name = 'key'

    key = fields.Char('Key', required=True, select=True)
    user = fields.Many2One(
        'web.user', 'User', required=True, select=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(UserSession, cls).__setup__()
        table = cls.__table__()
        cls.__rpc__ = {}
        cls._sql_constraints += [
            ('key_unique', Unique(table, table.key),
                'web_user.msg_user_session_key_unique'),
            ]

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
                    - CurrentTimestamp()) > cls.timeout()))

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
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            # Ensure to get a different key for each record
            # default methods are called only once
            values.setdefault('key', cls.default_key())
        return super(UserSession, cls).create(vlist)


class EmailValidation(Report):
    __name__ = 'web.user.email_validation'

    @classmethod
    def get_context(cls, records, data):
        context = super(EmailValidation, cls).get_context(records, data)
        context['extract_params'] = _extract_params
        return context


class EmailResetPassword(Report):
    __name__ = 'web.user.email_reset_password'

    @classmethod
    def get_context(cls, records, data):
        context = super(EmailResetPassword, cls).get_context(records, data)
        context['extract_params'] = _extract_params
        return context

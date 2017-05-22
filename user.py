# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import hashlib
import random
import string
import time
import urllib
import urlparse
import uuid
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

from trytond.config import config
from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.sendmail import sendmail_transactional

from trytond.res.user import LoginAttempt

__all__ = ['User', 'UserAuthenticateAttempt', 'UserSession',
    'EmailValidation', 'EmailResetPassword']


def _send_email(from_, users, email_func):
    if from_ is None:
        from_ = config.get('email', 'from')
    for user in users:
        msg, title = email_func(user)
        msg['From'] = from_
        msg['To'] = user.email
        msg['Subject'] = Header(title, 'utf-8')
        sendmail_transactional(from_, [user.email], msg)


def _get_email_template(report, user):
    pool = Pool()
    Report = pool.get(report, type='report')
    language = user.party.lang.code if user.party and user.party.lang else None
    with Transaction().set_context(language=language):
        ext, content, _, title = Report.execute([user.id], {})
    if ext == 'html' and html2text:
        h = html2text.HTML2Text()
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(h.handle(content), 'plain', _charset='utf-8'))
        msg.attach(MIMEText(content, ext, _charset='utf-8'))
    else:
        msg = MIMEText(content, ext, _charset='utf-8')
    return msg, title


def _add_params(url, **params):
    parts = urlparse.urlsplit(url)
    query = urlparse.parse_qsl(parts.query)
    for key, value in sorted(params.items()):
        query.append((key, value))
    parts = list(parts)
    parts[3] = urllib.urlencode(query)
    return urlparse.urlunsplit(parts)


class User(ModelSQL, ModelView):
    'Web User'
    __name__ = 'web.user'
    _rec_name = 'email'

    email = fields.Char('E-mail', required=True, select=True)
    email_valid = fields.Boolean('E-mail Valid')
    email_token = fields.Char('E-mail Token', select=True)
    password_hash = fields.Char('Password Hash')
    password = fields.Function(
        fields.Char('Password'), 'get_password', setter='set_password')
    reset_password_token = fields.Char('Reset Password Token', select=True)
    reset_password_token_expire = fields.Timestamp(
        'Reset Password Token Expire')
    active = fields.Boolean('Active')
    party = fields.Many2One('party.party', 'Party')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('email_unique', Unique(table, table.email),
                'E-mail must be unique'),
            ]
        cls._buttons.update({
                'validate_email': {
                    'readonly': Eval('email_valid', False),
                    },
                'reset_password': {
                    'readonly': ~Eval('email_valid', False),
                    },
                })

    @staticmethod
    def default_active():
        return True

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
    def authenticate(cls, email, password):
        pool = Pool()
        Attempt = pool.get('web.user.authenticate.attempt')

        # Prevent brute force attack
        time.sleep(2 ** Attempt.count(email) - 1)

        users = cls.search([('email', '=', email)])
        if users:
            user, = users
            if cls.check_password(password, user.password_hash):
                Attempt.remove(email)
                return user
        Attempt.add(email)

    @staticmethod
    def hash_method():
        return 'bcrypt' if bcrypt else 'sha1'

    @classmethod
    def hash_password(cls, password):
        '''Hash given password in the form
        <hash_method>$<password>$<salt>...'''
        if not password:
            return ''
        return getattr(cls, 'hash_' + cls.hash_method())(password)

    @classmethod
    def check_password(cls, password, hash_):
        if not hash_:
            return False
        hash_method = hash_.split('$', 1)[0]
        return getattr(cls, 'check_' + hash_method)(password, hash_)

    @classmethod
    def hash_sha1(cls, password):
        salt = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        salted_password = password + salt
        if isinstance(salted_password, unicode):
            salted_password = salted_password.encode('utf-8')
        hash_ = hashlib.sha1(salted_password).hexdigest()
        return '$'.join(['sha1', hash_, salt])

    @classmethod
    def check_sha1(cls, password, hash_):
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        hash_method, hash_, salt = hash_.split('$', 2)
        salt = salt or ''
        if isinstance(salt, unicode):
            salt = salt.encode('utf-8')
        assert hash_method == 'sha1'
        return hash_ == hashlib.sha1(password + salt).hexdigest()

    @classmethod
    def hash_bcrypt(cls, password):
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        hash_ = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        return '$'.join(['bcrypt', hash_])

    @classmethod
    def check_bcrypt(cls, password, hash_):
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        hash_method, hash_ = hash_.split('$', 1)
        if isinstance(hash_, unicode):
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

    def set_email_token(self):
        self.email_token = uuid.uuid4().hex

    def get_email_validation(self):
        return _get_email_template('web.user.email_validation', self)

    def get_email_validation_url(self, url=None):
        if url is None:
            url = config.get('web', 'email_validation_url')
        return _add_params(url, token=self.email_token)

    @classmethod
    def validate_email_url(cls, url):
        parts = urlparse.urlsplit(url)
        tokens = filter(
            None, urlparse.parse_qs(parts.query).get('token', [None]))
        return cls.validate_email_token(tokens)

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
        users = filter(reset, users)

        for user in users:
            user.set_reset_password_token()
        cls.save(users)
        _send_email(from_, users, cls.get_email_reset_password)

    def set_reset_password_token(self):
        self.reset_password_token = uuid.uuid4().hex
        self.reset_password_token_expire = (
            datetime.datetime.now() + datetime.timedelta(
                seconds=config.getint(
                    'session', 'web_timeout_reset', default=24 * 60 * 60)))

    def clear_reset_password_token(self):
        self.reset_password_token = None
        self.reset_password_token_expire = None

    def get_email_reset_password(self):
        return _get_email_template('web.user.email_reset_password', self)

    def get_email_reset_password_url(self, url=None):
        if url is None:
            url = config.get('web', 'reset_password_url')
        return _add_params(
            url, token=self.reset_password_token, email=self.email)

    @classmethod
    def set_password_url(cls, url, password):
        parts = urlparse.urlsplit(url)
        query = urlparse.parse_qs(parts.query)
        email = query.get('email', [None])[0]
        token = query.get('token', [None])[0]
        return cls.set_password_token(email, token, password)

    @classmethod
    def set_password_token(cls, email, token, password):
        pool = Pool()
        Attempt = pool.get('web.user.authenticate.attempt')

        # Prevent brute force attack
        time.sleep(2 ** Attempt.count(email) - 1)

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
            ('key_unique', Unique(table, table.key), 'Key must be unique'),
            ]

    @classmethod
    def default_key(cls):
        return uuid.uuid4().hex

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
    def get_user(cls, session):
        sessions = cls.search([
                ('key', '=', session),
                ])
        if not sessions:
            return
        session, = sessions
        if not session.expired:
            return session.user
        else:
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


class EmailValidation(Report):
    __name__ = 'web.user.email_validation'


class EmailResetPassword(Report):
    __name__ = 'web.user.email_reset_password'

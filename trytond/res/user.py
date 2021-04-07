# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"User"

import copy
import string
import random
import hashlib
import time
import datetime
import logging
import uuid
import mmap
import re
try:
    import secrets
except ImportError:
    secrets = None
import ipaddress
import warnings
from email.header import Header
from functools import wraps
from itertools import groupby
from operator import attrgetter
from ast import literal_eval

from sql import Literal, Null
from sql.functions import CurrentTimestamp
from sql.conditionals import Coalesce, Case
from sql.aggregate import Count
from sql.operators import Concat

from passlib.context import CryptContext

try:
    import bcrypt
except ImportError:
    bcrypt = None

from trytond.cache import Cache
from trytond.config import config
from trytond.exceptions import LoginException, RateLimitException
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, Workflow, DeactivableMixin, fields, Unique,
    avatar_mixin)
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder, Eval, Bool
from trytond.report import Report, get_email
from trytond.rpc import RPC
from trytond.sendmail import sendmail_transactional
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.url import host, http_host
from trytond.wizard import Wizard, StateView, Button, StateTransition

logger = logging.getLogger(__name__)
_has_password = 'password' in re.split('[,+]', config.get(
    'session', 'authentications', default='password'))

passlib_path = config.get('password', 'passlib')
if passlib_path:
    CRYPT_CONTEXT = CryptContext.from_path(passlib_path)
else:
    schemes = ['pbkdf2_sha512']
    if bcrypt:
        schemes.insert(0, 'bcrypt')
    CRYPT_CONTEXT = CryptContext(schemes=schemes)


def gen_password(length=8):
    alphabet = string.ascii_letters + string.digits
    if secrets:
        choice = secrets.choice
    else:
        sysrand = random.SystemRandom()
        choice = sysrand.choice
    return ''.join(choice(alphabet) for _ in range(length))


def _send_email(from_, users, email_func):
    from_cfg = config.get('email', 'from')
    for user in users:
        if not user.email:
            logger.info("Missing address for '%s' to send email", user.login)
            continue
        msg, title = email_func(user)
        msg['From'] = from_ or from_cfg
        msg['To'] = user.email
        msg['Subject'] = Header(title, 'utf-8')
        sendmail_transactional(from_cfg, [user.email], msg)


class PasswordError(UserError):
    pass


class DeleteError(UserError):
    pass


class User(avatar_mixin(100, 'login'), DeactivableMixin, ModelSQL, ModelView):
    "User"
    __name__ = "res.user"
    name = fields.Char('Name', select=True)
    login = fields.Char('Login', required=True)
    password_hash = fields.Char('Password Hash')
    password = fields.Function(fields.Char(
            "Password",
            states={
                'invisible': not _has_password,
                }),
        getter='get_password', setter='set_password')
    password_reset = fields.Char(
        "Reset Password",
        states={
            'invisible': not _has_password,
            })
    password_reset_expire = fields.Timestamp(
        "Reset Password Expire",
        states={
            'required': Bool(Eval('password_reset')),
            'invisible': not _has_password,
            },
        depends=['password_reset'])
    signature = fields.Text('Signature')
    menu = fields.Many2One('ir.action', 'Menu Action',
        domain=[('usage', '=', 'menu')], required=True)
    pyson_menu = fields.Function(fields.Char('PySON Menu'), 'get_pyson_menu')
    actions = fields.Many2Many('res.user-ir.action', 'user', 'action',
        'Actions', help='Actions that will be run at login.',
        size=5)
    groups = fields.Many2Many('res.user-res.group',
       'user', 'group', 'Groups')
    applications = fields.One2Many(
        'res.user.application', 'user', "Applications")
    language = fields.Many2One('ir.lang', 'Language',
        domain=['OR',
            ('translatable', '=', True),
            ])
    language_direction = fields.Function(fields.Char('Language Direction'),
            'get_language_direction')
    email = fields.Char('Email')
    status_bar = fields.Function(fields.Char('Status Bar'), 'get_status_bar')
    avatar_badge_url = fields.Function(
        fields.Char("Avatar Badge URL"), 'get_avatar_badge_url')
    warnings = fields.One2Many('res.user.warning', 'user', 'Warnings')
    sessions = fields.Function(fields.Integer('Sessions'),
            'get_sessions')
    _get_preferences_cache = Cache('res_user.get_preferences')
    _get_groups_cache = Cache('res_user.get_groups', context=False)
    _get_login_cache = Cache('res_user._get_login', context=False)

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls.__rpc__.update({
                'get_preferences': RPC(check_access=False),
                'set_preferences': RPC(
                    readonly=False, check_access=False, fresh_session=True),
                'get_preferences_fields_view': RPC(check_access=False),
                })
        table = cls.__table__()
        cls._sql_constraints += [
            ('login_key', Unique(table, table.login),
                'You can not have two users with the same login!')
        ]
        cls._buttons.update({
                'reset_password': {
                    'invisible': ~Eval('email', True) | (not _has_password),
                    },
                })
        cls._preferences_fields = [
            'name',
            'password',
            'email',
            'signature',
            'menu',
            'pyson_menu',
            'actions',
            'status_bar',
            'avatar',
            'avatar_url',
            'avatar_badge_url',
            'warnings',
            'applications',
        ]
        cls._context_fields = [
            'language',
            'language_direction',
            'groups',
        ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        model_data = ModelData.__table__()
        cursor = Transaction().connection.cursor()
        super(User, cls).__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 3.0
        if table.column_exist('password') and table.column_exist('salt'):
            sqltable = cls.__table__()
            password_hash_new = Concat('sha1$', Concat(sqltable.password,
                Concat('$', Coalesce(sqltable.salt, ''))))
            cursor.execute(*sqltable.update(
                columns=[sqltable.password_hash],
                values=[password_hash_new]))
            table.drop_column('password')
            table.drop_column('salt')

        # Migration from 4.2: Remove required on name
        table.not_null_action('name', action='remove')

        # Migration from 5.6: Set noupdate to admin
        cursor.execute(*model_data.update(
                [model_data.noupdate], [True],
                where=(model_data.model == cls.__name__)
                & (model_data.module == 'res')
                & (model_data.fs_id == 'user_admin')))

    @staticmethod
    def default_menu():
        pool = Pool()
        Action = pool.get('ir.action')
        actions = Action.search([
            ('usage', '=', 'menu'),
            ], limit=1)
        if actions:
            return actions[0].id
        return None

    def get_pyson_menu(self, name):
        encoder = PYSONEncoder()
        return encoder.encode(self.menu.get_action_value())

    def get_language_direction(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if self.language:
            return self.language.direction
        else:
            return Lang.default_direction()

    def get_status_bar(self, name):
        return self.name

    def get_avatar_badge_url(self, name):
        pass

    def get_password(self, name):
        return 'x' * 10

    @classmethod
    def set_password(cls, users, name, value):
        if value == 'x' * 10:
            return

        if Transaction().user and value:
            cls.validate_password(value, users)

        to_write = []
        for user in users:
            to_write.extend([[user], {
                        'password_hash': cls.hash_password(value),
                        }])
        cls.write(*to_write)

    @classmethod
    def validate_password(cls, password, users):
        password_b = password
        if isinstance(password, str):
            password_b = password.encode('utf-8')
        length = config.getint('password', 'length', default=0)
        if length > 0:
            if len(password_b) < length:
                raise PasswordError(gettext('res.msg_password_length'))
        path = config.get('password', 'forbidden', default=None)
        if path:
            with open(path, 'r') as f:
                forbidden = mmap.mmap(
                    f.fileno(), 0, access=mmap.ACCESS_READ)
                if forbidden.find(password_b) >= 0:
                    raise PasswordError(gettext('res.msg_password_forbidden'))
        entropy = config.getfloat('password', 'entropy', default=0)
        if entropy:
            if len(set(password)) / len(password) < entropy:
                raise PasswordError(gettext('res.msg_password_entropy'))
        for user in users:
            # Use getattr to allow to use non User instances
            for test, message in [
                    (getattr(user, 'name', ''), 'res.msg_password_name'),
                    (getattr(user, 'login', ''), 'res.msg_password_login'),
                    (getattr(user, 'email', ''), 'res.msg_password_email'),
                    ]:
                if test and password.lower() == test.lower():
                    raise PasswordError(gettext(message))

    @classmethod
    @ModelView.button
    def reset_password(cls, users, length=8, from_=None):
        for user in users:
            user.password_reset = gen_password(length=length)
            user.password_reset_expire = (
                datetime.datetime.now() + datetime.timedelta(
                    seconds=config.getint('password', 'reset_timeout')))
            user.password = None
        cls.save(users)
        _send_email(from_, users, cls.get_email_reset_password)

    def get_email_reset_password(self):
        return get_email(
            'res.user.email_reset_password', self, self.languages)

    @property
    def languages(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if self.language:
            languages = [self.language]
        else:
            languages = Lang.search([
                    ('code', '=', Transaction().language),
                    ])
        return languages

    @staticmethod
    def get_sessions(users, name):
        Session = Pool().get('ir.session')
        now = datetime.datetime.now()
        timeout = datetime.timedelta(
            seconds=config.getint('session', 'max_age'))
        result = dict((u.id, 0) for u in users)
        with Transaction().set_user(0):
            for sub_ids in grouped_slice(users):
                sessions = Session.search([
                        ('create_uid', 'in', sub_ids),
                        ], order=[('create_uid', 'ASC')])

                def filter_(session):
                    timestamp = session.write_date or session.create_date
                    return abs(timestamp - now) < timeout
                result.update(dict((i, len(list(g)))
                        for i, g in groupby(filter(filter_, sessions),
                            attrgetter('create_uid.id'))))
        return result

    @staticmethod
    def _convert_vals(vals):
        vals = vals.copy()
        pool = Pool()
        Action = pool.get('ir.action')
        if 'menu' in vals:
            vals['menu'] = Action.get_action_id(vals['menu'])
        return vals

    @classmethod
    def read(cls, ids, fields_names):
        result = super(User, cls).read(ids, fields_names)
        if not fields_names or 'password_hash' in fields_names:
            for values in result:
                values['password_hash'] = None
        return result

    @classmethod
    def create(cls, vlist):
        vlist = [cls._convert_vals(vals) for vals in vlist]
        res = super(User, cls).create(vlist)
        # Restart the cache for _get_login
        cls._get_login_cache.clear()
        return res

    @classmethod
    def write(cls, users, values, *args):
        pool = Pool()
        Session = pool.get('ir.session')
        UserDevice = pool.get('res.user.device')

        actions = iter((users, values) + args)
        all_users = []
        session_to_clear = []
        users_to_clear = []
        args = []
        for users, values in zip(actions, actions):
            all_users += users
            args.extend((users, cls._convert_vals(values)))

            if 'password' in values:
                session_to_clear += users
                users_to_clear += [u.login for u in users]

        super(User, cls).write(*args)

        Session.clear(session_to_clear)
        UserDevice.clear(users_to_clear)

        # Clean cursor cache as it could be filled by domain_get
        for cache in Transaction().cache.values():
            if cls.__name__ in cache:
                for user in all_users:
                    cache[cls.__name__].pop(user.id, None)
        # Restart the cache for domain_get method
        pool = Pool()
        pool.get('ir.rule')._domain_get_cache.clear()
        # Restart the cache for get_groups
        cls._get_groups_cache.clear()
        # Restart the cache for _get_login
        cls._get_login_cache.clear()
        # Restart the cache for get_preferences
        cls._get_preferences_cache.clear()
        # Restart the cache of check
        pool.get('ir.model.access')._get_access_cache.clear()
        # Restart the cache of check
        pool.get('ir.model.field.access')._get_access_cache.clear()
        # Restart the cache
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def delete(cls, users):
        raise DeleteError(gettext('res.msg_user_delete_forbidden'))

    def get_rec_name(self, name):
        return self.name if self.name else self.login

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('login',) + tuple(clause[1:]),
            ('name',) + tuple(clause[1:]),
            ]

    @classmethod
    def copy(cls, users, default=None):
        if default is None:
            default = {}
        default = default.copy()

        default['password'] = ''
        default.setdefault('warnings')
        default.setdefault('applications')

        new_users = []
        for user in users:
            default['login'] = user.login + ' (copy)'
            new_user, = super(User, cls).copy([user], default)
            new_users.append(new_user)
        return new_users

    @classmethod
    def _get_preferences(cls, user, context_only=False):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Action = pool.get('ir.action')
        Config = pool.get('ir.configuration')
        ConfigItem = pool.get('ir.module.config_wizard.item')

        res = {}
        if context_only:
            fields = cls._context_fields
        else:
            fields = cls._preferences_fields + cls._context_fields
        for field in fields:
            if cls._fields[field]._type in ('many2one',):
                if field == 'language':
                    if user.language:
                        res['language'] = user.language.code
                    else:
                        res['language'] = Config.get_language()
                else:
                    if getattr(user, field):
                        res[field] = getattr(user, field).id
                        res[field + '.rec_name'] = \
                            getattr(user, field).rec_name
            elif cls._fields[field]._type in ('one2many', 'many2many'):
                res[field] = [x.id for x in getattr(user, field)]
                admin_id = ModelData.get_id('res.user_admin')
                if field == 'actions' and user.id == admin_id:
                    config_wizard_id = ModelData.get_id('ir',
                        'act_module_config_wizard')
                    action_id = Action.get_action_id(config_wizard_id)
                    if action_id in res[field]:
                        res[field].remove(action_id)
                    if ConfigItem.search([
                                ('state', '=', 'open'),
                                ]):
                        res[field].insert(0, action_id)
            else:
                res[field] = getattr(user, field)

        if user.language:
            date = user.language.date
            for i, j in [('%a', ''), ('%A', ''), ('%b', '%m'), ('%B', '%m'),
                    ('%j', ''), ('%U', ''), ('%w', ''), ('%W', '')]:
                date = date.replace(i, j)
            res['locale'] = {
                'date': date,
                'grouping': literal_eval(user.language.grouping),
                'decimal_point': user.language.decimal_point,
                'thousands_sep': user.language.thousands_sep,
            }
        return res

    @classmethod
    def get_preferences(cls, context_only=False):
        key = (Transaction().user, context_only)
        preferences = cls._get_preferences_cache.get(key)
        if preferences is not None:
            return preferences.copy()
        user = Transaction().user
        user = cls(user)
        preferences = cls._get_preferences(user, context_only=context_only)
        cls._get_preferences_cache.set(key, preferences)
        return preferences.copy()

    @classmethod
    def set_preferences(cls, values):
        '''
        Set user preferences
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        values_clean = values.copy()
        fields = cls._preferences_fields + cls._context_fields
        user_id = Transaction().user
        user = cls(user_id)
        for field in values:
            if field not in fields or field == 'groups':
                del values_clean[field]
            if field == 'language':
                langs = Lang.search([
                    ('code', '=', values['language']),
                    ])
                if langs:
                    values_clean['language'] = langs[0].id
                else:
                    del values_clean['language']
        # Set new context to write as validation could depend on it
        context = {}
        for name in cls._context_fields:
            if name in values:
                context[name] = values[name]
        with Transaction().set_context(context):
            cls.write([user], values_clean)

    @classmethod
    def get_preferences_fields_view(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Lang = pool.get('ir.lang')
        Action = pool.get('ir.action')

        view_id = ModelData.get_id('res', 'user_view_form_preferences')
        res = cls.fields_view_get(view_id=view_id)
        res = copy.deepcopy(res)
        for field in res['fields']:
            if field not in ('groups', 'language_direction'):
                res['fields'][field]['readonly'] = False
            else:
                res['fields'][field]['readonly'] = True

        def convert2selection(definition, name):
            del definition[name]['relation']
            del definition[name]['domain']
            definition[name]['type'] = 'selection'
            selection = []
            definition[name]['selection'] = selection
            return selection

        if 'language' in res['fields']:
            selection = convert2selection(res['fields'], 'language')
            langs = Lang.search(cls.language.domain)
            lang_ids = [l.id for l in langs]
            with Transaction().set_context(translate_name=True):
                for lang in Lang.browse(lang_ids):
                    selection.append((lang.code, lang.name))
        if 'action' in res['fields']:
            selection = convert2selection(res['fields'], 'action')
            selection.append((None, ''))
            actions = Action.search([])
            for action in actions:
                selection.append((action.id, action.rec_name))
        if 'menu' in res['fields']:
            selection = convert2selection(res['fields'], 'menu')
            actions = Action.search([
                    ('usage', '=', 'menu'),
                    ])
            for action in actions:
                selection.append((action.id, action.rec_name))
        return res

    @classmethod
    def get_groups(cls, name=None):
        '''
        Return a list of all group ids for the user
        '''
        user = Transaction().user
        groups = cls._get_groups_cache.get(user)
        if groups is not None:
            return groups
        pool = Pool()
        UserGroup = pool.get('res.user-res.group')
        cursor = Transaction().connection.cursor()
        user_group = UserGroup.user_group_all_table()
        cursor.execute(*user_group.select(
                user_group.group,
                where=user_group.user == user))
        groups = [g for g, in cursor]
        cls._get_groups_cache.set(user, groups)
        return groups

    @classmethod
    def _get_login(cls, login):
        result = cls._get_login_cache.get(login)
        if result:
            return result
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        cursor.execute(*table.select(table.id, table.password_hash,
                Case(
                    (table.password_reset_expire > CurrentTimestamp(),
                        table.password_reset),
                    else_=None),
                where=(table.login == login)
                & (table.active == Literal(True))))
        result = cursor.fetchone() or (None, None, None)
        cls._get_login_cache.set(login, result)
        return result

    @classmethod
    def get_login(cls, login, parameters):
        '''
        Return user id if password matches
        '''
        pool = Pool()
        LoginAttempt = pool.get('res.user.login.attempt')
        UserDevice = pool.get('res.user.device')

        count_ip = LoginAttempt.count_ip()
        if count_ip > config.getint(
                'session', 'max_attempt_ip_network', default=300):
            # Do not add attempt as the goal is to prevent flooding
            raise RateLimitException()
        device_cookie = UserDevice.get_valid_cookie(
            login, parameters.get('device_cookie'))
        count = LoginAttempt.count(login, device_cookie)
        if count > config.getint('session', 'max_attempt', default=5):
            LoginAttempt.add(login, device_cookie)
            raise RateLimitException()
        Transaction().atexit(time.sleep, random.randint(0, 2 ** count - 1))
        for methods in config.get(
                'session', 'authentications', default='password').split(','):
            user_ids = set()
            for method in methods.split('+'):
                try:
                    func = getattr(cls, '_login_%s' % method)
                except AttributeError:
                    logger.info('Missing login method: %s', method)
                    break
                user_ids.add(func(login, parameters))
                if len(user_ids) != 1 or not all(user_ids):
                    break
            if len(user_ids) == 1 and all(user_ids):
                LoginAttempt.remove(login, device_cookie)
                return user_ids.pop()
        LoginAttempt.add(login, device_cookie)

    @classmethod
    def _login_password(cls, login, parameters):
        if 'password' not in parameters:
            msg = gettext('res.msg_user_password', login=login)
            raise LoginException('password', msg, type='password')
        user_id, password_hash, password_reset = cls._get_login(login)
        if user_id and password_hash:
            password = parameters['password']
            valid, new_hash = cls.check_password(password, password_hash)
            if valid:
                if new_hash:
                    logger.info("Update password hash for %s", user_id)
                    with Transaction().new_transaction() as transaction:
                        with transaction.set_user(0):
                            cls.write([cls(user_id)], {
                                    'password_hash': new_hash,
                                    })
                return user_id
        elif user_id and password_reset:
            if password_reset == parameters['password']:
                return user_id

    @classmethod
    def hash_password(cls, password):
        '''Hash given password in the form
        <hash_method>$<password>$<salt>...'''
        if not password:
            return None
        return CRYPT_CONTEXT.hash(password)

    @classmethod
    def check_password(cls, password, hash_):
        if not hash_:
            return False
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
        salt = gen_password()
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


class LoginAttempt(ModelSQL):
    """Login Attempt

    This class is separated from the res.user one in order to prevent locking
    the res.user table when in a long running process.
    """
    __name__ = 'res.user.login.attempt'
    login = fields.Char('Login', size=512)
    device_cookie = fields.Char("Device Cookie")
    ip_address = fields.Char("IP Address")
    ip_network = fields.Char("IP Network")

    @staticmethod
    def delay():
        return (datetime.datetime.now()
            - datetime.timedelta(seconds=config.getint('session', 'timeout')))

    @classmethod
    def ipaddress(cls):
        context = Transaction().context
        ip_address = ''
        ip_network = ''
        if context.get('_request') and context['_request'].get('remote_addr'):
            ip_address = ipaddress.ip_address(
                str(context['_request']['remote_addr']))
            prefix = config.getint(
                'session', 'ip_network_%s' % ip_address.version)
            ip_network = ipaddress.ip_network(
                str(context['_request']['remote_addr']))
            ip_network = ip_network.supernet(new_prefix=prefix)
        return ip_address, ip_network

    def _login_size(func):
        @wraps(func)
        def wrapper(cls, login, *args, **kwargs):
            return func(cls, login[:cls.login.size], *args, **kwargs)
        return wrapper

    @classmethod
    @_login_size
    def add(cls, login, device_cookie=None):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        cursor.execute(*table.delete(where=table.create_date < cls.delay()))

        ip_address, ip_network = cls.ipaddress()
        cls.create([{
                    'login': login,
                    'device_cookie': device_cookie,
                    'ip_address': str(ip_address),
                    'ip_network': str(ip_network),
                    }])

    @classmethod
    @_login_size
    def remove(cls, login, device_cookie=None):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        cursor.execute(*table.delete(
                where=(table.login == login)
                & (table.device_cookie == device_cookie)
                ))

    @classmethod
    @_login_size
    def count(cls, login, device_cookie=None):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        cursor.execute(*table.select(Count(Literal('*')),
                where=(table.login == login)
                & (table.device_cookie == device_cookie)
                & (table.create_date >= cls.delay())))
        return cursor.fetchone()[0]

    @classmethod
    def count_ip(cls):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        _, ip_network = cls.ipaddress()
        cursor.execute(*table.select(Count(Literal('*')),
                where=(table.ip_network == str(ip_network))
                & (table.create_date >= cls.delay())))
        return cursor.fetchone()[0]

    del _login_size


class UserDevice(ModelSQL):
    "User Device"
    __name__ = 'res.user.device'

    login = fields.Char("Login", required=True)
    cookie = fields.Char("Cookie", readonly=True, required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'renew': RPC(readonly=False),
                })

    @classmethod
    def get_valid_cookie(cls, login, cookie):
        try:
            device, = cls.search([
                    ('login', '=', login),
                    ('cookie', '=', cookie),
                    ], limit=1)
        except ValueError:
            return None

        return device.cookie

    @classmethod
    def renew(cls, current_cookie):
        pool = Pool()
        User = pool.get('res.user')

        user = User(Transaction().user)
        new_cookie = uuid.uuid4().hex
        current_devices = cls.search([
                    ('login', '=', user.login),
                    ('cookie', '=', current_cookie),
                    ])
        if current_devices:
            cls.write(current_devices, {
                    'cookie': new_cookie
                    })
        else:
            cls.create([{
                        'login': user.login,
                        'cookie': new_cookie,
                        }])
        return new_cookie

    @classmethod
    def clear(cls, logins):
        for sub_logins in grouped_slice(logins):
            cls.delete(cls.search([
                        ('login', 'in', list(sub_logins)),
                        ]))


class UserAction(ModelSQL):
    'User - Action'
    __name__ = 'res.user-ir.action'
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=True,
        required=True)
    action = fields.Many2One('ir.action', 'Action', ondelete='CASCADE',
        select=True, required=True)

    @staticmethod
    def _convert_values(values):
        pool = Pool()
        Action = pool.get('ir.action')
        values = values.copy()
        if values.get('action'):
            values['action'] = Action.get_action_id(values['action'])
        return values

    @classmethod
    def create(cls, vlist):
        vlist = [cls._convert_values(values) for values in vlist]
        return super(UserAction, cls).create(vlist)

    @classmethod
    def write(cls, records, values, *args):
        actions = iter((records, values) + args)
        args = []
        for records, values in zip(actions, actions):
            args.extend((records, cls._convert_values(values)))
        super(UserAction, cls).write(*args)


class UserGroup(ModelSQL):
    'User - Group'
    __name__ = 'res.user-res.group'
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=True,
            required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def create(cls, vlist):
        records = super().create(vlist)
        pool = Pool()
        # Restart the cache on the domain_get method
        pool.get('ir.rule')._domain_get_cache.clear()
        # Restart the cache for get_groups
        pool.get('res.user')._get_groups_cache.clear()
        # Restart the cache for get_preferences
        pool.get('res.user')._get_preferences_cache.clear()
        # Restart the cache for model access and view
        pool.get('ir.model.access')._get_access_cache.clear()
        pool.get('ir.model.field.access')._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()
        return records

    @classmethod
    def write(cls, groups, values, *args):
        super().write(groups, values, *args)
        pool = Pool()
        # Restart the cache on the domain_get method
        pool.get('ir.rule')._domain_get_cache.clear()
        # Restart the cache for get_groups
        pool.get('res.user')._get_groups_cache.clear()
        # Restart the cache for get_preferences
        pool.get('res.user')._get_preferences_cache.clear()
        # Restart the cache for model access and view
        pool.get('ir.model.access')._get_access_cache.clear()
        pool.get('ir.model.field.access')._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def delete(cls, groups):
        super().delete(groups)
        pool = Pool()
        # Restart the cache on the domain_get method
        pool.get('ir.rule')._domain_get_cache.clear()
        # Restart the cache for get_groups
        pool.get('res.user')._get_groups_cache.clear()
        # Restart the cache for get_preferences
        pool.get('res.user')._get_preferences_cache.clear()
        # Restart the cache for model access and view
        pool.get('ir.model.access')._get_access_cache.clear()
        pool.get('ir.model.field.access')._get_access_cache.clear()
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def user_group_all_table(cls):
        pool = Pool()
        Group = pool.get('res.group')
        user_group = cls.__table__()
        group_parents = Group.group_parent_all_cte()

        return (user_group
            .join(group_parents,
                condition=user_group.group == group_parents.id)
            .select(
                user_group.user.as_('user'),
                group_parents.parent.as_('group'),
                where=group_parents.parent != Null,
                with_=group_parents))


class Warning_(ModelSQL, ModelView):
    'User Warning'
    __name__ = 'res.user.warning'

    user = fields.Many2One('res.user', 'User', required=True, select=True)
    name = fields.Char('Name', required=True, select=True)
    always = fields.Boolean('Always')

    @classmethod
    def check(cls, warning_name):
        transaction = Transaction()
        user = transaction.user
        context = transaction.context
        if not user or context.get('_skip_warnings'):
            return False
        warnings = cls.search([
            ('user', '=', user),
            ('name', '=', warning_name),
            ])
        if not warnings:
            return True
        cls.delete([x for x in warnings if not x.always])
        return False


class UserApplication(Workflow, ModelSQL, ModelView):
    "User Application"
    __name__ = 'res.user.application'
    _rec_name = 'key'

    key = fields.Char("Key", required=True, select=True)
    user = fields.Many2One('res.user', "User", select=True)
    application = fields.Selection([], "Application")
    state = fields.Selection([
            ('requested', "Requested"),
            ('validated', "Validated"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True)

    @classmethod
    def __setup__(cls):
        super(UserApplication, cls).__setup__()
        cls._transitions |= set((
                ('requested', 'validated'),
                ('requested', 'cancelled'),
                ('validated', 'cancelled'),
                ))
        cls._buttons.update({
                'validate_': {
                    'invisible': Eval('state') != 'requested',
                    'depends': ['state'],
                    },
                'cancel': {
                    'invisible': Eval('state') == 'cancelled',
                    'depends': ['state'],
                    },
                })
        # Do not cache default_key as it depends on time
        cls.__rpc__['default_get'].cache = None

    @classmethod
    def default_key(cls):
        return ''.join(uuid.uuid4().hex for _ in range(4))

    @classmethod
    def default_state(cls):
        return 'requested'

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_(cls, applications):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, applications):
        pass

    @classmethod
    def count(cls, user_id):
        return cls.search([
                ('user', '=', user_id),
                ('state', '=', 'requested'),
                ], count=True)

    @classmethod
    def check(cls, key, application):
        records = cls.search([
                ('key', '=', key),
                ('application', '=', application),
                ('state', '=', 'validated'),
                ], limit=1)
        if not records:
            return
        record, = records
        return record

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        User = pool.get('res.user')
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            # Ensure we get a different key for each record
            # default methods are called only once
            values.setdefault('key', cls.default_key())
        applications = super(UserApplication, cls).create(vlist)
        User._get_preferences_cache.clear()
        return applications

    @classmethod
    def write(cls, *args):
        pool = Pool()
        User = pool.get('res.user')
        super(UserApplication, cls).write(*args)
        User._get_preferences_cache.clear()

    @classmethod
    def delete(cls, applications):
        pool = Pool()
        User = pool.get('res.user')
        super(UserApplication, cls).delete(applications)
        User._get_preferences_cache.clear()


class EmailResetPassword(Report):
    __name__ = 'res.user.email_reset_password'

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Lang = pool.get('ir.lang')
        context = super().get_context(records, header, data)
        lang = Lang.get()
        context['host'] = host()
        context['http_host'] = http_host()
        context['database'] = Transaction().database.name
        context['expire'] = lang.strftime(
            records[0].password_reset_expire,
            format=lang.date + ' %H:%M:%S')
        return context


class UserConfigStart(ModelView):
    'User Config Init'
    __name__ = 'res.user.config.start'


class UserConfig(Wizard):
    'Configure users'
    __name__ = 'res.user.config'

    start = StateView('res.user.config.start',
        'res.user_config_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'user', 'tryton-ok', default=True),
            ])
    user = StateView('res.user',
        'res.user_view_form', [
            Button('End', 'end', 'tryton-cancel'),
            Button('Add', 'add', 'tryton-ok'),
            ])
    add = StateTransition()

    def transition_add(self):
        pool = Pool()
        User = pool.get('res.user')
        self.user.save()
        self.user = User()
        return 'user'

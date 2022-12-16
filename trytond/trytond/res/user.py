# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"User"
import copy
import string
import random
import hashlib
import time
import datetime
from functools import wraps
from itertools import groupby, ifilter
from operator import attrgetter
from ast import literal_eval

from sql import Literal
from sql.conditionals import Coalesce
from sql.aggregate import Count
from sql.operators import Concat

try:
    import bcrypt
except ImportError:
    bcrypt = None

from ..model import ModelView, ModelSQL, fields
from ..wizard import Wizard, StateView, Button, StateTransition
from ..tools import grouped_slice
from .. import backend
from ..transaction import Transaction
from ..cache import Cache
from ..pool import Pool
from ..config import config
from ..pyson import PYSONEncoder
from ..rpc import RPC

__all__ = [
    'User', 'LoginAttempt', 'UserAction', 'UserGroup', 'Warning_',
    'UserConfigStart', 'UserConfig',
    ]


class User(ModelSQL, ModelView):
    "User"
    __name__ = "res.user"
    name = fields.Char('Name', required=True, select=True, translate=True)
    login = fields.Char('Login', required=True)
    password_hash = fields.Char('Password Hash')
    password = fields.Function(fields.Char('Password'), getter='get_password',
        setter='set_password')
    signature = fields.Text('Signature')
    active = fields.Boolean('Active')
    menu = fields.Many2One('ir.action', 'Menu Action',
        domain=[('usage', '=', 'menu')], required=True)
    pyson_menu = fields.Function(fields.Char('PySON Menu'), 'get_pyson_menu')
    actions = fields.Many2Many('res.user-ir.action', 'user', 'action',
        'Actions', help='Actions that will be run at login')
    groups = fields.Many2Many('res.user-res.group',
       'user', 'group', 'Groups')
    rule_groups = fields.Many2Many('ir.rule.group-res.user',
       'user', 'rule_group', 'Rules',
       domain=[('global_p', '!=', True), ('default_p', '!=', True)])
    language = fields.Many2One('ir.lang', 'Language',
        domain=['OR',
            ('translatable', '=', True),
            ])
    language_direction = fields.Function(fields.Char('Language Direction'),
            'get_language_direction')
    email = fields.Char('Email')
    status_bar = fields.Function(fields.Char('Status Bar'), 'get_status_bar')
    warnings = fields.One2Many('res.user.warning', 'user', 'Warnings')
    sessions = fields.Function(fields.Integer('Sessions'),
            'get_sessions')
    _get_preferences_cache = Cache('res_user.get_preferences')
    _get_groups_cache = Cache('res_user.get_groups')
    _get_login_cache = Cache('res_user._get_login', context=False)

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls.__rpc__.update({
                'get_preferences': RPC(check_access=False),
                'set_preferences': RPC(readonly=False, check_access=False),
                'get_preferences_fields_view': RPC(check_access=False),
                })
        cls._sql_constraints += [
            ('login_key', 'UNIQUE (login)',
                'You can not have two users with the same login!')
        ]
        cls._preferences_fields = [
            'name',
            'password',
            'email',
            'signature',
            'menu',
            'pyson_menu',
            'actions',
            'status_bar',
            'warnings',
        ]
        cls._context_fields = [
            'language',
            'language_direction',
            'groups',
        ]
        cls._error_messages.update({
            'rm_root': ('You can not remove the root user\n'
                    'as it is used internally for resources\n'
                    'created by the system '
                    '(updates, module installation, ...)'),
            'wrong_password': 'Wrong password!',
            })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        super(User, cls).__register__(module_name)
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.6

        # For module dashboard
        table.module_name = 'dashboard'
        table.not_null_action('dashboard_layout', action='remove')

        # For module calendar_scheduling
        table.module_name = 'calendar_scheduling'
        for field in ('calendar_email_notification_new',
                'calendar_email_notification_update',
                'calendar_email_notification_cancel',
                'calendar_email_notification_partstat',
                ):
            table.not_null_action(field, action='remove')

        # Migration from 2.2
        table.not_null_action('menu', action='remove')

        # Migration from 2.6
        table.drop_column('login_try', exception=True)

        # Migration from 3.0
        if table.column_exist('password') and table.column_exist('salt'):
            sqltable = cls.__table__()
            password_hash_new = Concat('sha1$', Concat(sqltable.password,
                Concat('$', Coalesce(sqltable.salt, ''))))
            cursor.execute(*sqltable.update(
                columns=[sqltable.password_hash],
                values=[password_hash_new]))
            table.drop_column('password', exception=True)
            table.drop_column('salt', exception=True)

    @staticmethod
    def default_active():
        return True

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
        pool = Pool()
        Action = pool.get('ir.action')
        encoder = PYSONEncoder()
        return encoder.encode(
            Action.get_action_values(self.menu.type, [self.menu.id])[0])

    def get_language_direction(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if self.language:
            return self.language.direction
        else:
            return Lang.default_direction()

    def get_status_bar(self, name):
        return self.name

    def get_password(self, name):
        return 'x' * 10

    @classmethod
    def set_password(cls, users, name, value):
        if value == 'x' * 10:
            return
        to_write = []
        for user in users:
            to_write.extend([[user], {
                        'password_hash': cls.hash_password(value),
                        }])
        cls.write(*to_write)

    @staticmethod
    def get_sessions(users, name):
        Session = Pool().get('ir.session')
        now = datetime.datetime.now()
        timeout = datetime.timedelta(
            seconds=config.getint('session', 'timeout'))
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
                        for i, g in groupby(ifilter(filter_, sessions),
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
    def read(cls, ids, fields_names=None):
        result = super(User, cls).read(ids, fields_names=fields_names)
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
        actions = iter((users, values) + args)
        all_users = []
        args = []
        for users, values in zip(actions, actions):
            all_users += users
            args.extend((users, cls._convert_vals(values)))
        super(User, cls).write(*args)
        # Clean cursor cache as it could be filled by domain_get
        for cache in Transaction().cursor.cache.itervalues():
            if cls.__name__ in cache:
                for user in all_users:
                    if user.id in cache[cls.__name__]:
                        cache[cls.__name__][user.id].clear()
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
        if [u.id for u in users if u.id == 0]:
            cls.raise_user_error('rm_root')
        super(User, cls).delete(users)
        # Restart the cache for _get_login
        cls._get_login_cache.clear()

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('login',) + tuple(clause[1:]),
            (cls._rec_name,) + tuple(clause[1:]),
            ]

    @classmethod
    def copy(cls, users, default=None):
        if default is None:
            default = {}
        default = default.copy()

        default['password'] = ''

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
        ConfigItem = pool.get('ir.module.module.config_wizard.item')

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
                        res['language'] = None
                else:
                    res[field] = None
                    if getattr(user, field):
                        res[field] = getattr(user, field).id
                        res[field + '.rec_name'] = \
                            getattr(user, field).rec_name
            elif cls._fields[field]._type in ('one2many', 'many2many'):
                res[field] = [x.id for x in getattr(user, field)]
                if field == 'actions' and user.login == 'admin':
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
    def set_preferences(cls, values, old_password=False):
        '''
        Set user preferences.
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
            if field == 'password':
                if not cls.get_login(user.login, old_password):
                    cls.raise_user_error('wrong_password')
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
    def get_groups(cls):
        '''
        Return a list of group ids for the user
        '''
        user = Transaction().user
        groups = cls._get_groups_cache.get(user)
        if groups is not None:
            return groups
        groups = cls.read([Transaction().user], ['groups'])[0]['groups']
        cls._get_groups_cache.set(user, groups)
        return groups

    @classmethod
    def _get_login(cls, login):
        result = cls._get_login_cache.get(login)
        if result:
            return result
        cursor = Transaction().cursor
        table = cls.__table__()
        cursor.execute(*table.select(table.id, table.password_hash,
                where=(table.login == login) & table.active))
        result = cursor.fetchone() or (None, None)
        cls._get_login_cache.set(login, result)
        return result

    @classmethod
    def get_login(cls, login, password):
        '''
        Return user id if password matches
        '''
        LoginAttempt = Pool().get('res.user.login.attempt')
        time.sleep(2 ** LoginAttempt.count(login) - 1)
        user_id, password_hash = cls._get_login(login)
        if user_id:
            if cls.check_password(password, password_hash):
                LoginAttempt.remove(login)
                return user_id
        LoginAttempt.add(login)
        return 0

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
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        salt = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        hash_ = hashlib.sha1(password + salt).hexdigest()
        return '$'.join(['sha1', hash_, salt])

    @classmethod
    def check_sha1(cls, password, hash_):
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        if isinstance(hash_, unicode):
            hash_ = hash_.encode('utf-8')
        hash_method, hash_, salt = hash_.split('$', 2)
        salt = salt or ''
        assert hash_method == 'sha1'
        return hash_ == hashlib.sha1(password + salt).hexdigest()

    @classmethod
    def hash_bcrypt(cls, password):
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        hash_ = bcrypt.hashpw(password, bcrypt.gensalt())
        return '$'.join(['bcrypt', hash_])

    @classmethod
    def check_bcrypt(cls, password, hash_):
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        if isinstance(hash_, unicode):
            hash_ = hash_.encode('utf-8')
        hash_method, hash_ = hash_.split('$', 1)
        assert hash_method == 'bcrypt'
        return hash_ == bcrypt.hashpw(password, hash_)


class LoginAttempt(ModelSQL):
    """Login Attempt

    This class is separated from the res.user one in order to prevent locking
    the res.user table when in a long running process.
    """
    __name__ = 'res.user.login.attempt'
    login = fields.Char('Login', size=512)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        super(LoginAttempt, cls).__register__(module_name)
        table = TableHandler(Transaction().cursor, cls, module_name)

        # Migration from 2.8: remove user
        table.drop_column('user')

    @staticmethod
    def delay():
        return (datetime.datetime.now()
            - datetime.timedelta(seconds=config.getint('session', 'timeout')))

    def _login_size(func):
        @wraps(func)
        def wrapper(cls, login, *args, **kwargs):
            return func(cls, login[:cls.login.size], *args, **kwargs)
        return wrapper

    @classmethod
    @_login_size
    def add(cls, login):
        cls.delete(cls.search([
                    ('create_date', '<', cls.delay()),
                    ]))
        cls.create([{'login': login}])

    @classmethod
    @_login_size
    def remove(cls, login):
        cursor = Transaction().cursor
        table = cls.__table__()
        cursor.execute(*table.delete(where=table.login == login))

    @classmethod
    @_login_size
    def count(cls, login):
        cursor = Transaction().cursor
        table = cls.__table__()
        cursor.execute(*table.select(Count(Literal(1)),
                where=(table.login == login)
                & (table.create_date >= cls.delay())))
        return cursor.fetchone()[0]

    del _login_size


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
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'res_group_user_rel', cls._table)
        TableHandler.sequence_rename(cursor, 'res_group_user_rel_id_seq',
            cls._table + '_id_seq')
        # Migration from 2.0 uid and gid rename into user and group
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('uid', 'user')
        table.column_rename('gid', 'group')
        super(UserGroup, cls).__register__(module_name)


class Warning_(ModelSQL, ModelView):
    'User Warning'
    __name__ = 'res.user.warning'

    user = fields.Many2One('res.user', 'User', required=True, select=True)
    name = fields.Char('Name', required=True, select=True)
    always = fields.Boolean('Always')

    @classmethod
    def check(cls, warning_name):
        user = Transaction().user
        if not user:
            return False
        warnings = cls.search([
            ('user', '=', user),
            ('name', '=', warning_name),
            ])
        if not warnings:
            return True
        cls.delete([x for x in warnings if not x.always])
        return False


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

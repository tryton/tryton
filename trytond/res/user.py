#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"User"
import copy
import string
import random
try:
    import hashlib
except ImportError:
    hashlib = None
    import sha
import time
import datetime
from itertools import groupby, ifilter
from operator import attrgetter

from ..model import ModelView, ModelSQL, fields
from ..wizard import Wizard, StateView, Button, StateTransition
from ..tools import safe_eval
from ..backend import TableHandler
from ..transaction import Transaction
from ..cache import Cache
from ..pool import Pool
from ..config import CONFIG
from ..pyson import PYSONEncoder
from ..rpc import RPC

try:
    import pytz
    TIMEZONES = [(x, x) for x in pytz.common_timezones]
except ImportError:
    TIMEZONES = []

__all__ = [
    'User', 'UserAction', 'UserGroup', 'Warning_',
    'UserConfigStart', 'UserConfig',
    ]


class User(ModelSQL, ModelView):
    "User"
    __name__ = "res.user"
    name = fields.Char('Name', required=True, select=True, translate=True)
    login = fields.Char('Login', required=True)
    login_try = fields.Integer('Login Try', required=True)
    password = fields.Sha('Password')
    salt = fields.Char('Salt', size=8)
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
            ('code', '=', CONFIG['language']),
            ])
    language_direction = fields.Function(fields.Char('Language Direction'),
            'get_language_direction')
    timezone = fields.Selection(TIMEZONES, 'Timezone', translate=False)
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
                'get_preferences': RPC(),
                'set_preferences': RPC(readonly=False),
                'get_preferences_fields_view': RPC(),
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
            'timezone',
            'groups',
        ]
        cls._error_messages.update({
            'rm_root': 'You can not remove the root user\n' \
                            'as it is used internally for resources\n' \
                            'created by the system ' \
                            '(updates, module installation, ...)',
            'wrong_password': 'Wrong password!',
            })

    @classmethod
    def __register__(cls, module_name):
        super(User, cls).__register__(module_name)
        table = TableHandler(Transaction().cursor, cls, module_name)

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

    @staticmethod
    def default_login_try():
        return 0

    @staticmethod
    def default_password():
        return None

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

    @staticmethod
    def get_sessions(users, name):
        Session = Pool().get('ir.session')
        cursor = Transaction().cursor
        now = datetime.datetime.now()
        timeout = datetime.timedelta(seconds=int(CONFIG['session_timeout']))
        result = dict((u.id, 0) for u in users)
        for i in range(0, len(users), cursor.IN_MAX):
            sub_ids = [u.id for u in users[i:i + cursor.IN_MAX]]

            with Transaction().set_user(0):
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
        if 'password' in vals:
            if vals['password'] == 'x' * 10:
                del vals['password']
            elif vals['password']:
                vals['salt'] = ''.join(random.sample(
                    string.ascii_letters + string.digits, 8))
                vals['password'] += vals['salt']
        return vals

    @classmethod
    def create(cls, vals):
        vals = cls._convert_vals(vals)
        res = super(User, cls).create(vals)
        # Restart the cache for _get_login
        cls._get_login_cache.clear()
        return res

    @classmethod
    def write(cls, users, vals):
        vals = cls._convert_vals(vals)
        super(User, cls).write(users, vals)
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
    def read(cls, ids, fields_names=None):
        res = super(User, cls).read(ids, fields_names=fields_names)
        for val in res:
            if 'password' in val:
                val['password'] = 'x' * 10
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        users = cls.search([
            ('login', '=', clause[2]),
            ], order=[])
        if len(users) == 1:
            return [('id', '=', users[0].id)]
        return [(cls._rec_name,) + tuple(clause[1:])]

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
                        res['language'] = CONFIG['language']
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
                'grouping': safe_eval(user.language.grouping),
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
        with Transaction().set_user(0):
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
        with Transaction().set_user(0):
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
        with Transaction().set_user(0):
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
            definition[name]['type'] = 'selection'
            selection = []
            definition[name]['selection'] = selection
            return selection

        if 'language' in res['fields']:
            selection = convert2selection(res['fields'], 'language')
            langs = Lang.search(['OR',
                    ('translatable', '=', True),
                    ('code', '=', CONFIG['language']),
                    ])
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
        cursor.execute('SELECT id, password, salt ' \
                'FROM "' + cls._table + '" '
                'WHERE login = %s AND active', (login,))
        result = cursor.fetchone() or (None, None, None)
        cls._get_login_cache.set(login, result)
        return result

    @classmethod
    def get_login(cls, login, password):
        '''
        Return user id if password matches
        '''
        user_id, user_password, salt = cls._get_login(login)
        if not user_id:
            return 0
        password += salt or ''
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        if hashlib:
            password_sha = hashlib.sha1(password).hexdigest()
        else:
            password_sha = sha.new(password).hexdigest()
        cursor = Transaction().cursor
        if password_sha == user_password:
            cursor.execute('UPDATE "' + cls._table + '" '
                'SET login_try = 0 '
                'WHERE login = %s', (login,))
            return user_id
        cursor.execute('UPDATE "' + cls._table + '" '
            'SET login_try = login_try + 1 '
            'WHERE login = %s', (login,))
        cursor.execute('SELECT login_try FROM "' + cls._table + '" '
            'WHERE login = %s', (login,))
        login_try, = cursor.fetchone()
        time.sleep(2 ** login_try)
        return 0


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
    def create(cls, values):
        values = cls._convert_values(values)
        return super(UserAction, cls).create(values)

    @classmethod
    def write(cls, records, values):
        values = cls._convert_values(values)
        super(UserAction, cls).write(records, values)


class UserGroup(ModelSQL):
    'User - Group'
    __name__ = 'res.user-res.group'
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=True,
            required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def __register__(cls, module_name):
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
            Button('Ok', 'user', 'tryton-ok', default=True),
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

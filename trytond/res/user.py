#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"User"
from __future__ import with_statement
import copy
import string
import random
try:
    import hashlib
except ImportError:
    hashlib = None
    import sha
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.tools import safe_eval
from trytond.backend import TableHandler
from trytond.security import get_connections
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pyson import Eval, Greater


class User(ModelSQL, ModelView):
    "User"
    _name = "res.user"
    _description = __doc__
    name = fields.Char('Name', required=True, select=1, translate=True)
    login = fields.Char('Login', required=True)
    password = fields.Sha('Password')
    salt = fields.Char('Salt', size=8)
    signature = fields.Text('Signature')
    active = fields.Boolean('Active')
    action = fields.Many2One('ir.action', 'Home Action', states={
        'required': Greater(Eval('active_id', 0), 0),
        })
    menu = fields.Many2One('ir.action', 'Menu Action',
            domain=[('usage','=','menu')], required=True)
    groups = fields.Many2Many('res.user-res.group',
       'uid', 'gid', 'Groups')
    rule_groups = fields.Many2Many('ir.rule.group-res.user',
       'user_id', 'rule_group_id', 'Rules',
       domain=[('global_p', '!=', True), ('default_p', '!=', True)])
    language = fields.Many2One('ir.lang', 'Language',
            domain=['OR', ('translatable', '=', True), ('code', '=', 'en_US')])
    language_direction = fields.Function(fields.Char('Language Direction'),
            'get_language_direction')
    timezone = fields.Selection('timezones', 'Timezone')
    email = fields.Char('Email')
    status_bar = fields.Function(fields.Char('Status Bar'), 'get_status_bar')
    warnings = fields.One2Many('res.user.warning', 'user', 'Warnings')
    connections = fields.Function(fields.Integer('Connections'),
            'get_connections')

    def __init__(self):
        super(User, self).__init__()
        self._rpc.update({
            'get_preferences': False,
            'set_preferences': True,
            'get_preferences_fields_view': False,
        })
        self._sql_constraints += [
            ('login_key', 'UNIQUE (login)',
                'You can not have two users with the same login!')
        ]
        self._preferences_fields = [
            'name',
            'password',
            'email',
            'signature',
            'menu',
            'action',
            'status_bar',
            'warnings',
        ]
        self._context_fields = [
            'language',
            'language_direction',
            'timezone',
            'groups',
        ]
        self._error_messages.update({
            'rm_root': 'You can not remove the root user\n' \
                            'as it is used internally for resources\n' \
                            'created by the system ' \
                            '(updates, module installation, ...)',
            'wrong_password': 'Wrong password!',
            })

    def init(self, module_name):
        super(User, self).init(module_name)
        table = TableHandler(Transaction().cursor, self, module_name)

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

    def default_password(self):
        return False

    def default_active(self):
        return 1

    def default_menu(self):
        action_obj = self.pool.get('ir.action')
        action_ids = action_obj.search([
            ('usage', '=', 'menu'),
            ], limit=1)
        if action_ids:
            return action_ids[0]
        return False

    def default_action(self):
        return self.default_menu()

    def get_language_direction(self, ids, name):
        res = {}
        lang_obj = self.pool.get('ir.lang')
        default_direction = lang_obj.default_direction()
        for user in self.browse(ids):
            if user.language:
                res[user.id] = user.language.direction
            else:
                res[user.id] = default_direction
        return res

    def get_status_bar(self, ids, name):
        res = {}
        for user in self.browse(ids):
            res[user.id] = user.name
        return res

    def get_connections(self, ids, name):
        res = {}
        transaction = Transaction()
        for user_id in ids:
            res[user_id] = get_connections(transaction.cursor.database_name,
                    transaction.user)
        return res

    def _convert_vals(self, vals):
        vals = vals.copy()
        action_obj = self.pool.get('ir.action')
        if 'action' in vals:
            vals['action'] = action_obj.get_action_id(vals['action'])
        if 'menu' in vals:
            vals['menu'] = action_obj.get_action_id(vals['menu'])
        if 'password' in vals:
            if vals['password'] == 'x' * 10:
                del vals['password']
            elif vals['password']:
                vals['salt'] = ''.join(random.sample(
                    string.ascii_letters + string.digits, 8))
                vals['password'] += vals['salt']
        return vals

    def create(self, vals):
        vals = self._convert_vals(vals)
        res = super(User, self).create(vals)
        # Restart the cache for _get_login
        self._get_login.reset()
        return res

    def write(self, ids, vals):
        vals = self._convert_vals(vals)
        res = super(User, self).write(ids, vals)
        # Restart the cache for domain_get method
        self.pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        self.get_groups.reset()
        # Restart the cache for _get_login
        self._get_login.reset()
        # Restart the cache for get_preferences
        self.get_preferences.reset()
        # Restart the cache of check
        self.pool.get('ir.model.access').check.reset()
        # Restart the cache
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get.reset()
            except Exception:
                pass
        return res

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 0 in ids:
            self.raise_user_error('rm_root')
        res = super(User, self).delete(ids)
        # Restart the cache for _get_login
        self._get_login.reset()
        return res

    def read(self, ids, fields_names=None):
        res = super(User, self).read(ids, fields_names=fields_names)
        if isinstance(ids, (int, long)):
            if 'password' in res:
                res['password'] = 'x' * 10
        else:
            for val in res:
                if 'password' in val:
                    val['password'] = 'x' * 10
        return res

    def search_rec_name(self, name, clause):
        ids = self.search([
            ('login', '=', clause[2]),
            ], order=[])
        if len(ids) == 1:
            return [('id', '=', ids[0])]
        return [(self._rec_name,) + clause[1:]]

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        default['password'] = ''

        new_ids = []
        for user in self.browse(ids):
            default['login'] = user.login + ' (copy)'
            new_id = super(User, self).copy(user.id, default)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def _get_preferences(self, user, context_only=False):
        res = {}
        if context_only:
            fields = self._context_fields
        else:
            fields = self._preferences_fields + self._context_fields
        for field in fields:
            if self._columns[field]._type in ('many2one',):
                if field == 'language':
                    if user.language:
                        res['language'] = user.language.code
                    else:
                        res['language'] = 'en_US'
                else:
                    res[field] = user[field].id
            elif self._columns[field]._type in ('one2many', 'many2many'):
                res[field] = [x.id for x in user[field]]
            else:
                res[field] = user[field]

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

    @Cache('res_user.get_preferences')
    def get_preferences(self, context_only=False):
        user = Transaction().user
        with Transaction().set_user(0):
            user = self.browse(user)
        return self._get_preferences(user, context_only=context_only)

    def set_preferences(self, values, old_password=False):
        '''
        Set user preferences.

        :param values: a dictionary with values
        :param old_password: the previous password if password is in values
        '''
        lang_obj = self.pool.get('ir.lang')
        values_clean = values.copy()
        fields = self._preferences_fields + self._context_fields
        user_id = Transaction().user
        for field in values:
            if field not in fields or field == 'groups':
                del values_clean[field]
            if field == 'password':
                with Transaction().set_user(0):
                    user = self.browse(user_id)
                    if not self.get_login(user.login, old_password):
                        self.raise_user_error('wrong_password')
            if field == 'language':
                lang_ids = lang_obj.search([
                    ('code', '=', values['language']),
                    ])
                if lang_ids:
                    values_clean['language'] = lang_ids[0]
                else:
                    del values_clean['language']
        with Transaction().set_user(0):
            self.write(user_id, values_clean)

    def get_preferences_fields_view(self):
        model_data_obj = self.pool.get('ir.model.data')
        lang_obj = self.pool.get('ir.lang')

        view_id = model_data_obj.get_id('res', 'user_view_form_preferences')
        res = self.fields_view_get(view_id=view_id)
        res = copy.deepcopy(res)
        for field in res['fields']:
            if field not in ('groups', 'language_direction'):
                res['fields'][field]['readonly'] = False
            else:
                res['fields'][field]['readonly'] = True
        if 'language' in res['fields']:
            del res['fields']['language']['relation']
            res['fields']['language']['type'] = 'selection'
            res['fields']['language']['selection'] = []
            lang_ids = lang_obj.search(['OR',
                ('translatable', '=', True),
                ('code', '=', 'en_US'),
                ])
            with Transaction().set_context(translate_name=True):
                for lang in lang_obj.browse(lang_ids):
                    res['fields']['language']['selection'].append(
                            (lang.code, lang.name))
        return res

    def timezones(self):
        try:
            import pytz
            res = [(x, x) for x in pytz.common_timezones]
        except ImportError:
            res = []
        return res

    @Cache('res_user.get_groups')
    def get_groups(self):
        '''
        Return a list of group ids for the user

        :return: a list of group ids
        '''
        return self.read(Transaction().user, ['groups'])['groups']

    @Cache('res_user._get_login')
    def _get_login(self, login):
        cursor = Transaction().cursor
        cursor.execute('SELECT id, password, salt ' \
                'FROM "' + self._table + '" '
                'WHERE login = %s AND active', (login,))
        res = cursor.fetchone()
        if not res:
            return None, None, None
        return res

    def get_login(self, login, password):
        '''
        Return user id if password matches

        :param login: the login name
        :param password: the password
        :return: integer
        '''
        user_id, user_password, salt = self._get_login(login)
        if not user_id:
            return 0
        password += salt or ''
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        if hashlib:
            password_sha = hashlib.sha1(password).hexdigest()
        else:
            password_sha = sha.new(password).hexdigest()
        if password_sha == user_password:
            return user_id
        return 0

User()


class UserGroup(ModelSQL):
    'User - Group'
    _name = 'res.user-res.group'
    _description = __doc__
    uid = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=1,
            required=True)
    gid = fields.Many2One('res.group', 'Group', ondelete='CASCADE', select=1,
            required=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'res_group_user_rel', self._table)
        TableHandler.sequence_rename(cursor, 'res_group_user_rel_id_seq',
                self._table + '_id_seq')
        super(UserGroup, self).init(module_name)

UserGroup()


class Group(ModelSQL, ModelView):
    "Group"
    _name = "res.group"
    users = fields.Many2Many('res.user-res.group', 'gid', 'uid', 'Users')

Group()


class Warning(ModelSQL, ModelView):
    'User Warning'
    _name = 'res.user.warning'
    _description = __doc__

    user = fields.Many2One('res.user', 'User', required=True, select=1)
    name = fields.Char('Name', required=True, select=1)
    always = fields.Boolean('Always')

    def check(self, warning_name):
        user = Transaction().user
        if not user:
            return False
        warning_ids = self.search([
            ('user', '=', user),
            ('name', '=', warning_name),
            ])
        if not warning_ids:
            return True
        warnings = self.browse(warning_ids)
        self.delete([x.id for x in warnings if not x.always])
        return False

Warning()


class UserConfigInit(ModelView):
    'User Config Init'
    _name = 'res.user.config.init'
    _description = __doc__

UserConfigInit()


class UserConfig(Wizard):
    'Configure users'
    _name = 'res.user.config'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'res.user.config.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('user', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'user': {
            'actions': ['_reset'],
            'result': {
                'type': 'form',
                'object': 'res.user',
                'state': [
                    ('end', 'End', 'tryton-cancel'),
                    ('add', 'Add', 'tryton-ok', True),
                ],
            },
        },
        'add': {
            'result': {
                'type': 'action',
                'action': '_add',
                'state': 'user',
            },
        },
    }

    def _reset(self, data):
        return {}

    def _add(self, data):
        res_obj = self.pool.get('res.user')
        res_obj.create(data['form'])
        return {}

UserConfig()

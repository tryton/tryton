#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"User"
import copy
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.tools import Cache, safe_eval
from trytond.backend import TableHandler
from trytond.security import get_connections
import string
import random
try:
    import hashlib
except ImportError:
    hashlib = None
    import sha
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

    def default_password(self, cursor, user, context=None):
        return False

    def default_active(self, cursor, user, context=None):
        return 1

    def default_menu(self, cursor, user, context=None):
        action_obj = self.pool.get('ir.action')
        action_ids = action_obj.search(cursor, user, [
            ('usage', '=', 'menu'),
            ], limit=1, context=context)
        if action_ids:
            return action_ids[0]
        return False

    def default_action(self, cursor, user, context=None):
        return self.default_menu(cursor, user, context=context)

    def get_language_direction(self, cursor, user, ids, name, context=None):
        res = {}
        lang_obj = self.pool.get('ir.lang')
        default_direction = lang_obj.default_direction(cursor, user, context=context)
        for user in self.browse(cursor, user, ids, context=context):
            if user.language:
                res[user.id] = user.language.direction
            else:
                res[user.id] = default_direction
        return res

    def get_status_bar(self, cursor, user_id, ids, name, context=None):
        res = {}
        for user in self.browse(cursor, user_id, ids, context=context):
            res[user.id] = user.name
        return res

    def get_connections(self, cursor, user, ids, name, context=None):
        res = {}
        for user_id in ids:
            res[user_id] = get_connections(cursor.database_name, user_id)
        return res

    def _convert_vals(self, cursor, user, vals, context=None):
        vals = vals.copy()
        action_obj = self.pool.get('ir.action')
        if 'action' in vals:
            vals['action'] = action_obj.get_action_id(cursor, user,
                    vals['action'], context=context)
        if 'menu' in vals:
            vals['menu'] = action_obj.get_action_id(cursor, user,
                    vals['menu'], context=context)
        if 'password' in vals:
            if vals['password'] == 'x' * 10:
                del vals['password']
            elif vals['password']:
                vals['salt'] = ''.join(random.sample(
                    string.ascii_letters + string.digits, 8))
                vals['password'] += vals['salt']
        return vals

    def create(self, cursor, user, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        res = super(User, self).create(cursor, user, vals, context=context)
        # Restart the cache for _get_login
        self._get_login(cursor.dbname)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        res = super(User, self).write(cursor, user, ids, vals, context=context)
        # Restart the cache for domain_get method
        self.pool.get('ir.rule').domain_get(cursor.dbname)
        # Restart the cache for get_groups
        self.get_groups(cursor.dbname)
        # Restart the cache for _get_login
        self._get_login(cursor.dbname)
        # Restart the cache for get_preferences
        self.get_preferences(cursor.dbname)
        # Restart the cache of check
        self.pool.get('ir.model.access').check(cursor.dbname)
        # Restart the cache
        for _, model in self.pool.iterobject():
            try:
                model.fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 0 in ids:
            self.raise_user_error(cursor, 'rm_root', context=context)
        res = super(User, self).delete(cursor, user, ids, context=context)
        # Restart the cache for _get_login
        self._get_login(cursor.dbname)
        return res

    def read(self, cursor, user, ids, fields_names=None, context=None):
        res = super(User, self).read(cursor, user, ids, fields_names=fields_names,
                context=context)
        if isinstance(ids, (int, long)):
            if 'password' in res:
                res['password'] = 'x' * 10
        else:
            for val in res:
                if 'password' in val:
                    val['password'] = 'x' * 10
        return res

    def search_rec_name(self, cursor, user, name, clause, context=None):
        ids = self.search(cursor, user, [
            ('login', '=', clause[2]),
            ], order=[], context=context)
        if len(ids) == 1:
            return [('id', '=', ids[0])]
        return [(self._rec_name,) + tuple(clause[1:])]

    def copy(self, cursor, user, ids, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        default['password'] = ''

        new_ids = []
        user_id = user
        for user in self.browse(cursor, user_id, ids, context=context):
            default['login'] = user.login + ' (copy)'
            new_id = super(User, self).copy(cursor, user_id, user.id, default,
                context=context)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def _get_preferences(self, cursor, user_id, user, context_only=False,
            context=None):
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
    def get_preferences(self, cursor, user_id, context_only=False, context=None):
        user = self.browse(cursor, 0, user_id, context=context)
        res = self._get_preferences(cursor, user_id, user,
                context_only=context_only, context=context)
        return res

    def set_preferences(self, cursor, user_id, values, old_password=False,
            context=None):
        '''
        Set user preferences.

        :param cursor: the database cursor
        :param user_id: the user id
        :param values: a dictionary with values
        :param old_password: the previous password if password is in values
        :param context: the context
        '''
        lang_obj = self.pool.get('ir.lang')
        values_clean = values.copy()
        fields = self._preferences_fields + self._context_fields
        for field in values:
            if field not in fields or field == 'groups':
                del values_clean[field]
            if field == 'password':
                user = self.browse(cursor, 0, user_id, context=context)
                if not self.get_login(cursor, 0, user.login, old_password,
                        context=context):
                    self.raise_user_error(cursor, 'wrong_password',
                            context=context)
            if field == 'language':
                lang_ids = lang_obj.search(cursor, user_id, [
                    ('code', '=', values['language']),
                    ], context=context)
                if lang_ids:
                    values_clean['language'] = lang_ids[0]
                else:
                    del values_clean['language']
        self.write(cursor, 0, user_id, values_clean, context=context)

    def get_preferences_fields_view(self, cursor, user, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        lang_obj = self.pool.get('ir.lang')

        if context is None:
            context = {}

        view_id = model_data_obj.get_id(cursor, user, 'res',
                'user_view_form_preferences')
        res = self.fields_view_get(cursor, user, view_id=view_id,
                context=context)
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
            lang_ids = lang_obj.search(cursor, user, ['OR',
                ('translatable', '=', True),
                ('code', '=', 'en_US'),
                ], context=None)
            ctx = context.copy()
            ctx['translate_name'] = True
            for lang in lang_obj.browse(cursor, user, lang_ids, context=ctx):
                res['fields']['language']['selection'].append(
                        (lang.code, lang.name))
        return res

    def timezones(self, cursor, user, context=None):
        try:
            import pytz
            res = [(x, x) for x in pytz.common_timezones]
        except ImportError:
            res = []
        return res

    @Cache('res_user.get_groups')
    def get_groups(self, cursor, user, context=None):
        '''
        Return a list of group ids for the user

        :param cursor: the database cursor
        :param user: the user id
        :param context: the context
        :return: a list of group ids
        '''
        return self.read(cursor, user, user, ['groups'],
                context=context)['groups']

    @Cache('res_user._get_login')
    def _get_login(self, cursor, user, login, context=None):
        cursor.execute('SELECT id, password, salt ' \
                'FROM "' + self._table + '" '
                'WHERE login = %s AND active', (login,))
        res = cursor.fetchone()
        if not res:
            return None, None, None
        return res

    def get_login(self, cursor, user, login, password, context=None):
        '''
        Return user id if password matches

        :param cursor: the database cursor
        :param user: the user id
        :param login: the login name
        :param password: the password
        :param context: the context
        :return: integer
        '''
        user_id, user_password, salt = self._get_login(cursor, user,
                login, context=context)
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

    def init(self, cursor, module_name):
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'res_group_user_rel', self._table)
        TableHandler.sequence_rename(cursor, 'res_group_user_rel_id_seq',
                self._table + '_id_seq')
        super(UserGroup, self).init(cursor, module_name)

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

    def check(self, cursor, user, warning_name, context=None):
        if not user:
            return False
        warning_ids = self.search(cursor, user, [
            ('user', '=', user),
            ('name', '=', warning_name),
            ], context=context)
        if not warning_ids:
            return True
        warnings = self.browse(cursor, user, warning_ids, context=context)
        self.delete(cursor, user, [x.id for x in warnings if not x.always],
                context=context)
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

    def _reset(self, cursor, user, data, context=None):
        return {}

    def _add(self, cursor, user, data, context=None):
        res_obj = self.pool.get('res.user')
        res_obj.create(cursor, user, data['form'], context=context)
        return {}

UserConfig()

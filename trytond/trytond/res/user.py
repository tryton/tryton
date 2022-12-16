#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"User"
import copy
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
from lxml import etree


class User(OSV):
    "User"
    _name = "res.user"
    _description = __doc__
    name = fields.Char('Name', required=True, select=1, translate=True)
    login = fields.Char('Login', required=True)
    password = fields.Sha('Password')
    signature = fields.Text('Signature')
    active = fields.Boolean('Active')
    action = fields.Many2One('ir.action', 'Home Action')
    menu = fields.Many2One('ir.action', 'Menu Action',
            domain=[('usage','=','menu')], required=True)
    groups = fields.Many2Many('res.group', 'res_group_user_rel',
       'uid', 'gid', 'Groups', ondelete_target='CASCADE')
    rule_groups = fields.Many2Many('ir.rule.group', 'user_rule_group_rel',
       'user_id', 'rule_group_id', 'Rules',
       domain=[('global_p', '!=', True), ('default_p', '!=', True)])
    language = fields.Many2One('ir.lang', 'Language',
            domain=['OR', ('translatable', '=', True), ('code', '=', 'en_US')])
    language_direction = fields.Function('get_language_direction', type='char',
            string='Language Direction')
    timezone = fields.Selection('timezones', 'Timezone')
    email = fields.Char('Email')
    status_bar = fields.Function('get_status_bar', type='char',
            string="Status Bar")

    def __init__(self):
        super(User, self).__init__()
        self._rpc_allowed += [
            'get_preferences',
            'set_preferences',
            'get_preferences_fields_view',
        ]
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
            })

    def default_password(self, cursor, user, context=None):
        return ''

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

    def get_language_direction(self, cursor, user, ids, name, arg, context=None):
        res = {}
        lang_obj = self.pool.get('ir.lang')
        default_direction = lang_obj.default_direction(cursor, user, context=context)
        for user in self.browse(cursor, user, ids, context=context):
            if user.language:
                res[user.id] = user.language.direction
            else:
                res[user.id] = default_direction
        return res

    def get_status_bar(self, cursor, user_id, ids, name, arg, context=None):
        res = {}
        for user in self.browse(cursor, user_id, ids, context=context):
            res[user.id] = user.name
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
        if 'password' in vals and vals['password'] == 'x' * 10:
            del vals['password']
        return vals

    def create(self, cursor, user, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        return super(User, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        res = super(User, self).write(cursor, user, ids, vals, context=context)
        # Restart the cache for domain_get method
        self.pool.get('ir.rule').domain_get(cursor.dbname)
        # Restart the cache of check
        self.pool.get('ir.model.access').check(cursor.dbname)
        # Restart the cache
        for model in self.pool.object_name_list():
            try:
                self.pool.get(model).fields_view_get(cursor.dbname)
            except:
                pass
        return res

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 0 in ids:
            self.raise_user_error(cursor, 'rm_root', context=context)
        return super(User, self).delete(cursor, user, ids, context=context)

    def read(self, cursor, user, ids, fields_names=None, context=None,
            load='_classic_write'):
        res = super(User, self).read(cursor, user, ids, fields_names=fields_names,
                context=context, load=load)
        if isinstance(ids, (int, long)):
            if 'password' in res:
                res['password'] = 'x' * 10
        else:
            for val in res:
                if 'password' in val:
                    val['password'] = 'x' * 10
        return res

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=80):
        if args is None:
            args = []
        ids = []
        if name:
            ids = self.search(cursor, user, [('login', '=', name)] + args,
                    limit=limit, context=context)
        if not ids:
            ids = self.search(cursor, user, [('name', operator, name)] + args,
                    limit=limit, context=context)
        return self.name_get(cursor, user, ids, context=context)

    def copy(self, cursor, user, obj_id, default=None, context=None):
        if default is None:
            default = {}
        login = self.read(cursor, user, obj_id, ['login'])['login']
        default.update({'login': login+' (copy)'})
        default.update({'password': ''})
        return super(User, self).copy(cursor, user, obj_id, default,
                context=context)

    def get_preferences(self, cursor, user, context_only=False, context=None):
        res = {}
        user = self.browse(cursor, 0, user, context=context)
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
            res['locale'] = {
                'date': user.language.date,
                'grouping': eval(user.language.grouping),
                'decimal_point': user.language.decimal_point,
                'thousands_sep': user.language.thousands_sep,
            }
        return res

    def set_preferences(self, cursor, user, values, context=None):
        lang_obj = self.pool.get('ir.lang')
        values_clean = values.copy()
        fields = self._preferences_fields + self._context_fields
        for field in values:
            if field not in fields or field == 'groups':
                del values_clean[field]
            if field == 'language':
                lang_ids = lang_obj.search(cursor, user, [
                    ('code', '=', values['language']),
                    ], context=context)
                if lang_ids:
                    values_clean['language'] = lang_ids[0]
                else:
                    del values_clean['language']
        self.write(cursor, 0, user, values_clean, context=context)

    def get_preferences_fields_view(self, cursor, user, context=None):
        lang_obj = self.pool.get('ir.lang')
        res = {}
        fields_names = self._preferences_fields + self._context_fields
        fields_names.pop(fields_names.index('status_bar'))
        fields = self.fields_get(cursor, user,
                fields_names=fields_names, context=context)

        xml = '<?xml version="1.0"?>' \
                '<form string="%s" col="2">' % \
                (self._description.decode('utf-8'),)
        fields_keys = fields.keys()
        fields_keys.sort(lambda x, y: cmp(fields_names.index(x), fields_names.index(y)))
        for field in fields_keys:
            if field == 'language':
                xml += '<label name="%s"/><field name="%s" widget="selection"/>' % \
                        (field.decode('utf-8'), field.decode('utf-8'))
            elif field == 'language_direction':
                pass
            elif self._columns[field]._type == 'many2many':
                xml += '<separator name="%s" colspan="2"/>' \
                        '<field name="%s" colspan="2"/>' % \
                        (field.decode('utf-8'), field.decode('utf-8'))
            else:
                xml += '<label name="%s"/><field name="%s"/>' % \
                        (field.decode('utf-8'), field.decode('utf-8'))
        xml += '</form>'
        tree = etree.fromstring(xml)
        arch, fields = self._view_look_dom_arch(cursor,
                user, tree, 'form', context=context)
        for field in fields:
            if field not in ('groups', 'language_direction'):
                fields[field]['readonly'] = False
            else:
                fields[field]['readonly'] = True
        res['arch'] = arch
        if 'language' in fields:
            del fields['language']['relation']
            fields['language']['selection'] = []
            lang_ids = lang_obj.search(cursor, user, ['OR',
                ('translatable', '=', True),
                ('code', '=', 'en_US'),
                ], context=None)
            for lang in lang_obj.browse(cursor, user, lang_ids, context=context):
                fields['language']['selection'].append((lang.code, lang.name))
        res['fields'] = fields
        return res

    def timezones(self, cursor, user, context=None):
        try:
            import pytz
            res = [(x, x) for x in pytz.common_timezones]
        except ImportError:
            res = []
        return res

User()


class Group(OSV):
    _name = 'res.group'
    users = fields.Many2Many(
        'res.user', 'res_group_user_rel', 'gid', 'uid', 'Users',
        ondelete_target='CASCADE')

Group()


class UserConfigInit(WizardOSV):
    _name = 'res.user.config.init'

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

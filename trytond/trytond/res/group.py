#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Group"
from trytond.model import ModelView, ModelSQL, fields


class Group(ModelSQL, ModelView):
    "Group"
    _name = "res.group"
    _description = __doc__
    name = fields.Char('Name', required=True, select=1, translate=True)
    model_access = fields.One2Many('ir.model.access', 'group',
       'Access Model')
    rule_groups = fields.Many2Many('ir.rule.group-res.group',
       'group_id', 'rule_group_id', 'Rules',
       domain=[('global_p', '!=', True), ('default_p', '!=', True)])
    menu_access = fields.Many2Many('ir.ui.menu-res.group',
       'gid', 'menu_id', 'Access Menu')

    def __init__(self):
        super(Group, self).__init__()
        self._sql_constraints += [
            ('name_uniq', 'unique (name)', 'The name of the group must be unique!')
        ]

    def create(self, vals):
        res = super(Group, self).create(vals)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        self.pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        self.pool.get('res.user').get_preferences.reset()
        return res

    def write(self, ids, vals):
        res = super(Group, self).write(ids, vals)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        self.pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        self.pool.get('res.user').get_preferences.reset()
        return res

    def delete(self, ids):
        res = super(Group, self).delete(ids)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        self.pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        self.pool.get('res.user').get_preferences.reset()
        return res

Group()

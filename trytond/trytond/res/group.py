#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Group"
from trytond.osv import fields, OSV


class Group(OSV):
    "Group"
    _name = "res.group"
    _description = __doc__
    name = fields.Char('Name', required=True, select=1, translate=True)
    model_access = fields.One2Many('ir.model.access', 'group',
       'Access Model')
    rule_groups = fields.Many2Many('ir.rule.group', 'group_rule_group_rel',
       'group_id', 'rule_group_id', 'Rules',
       domain=[('global_p', '!=', True), ('default_p', '!=', True)])
    menu_access = fields.Many2Many('ir.ui.menu', 'ir_ui_menu_group_rel',
       'gid', 'menu_id', 'Access Menu')

    def __init__(self):
        super(Group, self).__init__()
        self._sql_constraints += [
            ('name_uniq', 'unique (name)', 'The name of the group must be unique!')
        ]

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Group, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get(cursor.dbname)
        return res

Group()

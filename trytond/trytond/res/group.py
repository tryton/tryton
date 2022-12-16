#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Group"
from itertools import chain
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool


class MenuMany2Many(fields.Many2Many):

    def get(self, ids, model, name, values=None):
        menu_obj = self.get_target()
        res = super(MenuMany2Many, self).get(ids, model, name,
                values=values)
        menu_ids = list(set(chain(*res.values())))
        test_ids = []
        for i in range(0, len(menu_ids), Transaction().cursor.IN_MAX):
            sub_ids = menu_ids[i:i + Transaction().cursor.IN_MAX]
            test_ids.append(menu_obj.search([
                ('id', 'in', sub_ids),
                ]))
        menu_ids = set(chain(*test_ids))
        for ids in res.itervalues():
            for id_ in ids[:]:
                if id_ not in menu_ids:
                    ids.remove(id_)
        return res

class Group(ModelSQL, ModelView):
    "Group"
    _name = "res.group"
    _description = __doc__
    name = fields.Char('Name', required=True, select=1, translate=True)
    model_access = fields.One2Many('ir.model.access', 'group',
       'Access Model')
    field_access = fields.One2Many('ir.model.field.access', 'group',
        'Access Field')
    rule_groups = fields.Many2Many('ir.rule.group-res.group',
       'group', 'rule_group', 'Rules',
       domain=[('global_p', '!=', True), ('default_p', '!=', True)])
    menu_access = MenuMany2Many('ir.ui.menu-res.group',
       'group', 'menu', 'Access Menu')

    def __init__(self):
        super(Group, self).__init__()
        self._sql_constraints += [
            ('name_uniq', 'unique (name)', 'The name of the group must be unique!')
        ]

    def copy(self, ids, default=None):
        int_id = isinstance(ids, (int, long))
        if int_id:
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()

        new_ids = []
        for group in self.browse(ids):
            i = 1
            while True:
                name = '%s (%d)' % (group.name, i)
                if not self.search([('name', '=', name)], order=[]):
                    break
                i += 1
            default['name'] = name
            new_ids.append(super(Group, self).copy(group.id, default=default))
        if int_id:
            return new_ids[0]
        return new_ids

    def create(self, vals):
        res = super(Group, self).create(vals)
        pool = Pool()
        # Restart the cache on the domain_get method
        pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        pool.get('res.user').get_preferences.reset()
        return res

    def write(self, ids, vals):
        res = super(Group, self).write(ids, vals)
        pool = Pool()
        # Restart the cache on the domain_get method
        pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        pool.get('res.user').get_preferences.reset()
        return res

    def delete(self, ids):
        res = super(Group, self).delete(ids)
        pool = Pool()
        # Restart the cache on the domain_get method
        pool.get('ir.rule').domain_get.reset()
        # Restart the cache for get_groups
        pool.get('res.user').get_groups.reset()
        # Restart the cache for get_preferences
        pool.get('res.user').get_preferences.reset()
        return res

Group()

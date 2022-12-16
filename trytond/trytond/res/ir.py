# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, DeactivableMixin, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class UIMenuGroup(ModelSQL):
    "UI Menu - Group"
    __name__ = 'ir.ui.menu-res.group'
    menu = fields.Many2One('ir.ui.menu', 'Menu', ondelete='CASCADE',
            select=True, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def create(cls, vlist):
        res = super(UIMenuGroup, cls).create(vlist)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()
        return res

    @classmethod
    def write(cls, records, values, *args):
        super(UIMenuGroup, cls).write(records, values, *args)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()

    @classmethod
    def delete(cls, records):
        super(UIMenuGroup, cls).delete(records)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()


class ActionGroup(ModelSQL):
    "Action - Group"
    __name__ = 'ir.action-res.group'
    action = fields.Many2One('ir.action', 'Action', ondelete='CASCADE',
            select=True, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def create(cls, vlist):
        Action = Pool().get('ir.action')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('action'):
                vals['action'] = Action.get_action_id(vals['action'])
        res = super(ActionGroup, cls).create(vlist)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()
        return res

    @classmethod
    def write(cls, records, values, *args):
        Action = Pool().get('ir.action')
        actions = iter((records, values) + args)
        args = []
        for records, values in zip(actions, actions):
            if values.get('action'):
                values = values.copy()
                values['action'] = Action.get_action_id(values['action'])
            args.extend((records, values))
        super(ActionGroup, cls).write(*args)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()

    @classmethod
    def delete(cls, records):
        super(ActionGroup, cls).delete(records)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()


class Action(metaclass=PoolMeta):
    __name__ = 'ir.action'

    groups = fields.Many2Many(
        'ir.action-res.group', 'action', 'group', "Groups")


class ActionMixin(metaclass=PoolMeta):

    @classmethod
    def get_groups(cls, name, action_id=None):
        # TODO add cache
        domain = [
            (cls._action_name, '=', name),
            ]
        if action_id:
            domain.append(('id', '=', action_id))
        actions = cls.search(domain)
        groups = {g.id for a in actions for g in a.groups}
        return groups


class ActionReport(ActionMixin):
    __name__ = 'ir.action.report'


class ActionActWindow(ActionMixin):
    __name__ = 'ir.action.act_window'


class ActionWizard(ActionMixin):
    __name__ = 'ir.action.wizard'


class ActionURL(ActionMixin):
    __name__ = 'ir.action.url'


class ActionKeyword(metaclass=PoolMeta):
    __name__ = 'ir.action.keyword'

    groups = fields.Function(fields.One2Many('res.group', None, 'Groups'),
        'get_groups', searcher='search_groups')

    def get_groups(self, name):
        return [g.id for g in self.action.groups]

    @classmethod
    def search_groups(cls, name, clause):
        return [('action.' + clause[0],) + tuple(clause[1:])]


class ModelButtonGroup(DeactivableMixin, ModelSQL):
    "Model Button - Group"
    __name__ = 'ir.model.button-res.group'
    button = fields.Many2One('ir.model.button', 'Button',
        ondelete='CASCADE', select=True, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
        select=True, required=True)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        result = super(ModelButtonGroup, cls).create(vlist)
        # Restart the cache for get_groups
        pool.get('ir.model.button')._groups_cache.clear()
        return result

    @classmethod
    def write(cls, records, values, *args):
        pool = Pool()
        super(ModelButtonGroup, cls).write(records, values, *args)
        # Restart the cache for get_groups
        pool.get('ir.model.button')._groups_cache.clear()

    @classmethod
    def delete(cls, records):
        pool = Pool()
        super(ModelButtonGroup, cls).delete(records)
        # Restart the cache for get_groups
        pool.get('ir.model.button')._groups_cache.clear()


class ModelButtonRule(metaclass=PoolMeta):
    __name__ = 'ir.model.button.rule'
    group = fields.Many2One('res.group', "Group", ondelete='CASCADE')


class ModelButtonClick(metaclass=PoolMeta):
    __name__ = 'ir.model.button.click'
    user = fields.Many2One('res.user', "User", ondelete='CASCADE')


class RuleGroupGroup(ModelSQL):
    "Rule Group - Group"
    __name__ = 'ir.rule.group-res.group'
    rule_group = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='CASCADE', select=True, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=True, required=True)


class Lang(metaclass=PoolMeta):
    __name__ = 'ir.lang'

    @classmethod
    def write(cls, langs, values, *args):
        super(Lang, cls).write(langs, values, *args)
        # Restart the cache for get_preferences
        Pool().get('res.user')._get_preferences_cache.clear()


class SequenceType(metaclass=PoolMeta):
    __name__ = 'ir.sequence.type'
    groups = fields.Many2Many('ir.sequence.type-res.group', 'sequence_type',
            'group', 'User Groups',
            help='Groups allowed to edit the sequences of this type.')


class SequenceTypeGroup(ModelSQL):
    'Sequence Type - Group'
    __name__ = 'ir.sequence.type-res.group'
    sequence_type = fields.Many2One('ir.sequence.type', 'Sequence Type',
            ondelete='CASCADE', select=True, required=True)
    group = fields.Many2One('res.group', 'User Groups',
            ondelete='CASCADE', select=True, required=True)

    @classmethod
    def delete(cls, records):
        Rule = Pool().get('ir.rule')
        super(SequenceTypeGroup, cls).delete(records)
        # Restart the cache on the domain_get method of ir.rule
        Rule._domain_get_cache.clear()

    @classmethod
    def create(cls, vlist):
        Rule = Pool().get('ir.rule')
        res = super(SequenceTypeGroup, cls).create(vlist)
        # Restart the cache on the domain_get method of ir.rule
        Rule._domain_get_cache.clear()
        return res

    @classmethod
    def write(cls, records, values, *args):
        Rule = Pool().get('ir.rule')
        super(SequenceTypeGroup, cls).write(records, values, *args)
        # Restart the cache on the domain_get method
        Rule._domain_get_cache.clear()


class ModuleConfigWizardItem(metaclass=PoolMeta):
    __name__ = 'ir.module.config_wizard.item'

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        User = pool.get('res.user')
        result = super(ModuleConfigWizardItem, cls).create(vlist)
        # Restart the cache for get_preferences
        User._get_preferences_cache.clear()
        return result

    @classmethod
    def write(cls, items, values, *args):
        pool = Pool()
        User = pool.get('res.user')
        super(ModuleConfigWizardItem, cls).write(items, values, *args)
        # Restart the cache for get_preferences
        User._get_preferences_cache.clear()

    @classmethod
    def delete(cls, items):
        pool = Pool()
        User = pool.get('res.user')
        super(ModuleConfigWizardItem, cls).delete(items)
        # Restart the cache for get_preferences
        User._get_preferences_cache.clear()


class Export(metaclass=PoolMeta):
    __name__ = 'ir.export'

    groups = fields.Many2Many(
        'ir.export-res.group', 'export', 'group', "Groups",
        help="The user groups that can use the export.")
    write_groups = fields.Many2Many(
        'ir.export-write-res.group', 'export', 'group',
        "Modification Groups",
        domain=[
            ('id', 'in', Eval('groups', [])),
            ],
        states={
            'invisible': ~Eval('groups'),
            },
        depends=['groups'],
        help="The user groups that can modify the export.")


class Export_Group(ModelSQL):
    "Export Group"
    __name__ = 'ir.export-res.group'

    export = fields.Many2One(
        'ir.export', "Export", required=True, select=True, ondelete='CASCADE')
    group = fields.Many2One(
        'res.group', "Group", required=True, ondelete='CASCADE')


class Export_Write_Group(Export_Group):
    "Export Modification Group"
    __name__ = 'ir.export-write-res.group'
    _table = None  # Needed to reset Export_Group._table

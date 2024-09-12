# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.cache import Cache
from trytond.model import DeactivableMixin, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction, without_check_access


class UIMenu(metaclass=PoolMeta):
    __name__ = 'ir.ui.menu'

    groups = fields.Many2Many(
        'ir.ui.menu-res.group', 'menu', 'group', "Groups")


class UIMenuGroup(ModelSQL):
    "UI Menu - Group"
    __name__ = 'ir.ui.menu-res.group'
    menu = fields.Many2One('ir.ui.menu', 'Menu', ondelete='CASCADE',
        required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
        required=True)


class ActionGroup(ModelSQL):
    "Action - Group"
    __name__ = 'ir.action-res.group'
    action = fields.Many2One('ir.action', 'Action', ondelete='CASCADE',
        required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
        required=True)

    @classmethod
    def create(cls, vlist):
        Action = Pool().get('ir.action')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('action'):
                vals['action'] = Action.get_action_id(vals['action'])
        res = super(ActionGroup, cls).create(vlist)
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


class Action(metaclass=PoolMeta):
    __name__ = 'ir.action'

    groups = fields.Many2Many(
        'ir.action-res.group', 'action', 'group', "Groups")


class ActionMixin(metaclass=PoolMeta):

    @classmethod
    @without_check_access
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


class ModelButton(metaclass=PoolMeta):
    __name__ = 'ir.model.button'

    groups = fields.Many2Many(
        'ir.model.button-res.group', 'button', 'group', "Groups")
    _groups_cache = Cache('ir.model.button.groups')

    @classmethod
    def create(cls, vlist):
        result = super().create(vlist)
        cls._groups_cache.clear()
        return result

    @classmethod
    def write(cls, buttons, values, *args):
        super().write(buttons, values, *args)
        cls._groups_cache.clear()

    @classmethod
    def delete(cls, buttons):
        super().delete(buttons)
        cls._groups_cache.clear()

    @classmethod
    def get_groups(cls, model, name):
        '''
        Return a set of group ids for the named button on the model.
        '''
        key = (model, name)
        groups = cls._groups_cache.get(key)
        if groups is not None:
            return groups
        buttons = cls.search([
                ('model.model', '=', model),
                ('name', '=', name),
                ])
        if not buttons:
            groups = set()
        else:
            button, = buttons
            groups = set(g.id for g in button.groups)
        cls._groups_cache.set(key, groups)
        return groups


class ModelButtonGroup(DeactivableMixin, ModelSQL):
    "Model Button - Group"
    __name__ = 'ir.model.button-res.group'
    button = fields.Many2One('ir.model.button', 'Button',
        ondelete='CASCADE', required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
        required=True)

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


class RuleGroup(metaclass=PoolMeta):
    __name__ = 'ir.rule.group'

    groups = fields.Many2Many(
        'ir.rule.group-res.group', 'rule_group', 'group', "Groups")


class RuleGroupGroup(ModelSQL):
    "Rule Group - Group"
    __name__ = 'ir.rule.group-res.group'
    rule_group = fields.Many2One('ir.rule.group', 'Rule Group',
        ondelete='CASCADE', required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
        required=True)


class Rule(metaclass=PoolMeta):
    __name__ = 'ir.rule'

    @classmethod
    def _get_context(cls, model_name):
        context = super()._get_context(model_name)
        if model_name in {'res.user.warning', 'res.user.application'}:
            context['user_id'] = Transaction().user
        return context

    @classmethod
    def _get_cache_key(cls, model_names):
        key = super()._get_cache_key(model_names)
        if model_names & {'res.user.warning', 'res.user.application'}:
            key = (*key, Transaction().user)
        return key


class SequenceType(metaclass=PoolMeta):
    __name__ = 'ir.sequence.type'
    groups = fields.Many2Many('ir.sequence.type-res.group', 'sequence_type',
            'group', 'User Groups',
            help='Groups allowed to edit the sequences of this type.')


class SequenceTypeGroup(ModelSQL):
    'Sequence Type - Group'
    __name__ = 'ir.sequence.type-res.group'
    sequence_type = fields.Many2One('ir.sequence.type', 'Sequence Type',
        ondelete='CASCADE', required=True)
    group = fields.Many2One('res.group', 'User Groups',
        ondelete='CASCADE', required=True)


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
        'ir.export', "Export", required=True, ondelete='CASCADE')
    group = fields.Many2One(
        'res.group', "Group", required=True, ondelete='CASCADE')


class Export_Write_Group(Export_Group):
    "Export Modification Group"
    __name__ = 'ir.export-write-res.group'
    _table = None  # Needed to reset Export_Group._table

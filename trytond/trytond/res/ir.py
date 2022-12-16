#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from ..model import ModelSQL, fields
from ..backend import TableHandler
from ..transaction import Transaction
from ..pool import Pool, PoolMeta

__all__ = [
    'UIMenuGroup', 'ActionGroup', 'ModelFieldGroup', 'ModelButtonGroup',
    'RuleGroupGroup', 'RuleGroupUser', 'Lang', 'SequenceType',
    'SequenceTypeGroup', 'Sequence', 'SequenceStrict',
    'ModuleConfigWizardItem',
    ]
__metaclass__ = PoolMeta


class UIMenuGroup(ModelSQL):
    "UI Menu - Group"
    __name__ = 'ir.ui.menu-res.group'
    menu = fields.Many2One('ir.ui.menu', 'Menu', ondelete='CASCADE',
            select=True, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_ui_menu_group_rel', cls._table)
        TableHandler.sequence_rename(cursor, 'ir_ui_menu_group_rel_id_seq',
                cls._table + '_id_seq')
        # Migration from 2.0 menu_id and gid renamed into menu group
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('menu_id', 'menu')
        table.column_rename('gid', 'group')
        super(UIMenuGroup, cls).__register__(module_name)

    @classmethod
    def create(cls, vlist):
        res = super(UIMenuGroup, cls).create(vlist)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()
        return res

    @classmethod
    def write(cls, records, vals):
        super(UIMenuGroup, cls).write(records, vals)
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
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_action_group_rel', cls._table)
        TableHandler.sequence_rename(cursor, 'ir_action_group_rel_id_seq',
                cls._table + '_id_seq')
        # Migration from 2.0 action_id and gid renamed into action and group
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('action_id', 'action')
        table.column_rename('gid', 'group')
        super(ActionGroup, cls).__register__(module_name)

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
    def write(cls, records, vals):
        Action = Pool().get('ir.action')
        if vals.get('action'):
            vals = vals.copy()
            vals['action'] = Action.get_action_id(vals['action'])
        super(ActionGroup, cls).write(records, vals)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()

    @classmethod
    def delete(cls, records):
        super(ActionGroup, cls).delete(records)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()


class ModelFieldGroup(ModelSQL):
    "Model Field Group Rel"
    __name__ = 'ir.model.field-res.group'
    field = fields.Many2One('ir.model.field', 'Model Field',
            ondelete='CASCADE', select=True, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_model_field_group_rel',
            cls._table)
        TableHandler.sequence_rename(cursor, 'ir_model_field_group_rel_id_seq',
            cls._table + '_id_seq')
        table = TableHandler(cursor, cls, module_name)
        # Migration from 2.6: field_id and group_id renamed to field and group
        table.column_rename('field_id', 'field')
        table.column_rename('group_id', 'group')
        super(ModelFieldGroup, cls).__register__(module_name)


class ModelButtonGroup(ModelSQL):
    "Model Button - Group"
    __name__ = 'ir.model.button-res.group'
    button = fields.Many2One('ir.model.button', 'Button',
        ondelete='CASCADE', select=True, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
        select=True, required=True)
    active = fields.Boolean('Active', select=True)

    @staticmethod
    def default_active():
        return True

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        result = super(ModelButtonGroup, cls).create(vlist)
        # Restart the cache for get_groups
        pool.get('ir.model.button')._groups_cache.clear()
        return result

    @classmethod
    def write(cls, records, values):
        pool = Pool()
        super(ModelButtonGroup, cls).write(records, values)
        # Restart the cache for get_groups
        pool.get('ir.model.button')._groups_cache.clear()

    @classmethod
    def delete(cls, records):
        pool = Pool()
        super(ModelButtonGroup, cls).delete(records)
        # Restart the cache for get_groups
        pool.get('ir.model.button')._groups_cache.clear()


class RuleGroupGroup(ModelSQL):
    "Rule Group - Group"
    __name__ = 'ir.rule.group-res.group'
    rule_group = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='CASCADE', select=True, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'group_rule_group_rel', cls._table)
        TableHandler.sequence_rename(cursor, 'group_rule_group_rel_id_seq',
                cls._table + '_id_seq')
        # Migration from 2.0 rule_group_id and group_id renamed into rule_group
        # and group
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('rule_group_id', 'rule_group')
        table.column_rename('group_id', 'group')
        super(RuleGroupGroup, cls).__register__(module_name)


class RuleGroupUser(ModelSQL):
    "Rule Group - User"
    __name__ = 'ir.rule.group-res.user'
    rule_group = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='CASCADE', select=True, required=True)
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE',
            select=True, required=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'user_rule_group_rel', cls._table)
        TableHandler.sequence_rename(cursor, 'user_rule_group_rel_id_seq',
                cls._table + '_id_seq')
        # Migration from 2.0 rule_group_id and user_id renamed into rule_group
        # and user
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('rule_group_id', 'rule_group')
        table.column_rename('user_id', 'user')
        super(RuleGroupUser, cls).__register__(module_name)


class Lang:
    __name__ = 'ir.lang'

    @classmethod
    def write(cls, langs, vals):
        super(Lang, cls).write(langs, vals)
        # Restart the cache for get_preferences
        Pool().get('res.user')._get_preferences_cache.clear()


class SequenceType:
    __name__ = 'ir.sequence.type'
    groups = fields.Many2Many('ir.sequence.type-res.group', 'sequence_type',
            'group', 'User Groups',
            help='Groups allowed to edit the sequences of this type')


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
    def write(cls, records, vals):
        Rule = Pool().get('ir.rule')
        super(SequenceTypeGroup, cls).write(records, vals)
        # Restart the cache on the domain_get method
        Rule._domain_get_cache.clear()


class Sequence:
    __name__ = 'ir.sequence'
    groups = fields.Function(fields.Many2Many('res.group', None, None,
        'User Groups'), 'get_groups', searcher='search_groups')

    @classmethod
    def get_groups(cls, sequences, name):
        SequenceType = Pool().get('ir.sequence.type')
        code2seq = {}
        for sequence in sequences:
            code2seq.setdefault(sequence.code, []).append(sequence.id)

        sequence_types = SequenceType.search([
                ('code', 'in', code2seq.keys()),
                ])

        groups = {}
        for sequence_type in sequence_types:
            seq_ids = code2seq[sequence_type.code]
            for seq_id in seq_ids:
                groups.setdefault(seq_id, []).append(sequence_type.id)

        return groups

    @staticmethod
    def search_groups(name, clause):
        SequenceType = Pool().get('ir.sequence.type')
        seq_types = SequenceType.search([clause], order=[])
        codes = set(st.code for st in seq_types)
        return [('code', 'in', list(codes))]


class SequenceStrict(Sequence):
    # This empty class declaration is needed to inherit the groups
    # field
    __name__ = 'ir.sequence.strict'


class ModuleConfigWizardItem:
    __name__ = 'ir.module.module.config_wizard.item'

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        User = pool.get('res.user')
        result = super(ModuleConfigWizardItem, cls).create(vlist)
        # Restart the cache for get_preferences
        User._get_preferences_cache.clear()
        return result

    @classmethod
    def write(cls, items, values):
        pool = Pool()
        User = pool.get('res.user')
        super(ModuleConfigWizardItem, cls).write(items, values)
        # Restart the cache for get_preferences
        User._get_preferences_cache.clear()

    @classmethod
    def delete(cls, items):
        pool = Pool()
        User = pool.get('res.user')
        super(ModuleConfigWizardItem, cls).delete(items)
        # Restart the cache for get_preferences
        User._get_preferences_cache.clear()

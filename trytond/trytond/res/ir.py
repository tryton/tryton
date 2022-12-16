#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.backend import TableHandler
from trytond.transaction import Transaction
from trytond.pool import Pool


class UIMenuGroup(ModelSQL):
    "UI Menu - Group"
    _name = 'ir.ui.menu-res.group'
    _description = __doc__
    menu = fields.Many2One('ir.ui.menu', 'Menu', ondelete='CASCADE',
            select=1, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_ui_menu_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'ir_ui_menu_group_rel_id_seq',
                self._table + '_id_seq')
        # Migration from 2.0 menu_id and gid renamed into menu group
        table = TableHandler(cursor, self, module_name)
        table.column_rename('menu_id', 'menu')
        table.column_rename('gid', 'group')
        super(UIMenuGroup, self).init(module_name)

    def create(self, vals):
        res = super(UIMenuGroup, self).create(vals)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule').domain_get.reset()
        return res

    def write(self, ids, vals):
        res = super(UIMenuGroup, self).write(ids, vals)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule').domain_get.reset()
        return res

    def delete(self, ids):
        res = super(UIMenuGroup, self).delete(ids)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule').domain_get.reset()
        return res

UIMenuGroup()


class ActionGroup(ModelSQL):
    "Action - Group"
    _name = 'ir.action-res.group'
    _description = __doc__
    action = fields.Many2One('ir.action', 'Action', ondelete='CASCADE',
            select=1, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_action_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'ir_action_group_rel_id_seq',
                self._table + '_id_seq')
        # Migration from 2.0 action_id and gid renamed into action and group
        table = TableHandler(cursor, self, module_name)
        table.column_rename('action_id', 'action')
        table.column_rename('gid', 'group')
        super(ActionGroup, self).init(module_name)

    def create(self, vals):
        action_obj = Pool().get('ir.action')
        if vals.get('action'):
            vals = vals.copy()
            vals['action'] = action_obj.get_action_id(vals['action'])
        res = super(ActionGroup, self).create(vals)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule').domain_get.reset()
        return res

    def write(self, ids, vals):
        action_obj = Pool().get('ir.action')
        if vals.get('action'):
            vals = vals.copy()
            vals['action'] = action_obj.get_action_id(vals['action'])
        res = super(ActionGroup, self).write(ids, vals)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule').domain_get.reset()
        return res

    def delete(self, ids):
        res = super(ActionGroup, self).delete(ids)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule').domain_get.reset()
        return res

ActionGroup()


class ModelFieldGroup(ModelSQL):
    "Model Field Group Rel"
    _name = 'ir.model.field-res.group'
    _description = __doc__
    field_id = fields.Many2One('ir.model.field', 'Model Field',
            ondelete='CASCADE', select=1, required=True)
    group_id = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_model_field_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'ir_model_field_group_rel_id_seq',
                self._table + '_id_seq')
        super(ModelFieldGroup, self).init(module_name)

ModelFieldGroup()


class RuleGroupGroup(ModelSQL):
    "Rule Group - Group"
    _name = 'ir.rule.group-res.group'
    _description = __doc__
    rule_group = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='CASCADE', select=1, required=True)
    group = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'group_rule_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'group_rule_group_rel_id_seq',
                self._table + '_id_seq')
        # Migration from 2.0 rule_group_id and group_id renamed into rule_group
        # and group
        table = TableHandler(cursor, self, module_name)
        table.column_rename('rule_group_id', 'rule_group')
        table.column_rename('group_id', 'group')
        super(RuleGroupGroup, self).init(module_name)

RuleGroupGroup()


class RuleGroupUser(ModelSQL):
    "Rule Group - User"
    _name = 'ir.rule.group-res.user'
    _description = __doc__
    rule_group = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='CASCADE', select=1, required=True)
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE',
            select=1, required=True)

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'user_rule_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'user_rule_group_rel_id_seq',
                self._table + '_id_seq')
        # Migration from 2.0 rule_group_id and user_id renamed into rule_group
        # and user
        table = TableHandler(cursor, self, module_name)
        table.column_rename('rule_group_id', 'rule_group')
        table.column_rename('user_id', 'user')
        super(RuleGroupUser, self).init(module_name)

RuleGroupUser()


class Lang(ModelSQL, ModelView):
    _name = 'ir.lang'

    def write(self, ids, vals):
        res = super(Lang, self).write(ids, vals)
        # Restart the cache for get_preferences
        Pool().get('res.user').get_preferences.reset()
        return res

Lang()


class SequenceType(ModelSQL, ModelView):
    _name = 'ir.sequence.type'
    groups = fields.Many2Many('ir.sequence.type-res.group', 'sequence_type',
            'group', 'User Groups',
            help='Groups allowed to edit the sequences of this type')

SequenceType()


class SequenceTypeGroup(ModelSQL):
    'Sequence Type - Group'
    _name = 'ir.sequence.type-res.group'
    _description = __doc__
    sequence_type = fields.Many2One('ir.sequence.type', 'Sequence Type',
            ondelete='CASCADE', select=1, required=True)
    group = fields.Many2One('res.group', 'User Groups',
            ondelete='CASCADE', select=1, required=True)

    def delete(self, ids):
        rule_obj = Pool().get('ir.rule')
        res = super(SequenceTypeGroup, self).delete(ids)
        # Restart the cache on the domain_get method of ir.rule
        rule_obj.domain_get.reset()
        return res

    def create(self, vals):
        rule_obj = Pool().get('ir.rule')
        res = super(SequenceTypeGroup, self).create(vals)
        # Restart the cache on the domain_get method of ir.rule
        rule_obj.domain_get.reset()
        return res

    def write(self, ids, vals):
        rule_obj = Pool().get('ir.rule')
        res = super(SequenceTypeGroup, self).write(ids, vals)
        # Restart the cache on the domain_get method
        rule_obj.domain_get.reset()
        return res

SequenceTypeGroup()


class Sequence(ModelSQL, ModelView):
    _name = 'ir.sequence'
    groups = fields.Function(fields.Many2Many('res.group', None, None,
        'User Groups'), 'get_groups', searcher='search_groups')

    def get_groups(self, ids, name):
        sequence_type_obj = Pool().get('ir.sequence.type')
        sequences= self.browse(ids)
        code2seq = {}
        for sequence in sequences:
            code2seq.setdefault(sequence.code, []).append(sequence.id)

        sequence_type_ids = sequence_type_obj.search([
                ('code', 'in', code2seq.keys()),
                ])
        sequence_types = sequence_type_obj.browse(sequence_type_ids)

        res = {}
        for sequence_type in sequence_types:
            seq_ids = code2seq[sequence_type.code]
            for seq_id in seq_ids:
                res.setdefault(seq_id, []).append(sequence_type.id)

        return res

    def search_groups(self, name, clause):
        sequence_type_obj = Pool().get('ir.sequence.type')
        ids = sequence_type_obj.search([clause], order=[])
        seq_types = sequence_type_obj.browse(ids)
        codes = set(st.code for st in seq_types)
        return [('code', 'in', list(codes))]

Sequence()


class SequenceStrict(Sequence):
    # This empty class declaration is needed to inherit the groups
    # field
    _name = 'ir.sequence.strict'

SequenceStrict()

#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.backend import TableHandler


class UIMenuGroup(ModelSQL):
    "UI Menu - Group"
    _name = 'ir.ui.menu-res.group'
    _description = __doc__
    menu_id = fields.Many2One('ir.ui.menu', 'Menu', ondelete='CASCADE',
            select=1, required=True)
    gid = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

    def init(self, cursor, module_name):
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_ui_menu_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'ir_ui_menu_group_rel_id_seq',
                self._table + '_id_seq')
        super(UIMenuGroup, self).init(cursor, module_name)

UIMenuGroup()


class ActionGroup(ModelSQL):
    "Action - Group"
    _name = 'ir.action-res.group'
    _description = __doc__
    action_id = fields.Many2One('ir.action', 'Action', ondelete='CASCADE',
            select=1, required=True)
    gid = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

    def init(self, cursor, module_name):
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_action_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'ir_action_group_rel_id_seq',
                self._table + '_id_seq')
        super(ActionGroup, self).init(cursor, module_name)

ActionGroup()


class ModelFieldGroup(ModelSQL):
    "Model Field Group Rel"
    _name = 'ir.model.field-res.group'
    _description = __doc__
    field_id = fields.Many2One('ir.model.field', 'Model Field',
            ondelete='CASCADE', select=1, required=True)
    group_id = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

    def init(self, cursor, module_name):
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'ir_model_field_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'ir_model_field_group_rel_id_seq',
                self._table + '_id_seq')
        super(ModelFieldGroup, self).init(cursor, module_name)

ModelFieldGroup()


class RuleGroupGroup(ModelSQL):
    "Rule Group - Group"
    _name = 'ir.rule.group-res.group'
    _description = __doc__
    rule_group_id = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='CASCADE', select=1, required=True)
    group_id = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

    def init(self, cursor, module_name):
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'group_rule_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'group_rule_group_rel_id_seq',
                self._table + '_id_seq')
        super(RuleGroupGroup, self).init(cursor, module_name)

RuleGroupGroup()


class RuleGroupUser(ModelSQL):
    "Rule Group - User"
    _name = 'ir.rule.group-res.user'
    _description = __doc__
    rule_group_id = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='CASCADE', select=1, required=True)
    user_id = fields.Many2One('res.user', 'User', ondelete='CASCADE',
            select=1, required=True)

    def init(self, cursor, module_name):
        # Migration from 1.0 table name change
        TableHandler.table_rename(cursor, 'user_rule_group_rel', self._table)
        TableHandler.sequence_rename(cursor, 'user_rule_group_rel_id_seq',
                self._table + '_id_seq')
        super(RuleGroupUser, self).init(cursor, module_name)

RuleGroupUser()


class Lang(ModelSQL, ModelView):
    _name = 'ir.lang'

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Lang, self).write(cursor, user, ids, vals, context=context)
        # Restart the cache for get_preferences
        self.pool.get('res.user').get_preferences(cursor.dbname)
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

    def delete(self, cursor, user, ids, context=None):
        rule_obj = self.pool.get('ir.rule')
        res = super(SequenceTypeGroup, self).delete(cursor, user, ids,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        rule_obj.domain_get(cursor.dbname)
        return res

    def create(self, cursor, user, vals, context=None):
        rule_obj = self.pool.get('ir.rule')
        res = super(SequenceTypeGroup, self).create(cursor, user, vals,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        rule_obj.domain_get(cursor.dbname)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        rule_obj = self.pool.get('ir.rule')
        res = super(SequenceTypeGroup, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method
        rule_obj.domain_get(cursor.dbname)
        return res

SequenceTypeGroup()


class Sequence(ModelSQL, ModelView):
    _name = 'ir.sequence'
    groups = fields.Function(fields.Many2Many('res.group', None, None,
        'User Groups'), 'get_groups', searcher='search_groups')

    def get_groups(self, cursor, user, ids, name, context=None):
        sequence_type_obj = self.pool.get('ir.sequence.type')
        sequences= self.browse(cursor, user, ids, context=context)
        code2seq = {}
        for sequence in sequences:
            code2seq.setdefault(sequence.code, []).append(sequence.id)

        sequence_type_ids = sequence_type_obj.search(cursor, user, [
                ('code', 'in', code2seq.keys()),
                ], context=context)
        sequence_types = sequence_type_obj.browse(cursor, user,
                sequence_type_ids, context=context)

        res = {}
        for sequence_type in sequence_types:
            seq_ids = code2seq[sequence_type.code]
            for seq_id in seq_ids:
                res.setdefault(seq_id, []).append(sequence_type.id)

        return res

    def search_groups(self, cursor, user, name, clause, context=None):
        sequence_type_obj = self.pool.get('ir.sequence.type')
        ids = sequence_type_obj.search(cursor, user, [clause], order=[],
                context=context)
        seq_types = sequence_type_obj.browse(cursor, user, ids,
                context=context)
        codes = set(st.code for st in seq_types)
        return [('code', 'in', list(codes))]

Sequence()


class SequenceStrict(Sequence):
    # This empty class declaration is needed to inherit the groups
    # field
    _name = 'ir.sequence.strict'

SequenceStrict()

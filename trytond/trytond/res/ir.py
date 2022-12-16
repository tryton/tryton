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

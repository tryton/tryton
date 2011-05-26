#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import contextlib
import time
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval
from trytond.pyson import Eval, Get
from trytond.transaction import Transaction
from trytond.cache import Cache


class RuleGroup(ModelSQL, ModelView):
    "Rule group"
    _name = 'ir.rule.group'
    _description = __doc__
    name = fields.Char('Name', select=1)
    model = fields.Many2One('ir.model', 'Model', select=1,
            required=True)
    global_p = fields.Boolean('Global', select=1,
            help="Make the rule global \n" \
                    "so every users must follow this rule")
    default_p = fields.Boolean('Default', select=1,
            help="Add this rule to all users by default")
    rules = fields.One2Many('ir.rule', 'rule_group', 'Tests',
            help="The rule is satisfied if at least one test is True")
    groups = fields.Many2Many('ir.rule.group-res.group',
            'rule_group_id', 'group_id', 'Groups')
    users = fields.Many2Many('ir.rule.group-res.user',
            'rule_group_id', 'user_id', 'Users')
    perm_read = fields.Boolean('Read Access')
    perm_write = fields.Boolean('Write Access')
    perm_create = fields.Boolean('Create Access')
    perm_delete = fields.Boolean('Delete Access')

    def __init__(self):
        super(RuleGroup, self).__init__()
        self._order.insert(0, ('model', 'ASC'))
        self._order.insert(1, ('global_p', 'ASC'))
        self._order.insert(2, ('default_p', 'ASC'))
        self._sql_constraints += [
            ('global_default_exclusive', 'CHECK(NOT(global_p AND default_p))',
                'Global and Default are mutually exclusive!'),
        ]

    def default_global_p(self):
        return True

    def default_default_p(self):
        return False

    def default_perm_read(self):
        return True

    def default_perm_write(self):
        return True

    def default_perm_create(self):
        return True

    def default_perm_delete(self):
        return True

    def delete(self, ids):
        res = super(RuleGroup, self).delete(ids)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get.reset()
        return res

    def create(self, vals):
        res = super(RuleGroup, self).create(vals)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get.reset()
        return res

    def write(self, ids, vals):
        res = super(RuleGroup, self).write(ids, vals)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get.reset()
        return res

RuleGroup()


class Rule(ModelSQL, ModelView):
    "Rule"
    _name = 'ir.rule'
    _rec_name = 'field'
    _description = __doc__
    field = fields.Many2One('ir.model.field', 'Field',
       domain=[('model', '=', Get(Eval('_parent_rule_group', {}), 'model'))],
       select=1, required=True)
    operator = fields.Selection([
       ('=', '='),
       ('<>', '<>'),
       ('<=', '<='),
       ('>=', '>='),
       ('in', 'in'),
       ('child_of', 'child_of'),
       ], 'Operator', required=True, translate=False)
    operand = fields.Selection('get_operand','Operand', required=True)
    rule_group = fields.Many2One('ir.rule.group', 'Group', select=2,
       required=True, ondelete="CASCADE")

    def _operand_get(self, obj_name='', level=3, recur=None, root_tech='', root=''):
        res = {}
        if not obj_name:
            obj_name = 'res.user'
        res.update({"False": "False", "True": "True", "User": "user.id"})
        if not recur:
            recur = []
        with Transaction().set_context(language='en_US'):
            obj_fields = self.pool.get(obj_name).fields_get()
        key = obj_fields.keys()
        key.sort()
        for k in key:

            if obj_fields[k]['type'] in ('many2one'):
                res[root + '/' + obj_fields[k]['string']] = \
                        root_tech + '.' + k + '.id'

            elif obj_fields[k]['type'] in ('many2many', 'one2many'):
                res[root + '/' + obj_fields[k]['string']] = \
                        '[x.id for x in ' + root_tech + '.' + k + ']'
            else:
                res[root + '/' + obj_fields[k]['string']] = \
                        root_tech + '.' + k

            if (obj_fields[k]['type'] in recur) and (level>0):
                res.update(self._operand_get(obj_fields[k]['relation'],
                    level-1, recur, root_tech + '.' + k,
                    root + '/' + obj_fields[k]['string']))

        return res

    def get_operand(self):
        res = []
        operands = self._operand_get('res.user', level=1, recur=['many2one'],
                root_tech='user', root='User')
        for i in operands.keys():
            res.append((i, i))
        return res

    @Cache('ir_rule.domain_get')
    def domain_get(self, model_name, mode='read'):
        assert mode in ['read', 'write', 'create', 'delete'], \
                'Invalid domain mode for security'

        # root user above constraint
        if Transaction().user == 0:
            if not Transaction().context.get('user'):
                return '', []
            with Transaction().set_user(Transaction().context['user']):
                return self.domain_get(model_name)

        rule_group_obj = self.pool.get('ir.rule.group')
        model_obj = self.pool.get('ir.model')
        rule_group_user_obj = self.pool.get('ir.rule.group-res.user')
        rule_group_group_obj = self.pool.get('ir.rule.group-res.group')
        user_group_obj = self.pool.get('res.user-res.group')

        cursor = Transaction().cursor
        cursor.execute('SELECT r.id FROM "' + self._table + '" r ' \
                'JOIN "' + rule_group_obj._table + '" g ' \
                    "ON (g.id = r.rule_group) " \
                'JOIN "' + model_obj._table + '" m ON (g.model = m.id) ' \
                "WHERE m.model = %s "
                    "AND g.perm_" + mode + " "
                    "AND (g.id IN (" \
                            'SELECT rule_group_id ' \
                            'FROM "' + rule_group_user_obj._table + '" ' \
                                "WHERE user_id = %s " \
                            "UNION SELECT rule_group_id " \
                            'FROM "' + rule_group_group_obj._table + '" g_rel ' \
                                'JOIN "' + user_group_obj._table + '" u_rel ' \
                                    "ON (g_rel.group_id = u_rel.gid) " \
                                "WHERE u_rel.uid = %s) " \
                        "OR default_p " \
                        "OR g.global_p)",
                (model_name, Transaction().user, Transaction().user))
        ids = [x[0] for x in cursor.fetchall()]
        if not ids:
            return '', []
        obj = self.pool.get(model_name)
        clause = {}
        clause_global = {}
        operand2query = self._operand_get('res.user', level=1,
                recur=['many2one'], root_tech='user', root='User')
        # Use root user without context to prevent recursion
        user = Transaction().user
        with contextlib.nested(Transaction().set_user(0),
                Transaction().set_context(user=0)):
            for rule in self.browse(ids):
                operator = rule.operator
                if operator == '<>':
                    operator = '!='
                dom = safe_eval("[('%s', '%s', %s)]" % \
                        (rule.field.name, operator,
                            operand2query[rule.operand]), {
                                'user': self.pool.get('res.user').browse(user),
                                'time': time,
                                })

                if rule.rule_group['global_p']:
                    clause_global.setdefault(rule.rule_group.id, ['OR'])
                    clause_global[rule.rule_group.id].append(dom)
                else:
                    clause.setdefault(rule.rule_group.id, ['OR'])
                    clause[rule.rule_group.id].append(dom)

        query = ''
        val = []

        # Test if there is no rule_group that have no rule
        cursor.execute('SELECT g.id FROM "' + rule_group_obj._table + '" g ' \
                'JOIN "' + model_obj._table + '" m ON (g.model = m.id) ' \
            'WHERE m.model = %s ' \
                'AND (g.id NOT IN (SELECT rule_group ' \
                        'FROM "' + self._table + '")) ' \
                'AND (g.id IN (SELECT rule_group_id ' \
                        'FROM "' + rule_group_user_obj._table + '" ' \
                        'WHERE user_id = %s ' \
                        'UNION SELECT rule_group_id ' \
                        'FROM "' + rule_group_group_obj._table + '" g_rel ' \
                            'JOIN "' + user_group_obj._table + '" u_rel ' \
                                'ON g_rel.group_id = u_rel.gid ' \
                        'WHERE u_rel.uid = %s))', (model_name, user, user))
        fetchone = cursor.fetchone()
        if fetchone:
            group_id = fetchone[0]
            clause[group_id] = []
        clause = clause.values()
        clause.insert(0, 'OR')

        clause_global = clause_global.values()

        if clause_global:
            clause_global.insert(0, 'AND')
            clause = ['AND', clause_global, clause]

        query, val, _, _ = obj.search_domain(clause, active_test=False)

        return query, val

    def delete(self, ids):
        res = super(Rule, self).delete(ids)
        # Restart the cache on the domain_get method of ir.rule
        self.domain_get.reset()
        return res

    def create(self, vals):
        res = super(Rule, self).create(vals)
        # Restart the cache on the domain_get method of ir.rule
        self.domain_get.reset()
        return res

    def write(self, ids, vals):
        res = super(Rule, self).write(ids, vals)
        # Restart the cache on the domain_get method
        self.domain_get.reset()
        return res

Rule()

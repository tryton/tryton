#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Rule"
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import Cache, safe_eval
from trytond.pyson import Eval, Get
import time


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

    def default_global_p(self, cursor, user, context=None):
        return True

    def default_default_p(self, cursor, user, context=None):
        return False

    def default_perm_read(self, cursor, user, context=None):
        return True

    def default_perm_write(self, cursor, user, context=None):
        return True

    def default_perm_create(self, cursor, user, context=None):
        return True

    def default_perm_delete(self, cursor, user, context=None):
        return True

    def delete(self, cursor, user, ids, context=None):
        res = super(RuleGroup, self).delete(cursor, user, ids,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get(cursor.dbname)
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(RuleGroup, self).create(cursor, user, vals,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get(cursor.dbname)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(RuleGroup, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get(cursor.dbname)
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

    def _operand_get(self, cursor, user, obj_name='', level=3, recur=None, root_tech='', root=''):
        res = {}
        if not obj_name:
            obj_name = 'res.user'
        res.update({"False": "False", "True": "True", "User": "user.id"})
        if not recur:
            recur = []
        obj_fields = self.pool.get(obj_name).fields_get(cursor, user)
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
                res.update(self._operand_get(cursor, user,
                    obj_fields[k]['relation'], level-1,
                    recur, root_tech + '.' + k, root + '/' + \
                            obj_fields[k]['string']))

        return res

    def get_operand(self, cursor, user, context=None):
        res = []
        operands = self._operand_get(cursor, user, 'res.user', level=1,
                recur=['many2one'], root_tech='user', root='User')
        for i in operands.keys():
            res.append((i, i))
        return res

    @Cache('ir_rule.domain_get')
    def domain_get(self, cursor, user, model_name, mode='read', context=None):
        if context is None:
            context = {}
        assert mode in ['read', 'write', 'create', 'delete'], \
                'Invalid domain mode for security'

        # Fix for issue1661
        if (model_name in ('ir.sequence', 'ir.sequence.strict')
                and mode == 'read'):
            return '', []

        # root user above constraint
        if user == 0:
            if not context.get('user'):
                return '', []
            ctx = context.copy()
            del ctx['user']
            return self.domain_get(cursor, context['user'], model_name,
                    context=ctx)

        rule_group_obj = self.pool.get('ir.rule.group')
        model_obj = self.pool.get('ir.model')
        rule_group_user_obj = self.pool.get('ir.rule.group-res.user')
        rule_group_group_obj = self.pool.get('ir.rule.group-res.group')
        user_group_obj = self.pool.get('res.user-res.group')

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
                        "OR g.global_p)", (model_name, user, user))
        ids = [x[0] for x in cursor.fetchall()]
        if not ids:
            return '', []
        obj = self.pool.get(model_name)
        clause = {}
        clause_global = {}
        operand2query = self._operand_get(cursor, user, 'res.user', level=1,
                recur=['many2one'], root_tech='user', root='User')
        # Use root user without context to prevent recursion
        for rule in self.browse(cursor, 0, ids):
            dom = safe_eval("[('%s', '%s', %s)]" % \
                    (rule.field.name, rule.operator,
                        operand2query[rule.operand]),
                    {'user': self.pool.get('res.user').browse(cursor, 0,
                        user), 'time': time})

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

        query, val, _, _ = obj.search_domain(cursor, user,
                clause, active_test=False, context=context)

        return query, val

    def delete(self, cursor, user, ids, context=None):
        res = super(Rule, self).delete(cursor, user, ids, context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.domain_get(cursor.dbname)
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(Rule, self).create(cursor, user, vals, context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.domain_get(cursor.dbname)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Rule, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method
        self.domain_get(cursor.dbname)
        return res

Rule()

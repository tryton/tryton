#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
import time
import datetime

from ..model import ModelView, ModelSQL, fields
from ..tools import safe_eval
from ..transaction import Transaction
from ..cache import Cache
from ..pool import Pool
from ..backend import TableHandler

__all__ = [
    'RuleGroup', 'Rule',
    ]


class RuleGroup(ModelSQL, ModelView):
    "Rule group"
    __name__ = 'ir.rule.group'
    name = fields.Char('Name', select=True)
    model = fields.Many2One('ir.model', 'Model', select=True,
        required=True)
    global_p = fields.Boolean('Global', select=True,
        help="Make the rule global \nso every users must follow this rule")
    default_p = fields.Boolean('Default', select=True,
        help="Add this rule to all users by default")
    rules = fields.One2Many('ir.rule', 'rule_group', 'Tests',
        help="The rule is satisfied if at least one test is True")
    groups = fields.Many2Many('ir.rule.group-res.group',
        'rule_group', 'group', 'Groups')
    users = fields.Many2Many('ir.rule.group-res.user',
        'rule_group', 'user', 'Users')
    perm_read = fields.Boolean('Read Access')
    perm_write = fields.Boolean('Write Access')
    perm_create = fields.Boolean('Create Access')
    perm_delete = fields.Boolean('Delete Access')

    @classmethod
    def __setup__(cls):
        super(RuleGroup, cls).__setup__()
        cls._order.insert(0, ('model', 'ASC'))
        cls._order.insert(1, ('global_p', 'ASC'))
        cls._order.insert(2, ('default_p', 'ASC'))
        cls._sql_constraints += [
            ('global_default_exclusive', 'CHECK(NOT(global_p AND default_p))',
                'Global and Default are mutually exclusive!'),
        ]

    @staticmethod
    def default_global_p():
        return True

    @staticmethod
    def default_default_p():
        return False

    @staticmethod
    def default_perm_read():
        return True

    @staticmethod
    def default_perm_write():
        return True

    @staticmethod
    def default_perm_create():
        return True

    @staticmethod
    def default_perm_delete():
        return True

    @classmethod
    def delete(cls, groups):
        super(RuleGroup, cls).delete(groups)
        # Restart the cache on the domain_get method of ir.rule
        Pool().get('ir.rule')._domain_get_cache.clear()

    @classmethod
    def create(cls, vlist):
        res = super(RuleGroup, cls).create(vlist)
        # Restart the cache on the domain_get method of ir.rule
        Pool().get('ir.rule')._domain_get_cache.clear()
        return res

    @classmethod
    def write(cls, groups, vals):
        super(RuleGroup, cls).write(groups, vals)
        # Restart the cache on the domain_get method of ir.rule
        Pool().get('ir.rule')._domain_get_cache.clear()


class Rule(ModelSQL, ModelView):
    "Rule"
    __name__ = 'ir.rule'
    _rec_name = 'field'
    rule_group = fields.Many2One('ir.rule.group', 'Group', select=True,
       required=True, ondelete="CASCADE")
    domain = fields.Char('Domain', required=True,
        help='Domain is evaluated with "user" as the current user')
    _domain_get_cache = Cache('ir_rule.domain_get')

    @classmethod
    def __setup__(cls):
        super(Rule, cls).__setup__()
        cls._error_messages.update({
                'invalid_domain': 'Invalid domain in rule "%s".',
                })

    @classmethod
    def __register__(cls, module_name):
        super(Rule, cls).__register__(module_name)
        table = TableHandler(Transaction().cursor, cls, module_name)

        # Migration from 2.6: replace field, operator and operand by domain
        table.not_null_action('field', action='remove')
        table.not_null_action('operator', action='remove')
        table.not_null_action('operand', action='remove')

    @classmethod
    def validate(cls, rules):
        super(Rule, cls).validate(rules)
        cls.check_domain(rules)

    @classmethod
    def check_domain(cls, rules):
        ctx = cls._get_context()
        for rule in rules:
            try:
                value = safe_eval(rule.domain, ctx)
            except Exception:
                cls.raise_user_error('invalid_domain', (rule.rec_name,))
            if not isinstance(value, list):
                cls.raise_user_error('invalid_domain', (rule.rec_name,))
            else:
                try:
                    fields.domain_validate(value)
                except Exception:
                    cls.raise_user_error('invalid_domain', (rule.rec_name,))

    @staticmethod
    def _get_context():
        User = Pool().get('res.user')
        user_id = Transaction().user
        with Transaction().set_user(0, set_context=True):
            user = User(user_id)
        return {
            'user': user,
            'current_date': datetime.datetime.today(),
            'time': time,
            'context': Transaction().context,
            }

    @classmethod
    def domain_get(cls, model_name, mode='read'):
        assert mode in ['read', 'write', 'create', 'delete'], \
            'Invalid domain mode for security'

        # root user above constraint
        if Transaction().user == 0:
            if not Transaction().context.get('user'):
                return '', []
            with Transaction().set_user(Transaction().context['user']):
                return cls.domain_get(model_name, mode=mode)

        key = (model_name, mode)
        domain = cls._domain_get_cache.get(key)
        if domain:
            return domain

        pool = Pool()
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')
        RuleGroup_User = pool.get('ir.rule.group-res.user')
        RuleGroup_Group = pool.get('ir.rule.group-res.group')
        User_Group = pool.get('res.user-res.group')

        cursor = Transaction().cursor
        cursor.execute('SELECT r.id FROM "' + cls._table + '" r '
            'JOIN "' + RuleGroup._table + '" g '
                "ON (g.id = r.rule_group) "
            'JOIN "' + Model._table + '" m ON (g.model = m.id) '
            "WHERE m.model = %s "
                "AND g.perm_" + mode + " "
                "AND (g.id IN ("
                        'SELECT rule_group '
                        'FROM "' + RuleGroup_User._table + '" '
                        'WHERE "user" = %s '
                        "UNION SELECT rule_group "
                        'FROM "' + RuleGroup_Group._table + '" g_rel '
                        'JOIN "' + User_Group._table + '" u_rel '
                            'ON (g_rel."group" = u_rel."group") '
                        'WHERE u_rel."user" = %s) '
                    "OR default_p "
                    "OR g.global_p)",
                (model_name, Transaction().user, Transaction().user))
        ids = [x[0] for x in cursor.fetchall()]
        if not ids:
            cls._domain_get_cache.set(key, ('', []))
            return '', []
        obj = pool.get(model_name)
        clause = {}
        clause_global = {}
        user_id = Transaction().user
        ctx = cls._get_context()
        # Use root user without context to prevent recursion
        with contextlib.nested(Transaction().set_user(0),
                Transaction().set_context(user=0)):
            for rule in cls.browse(ids):
                assert rule.domain, ('Rule domain empty,'
                    'check if migration was done')
                dom = safe_eval(rule.domain, ctx)
                if rule.rule_group.global_p:
                    clause_global.setdefault(rule.rule_group.id, ['OR'])
                    clause_global[rule.rule_group.id].append(dom)
                else:
                    clause.setdefault(rule.rule_group.id, ['OR'])
                    clause[rule.rule_group.id].append(dom)

        # Test if there is no rule_group that have no rule
        cursor.execute('SELECT g.id FROM "' + RuleGroup._table + '" g '
                'JOIN "' + Model._table + '" m ON (g.model = m.id) '
            'WHERE m.model = %s '
                'AND (g.id NOT IN (SELECT rule_group '
                        'FROM "' + cls._table + '")) '
                'AND (g.id IN (SELECT rule_group '
                        'FROM "' + RuleGroup_User._table + '" '
                        'WHERE "user" = %s '
                        'UNION SELECT rule_group '
                        'FROM "' + RuleGroup_Group._table + '" g_rel '
                            'JOIN "' + User_Group._table + '" u_rel '
                                'ON g_rel."group" = u_rel."group" '
                        'WHERE u_rel."user" = %s))',
            (model_name, user_id, user_id))
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

        # Use root to prevent infinite recursion
        with contextlib.nested(Transaction().set_user(0),
                Transaction().set_context(active_test=False, user=0)):
            query, val = obj.search(clause, order=[], query_string=True)
        query = '("%s".id IN (%s))' % (obj._table, query)

        cls._domain_get_cache.set(key, (query, val))
        return query, val

    @classmethod
    def delete(cls, rules):
        super(Rule, cls).delete(rules)
        # Restart the cache on the domain_get method of ir.rule
        cls._domain_get_cache.clear()

    @classmethod
    def create(cls, vlist):
        res = super(Rule, cls).create(vlist)
        # Restart the cache on the domain_get method of ir.rule
        cls._domain_get_cache.clear()
        return res

    @classmethod
    def write(cls, rules, vals):
        super(Rule, cls).write(rules, vals)
        # Restart the cache on the domain_get method
        cls._domain_get_cache.clear()

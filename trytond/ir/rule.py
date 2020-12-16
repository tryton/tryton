# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from ..model import ModelView, ModelSQL, fields, EvalEnvironment, Check
from ..transaction import Transaction
from ..cache import Cache
from ..pool import Pool
from ..pyson import PYSONDecoder

__all__ = [
    'RuleGroup', 'Rule',
    ]


class RuleGroup(ModelSQL, ModelView):
    "Rule group"
    __name__ = 'ir.rule.group'
    name = fields.Char('Name', select=True)
    model = fields.Many2One('ir.model', 'Model', select=True,
        required=True, ondelete='CASCADE')
    global_p = fields.Boolean('Global', select=True,
        help="Make the rule global \nso every users must follow this rule")
    default_p = fields.Boolean('Default', select=True,
        help="Add this rule to all users by default")
    rules = fields.One2Many('ir.rule', 'rule_group', 'Tests',
        help="The rule is satisfied if at least one test is True")
    groups = fields.Many2Many('ir.rule.group-res.group',
        'rule_group', 'group', 'Groups')
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

        t = cls.__table__()
        cls._sql_constraints += [
            ('global_default_exclusive',
                Check(t, (t.global_p == False) | (t.default_p == False)),
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
    def write(cls, groups, vals, *args):
        super(RuleGroup, cls).write(groups, vals, *args)
        # Restart the cache on the domain_get method of ir.rule
        Pool().get('ir.rule')._domain_get_cache.clear()


class Rule(ModelSQL, ModelView):
    "Rule"
    __name__ = 'ir.rule'
    rule_group = fields.Many2One('ir.rule.group', 'Group', select=True,
       required=True, ondelete="CASCADE")
    domain = fields.Char('Domain', required=True,
        help='Domain is evaluated with a PYSON context containing:\n'
        '- "user" as the current user')
    _domain_get_cache = Cache('ir_rule.domain_get', context=False)

    @classmethod
    def __setup__(cls):
        super(Rule, cls).__setup__()
        cls._error_messages.update({
                'invalid_domain': 'Invalid domain in rule "%s".',
                })

    @classmethod
    def validate(cls, rules):
        super(Rule, cls).validate(rules)
        cls.check_domain(rules)

    @classmethod
    def check_domain(cls, rules):
        ctx = cls._get_context()
        for rule in rules:
            try:
                value = PYSONDecoder(ctx).decode(rule.domain)
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
        transaction = Transaction()
        user_id = transaction.user
        with transaction.set_context(_check_access=False, _datetime=None), \
                transaction.set_user(0):
            user = EvalEnvironment(User(user_id), User)
        return {
            'user': user,
            }

    @staticmethod
    def _get_cache_key():
        # _datetime value will be added to the domain
        return (Transaction().user, Transaction().context.get('_datetime'))

    @classmethod
    def domain_get(cls, model_name, mode='read'):
        assert mode in ['read', 'write', 'create', 'delete'], \
            'Invalid domain mode for security'

        # root user above constraint
        if Transaction().user == 0:
            if not Transaction().context.get('user'):
                return
            with Transaction().set_user(Transaction().context['user']):
                return cls.domain_get(model_name, mode=mode)

        key = (model_name, mode) + cls._get_cache_key()
        domain = cls._domain_get_cache.get(key, False)
        if domain is not False:
            return domain

        pool = Pool()
        RuleGroup = pool.get('ir.rule.group')
        Model = pool.get('ir.model')
        RuleGroup_Group = pool.get('ir.rule.group-res.group')
        User_Group = pool.get('res.user-res.group')

        cursor = Transaction().connection.cursor()
        rule_table = cls.__table__()
        rule_group = RuleGroup.__table__()
        rule_group_group = RuleGroup_Group.__table__()
        user_group = User_Group.__table__()
        model = Model.__table__()
        user_id = Transaction().user
        cursor.execute(*rule_table.join(rule_group,
                condition=rule_group.id == rule_table.rule_group
                ).join(model,
                condition=rule_group.model == model.id
                ).select(rule_table.id,
                where=(model.model == model_name)
                & (getattr(rule_group, 'perm_%s' % mode) == True)
                & (rule_group.id.in_(
                        rule_group_group.join(
                            user_group,
                            condition=(rule_group_group.group
                                == user_group.group)
                            ).select(rule_group_group.rule_group,
                            where=user_group.user == user_id)
                        )
                    | (rule_group.default_p == True)
                    | (rule_group.global_p == True)
                    )))
        ids = [x[0] for x in cursor.fetchall()]
        if not ids:
            cls._domain_get_cache.set(key, None)
            return
        clause = {}
        clause_global = {}
        ctx = cls._get_context()
        # Use root user without context to prevent recursion
        with Transaction().set_user(0), \
                Transaction().set_context(user=0):
            for rule in cls.browse(ids):
                assert rule.domain, ('Rule domain empty,'
                    'check if migration was done')
                dom = PYSONDecoder(ctx).decode(rule.domain)
                if rule.rule_group.global_p:
                    clause_global.setdefault(rule.rule_group.id, ['OR'])
                    clause_global[rule.rule_group.id].append(dom)
                else:
                    clause.setdefault(rule.rule_group.id, ['OR'])
                    clause[rule.rule_group.id].append(dom)

        # Test if there is no rule_group that have no rule
        cursor.execute(*rule_group.join(model,
                condition=rule_group.model == model.id
                ).select(rule_group.id,
                where=(model.model == model_name)
                & ~rule_group.id.in_(rule_table.select(rule_table.rule_group))
                & rule_group.id.in_(rule_group_group.join(user_group,
                        condition=rule_group_group.group == user_group.group
                        ).select(rule_group_group.rule_group,
                        where=user_group.user == user_id))))
        fetchone = cursor.fetchone()
        if fetchone:
            group_id = fetchone[0]
            clause[group_id] = []
        clause = list(clause.values())
        if clause:
            clause.insert(0, 'OR')

        clause_global = list(clause_global.values())

        if clause_global:
            clause_global.insert(0, 'AND')

        if clause and clause_global:
            clause = ['AND', clause_global, clause]
        elif clause_global:
            clause = clause_global

        cls._domain_get_cache.set(key, clause)
        return clause

    @classmethod
    def query_get(cls, model_name, mode='read'):
        pool = Pool()
        Model = pool.get(model_name)

        domain = cls.domain_get(model_name, mode=mode)

        # Use root to prevent infinite recursion
        with Transaction().set_user(0), \
                Transaction().set_context(active_test=False, user=0):
            return Model.search(domain, order=[], query=True)

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
    def write(cls, rules, vals, *args):
        super(Rule, cls).write(rules, vals, *args)
        # Restart the cache on the domain_get method
        cls._domain_get_cache.clear()

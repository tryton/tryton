# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import groupby

from efficient_apriori import apriori

from trytond.cache import Cache
from trytond.model import Index, ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import TimeDelta
from trytond.transaction import Transaction


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    product_association_rule_transactions_up_to = fields.TimeDelta(
        "Transactions Up to",
        domain=['OR',
            ('product_association_rule_transactions_up_to', '=', None),
            ('product_association_rule_transactions_up_to', '>=', TimeDelta()),
            ])
    product_association_rule_min_support = fields.Float(
        "Minimum Support", required=True,
        domain=[
            ('product_association_rule_min_support', '>=', 0),
            ('product_association_rule_min_support', '<=', 1),
            ],
        help="The minimum frequency of which the items in the rule "
        "appear together in the data set.")
    product_association_rule_min_confidence = fields.Float(
        "Minimum Confidence", required=True,
        domain=[
            ('product_association_rule_min_confidence', '>=', 0),
            ('product_association_rule_min_confidence', '<=', 1),
            ],
        help="The minimum probability of the rule.")
    product_association_rule_max_length = fields.Integer(
        "The maximal number of products for a rule.", required=True,
        domain=[
            ('product_association_rule_max_length', '>', 0),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product_recommendation_method.selection.append(
            ('association_rule', "Association Rule"))

    @classmethod
    def default_product_association_rule_min_support(cls):
        return 0.3

    @classmethod
    def default_product_association_rule_min_confidence(cls):
        return 0.5

    @classmethod
    def default_product_association_rule_max_length(cls):
        return 8


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @fields.depends(methods=['_recommended_products_association_rule'])
    def on_change_with_recommended_products(self, name=None):
        return super().on_change_with_recommended_products(name=name)

    @fields.depends('lines')
    def _recommended_products_association_rule(self):
        pool = Pool()
        Rule = pool.get('sale.product.association.rule')
        if self.lines:
            products = [
                l.product for l in self.lines
                if getattr(l, 'product', None)]
            yield from Rule.recommend(products)


class ProductAssociationRule(ModelSQL, ModelView):
    __name__ = 'sale.product.association.rule'

    antecedents = fields.Many2Many(
        'sale.product.association.rule.antecedent', 'rule', 'product',
        "Antecedents")
    antecedent_names = fields.Function(fields.Char(
            "Antecedents"), 'get_product_names')
    consequents = fields.Many2Many(
        'sale.product.association.rule.consequent', 'rule', 'product',
        "Consequents")
    consequent_names = fields.Function(fields.Char(
            "Consequents"), 'get_product_names')
    confidence = fields.Float(
        "Confidence",
        domain=[
            ('confidence', '>=', 0),
            ('confidence', '<=', 1),
            ],
        help="Probability of consequents, given antecedents.")
    support = fields.Float(
        "Support",
        domain=[
            ('support', '>=', 0),
            ('support', '<=', 1),
            ],
        help="The frequency of consequents and antecedents appear together.")
    lift = fields.Float(
        "Lift",
        domain=[
            ('lift', '>=', 0),
            ],
        help="If equals to 1, the two occurrences are "
        "independent of each other.\n"
        "If greater than 1, the degree to which the two occurrences are "
        "dependent on one another.\n"
        "If less than 1, the items are substitute to each other.")
    conviction = fields.Float(
        "Conviction",
        domain=[
            ('conviction', '>=', 0),
            ],
        help="The frequency that the rule makes an incorrect prediction.")
    _find_rules_cache = Cache(__name__ + '._find_rules', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    t,
                    (t.lift, Index.Range(order='DESC')),
                    (t.conviction, Index.Range(order='ASC'))),
                Index(
                    t,
                    (t.id, Index.Range(cardinality='high')),
                    (t.lift, Index.Range(order='DESC'))),
                })

    def get_product_names(self, name):
        return ', '.join(
            p.rec_name for p in getattr(self, name[:-len('_names')] + 's'))

    @classmethod
    def clean(cls, domain=None):
        table = cls.__table__()
        cursor = Transaction().connection.cursor()
        if domain:
            query = cls.search(domain, query=True)
            where = table.id.in_(query)
        else:
            where = None
        cursor.execute(*table.delete(where=where))

    @classmethod
    def transactions(cls):
        "Yield transaction as sets of product ids"
        yield from cls.transactions_sale()

    @classmethod
    def transactions_sale(cls, domain=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')
        Configuration = pool.get('sale.configuration')

        config = Configuration(1)
        today = Date.today()
        date = today
        if not config.product_association_rule_transactions_up_to:
            return
        date -= config.product_association_rule_transactions_up_to

        lines = SaleLine.search([
                ('sale.sale_date', '>=', date),
                ('sale.state', 'not in', ['draft', 'cancelled']),
                domain or [],
                ],
            order=[('sale.id', 'DESC')])
        for sale, lines in groupby(lines, lambda l: l.sale):
            yield {
                l.product.id for l in lines
                if l.product and Sale._is_recommendable_product(l.product)}

    @classmethod
    def compute(cls):
        pool = Pool()
        Configuration = pool.get('sale.configuration')

        config = Configuration(1)
        cls.clean()
        cls._find_rules_cache.clear()
        transactions = cls.transactions()

        _, rules = apriori(
            transactions,
            min_support=config.product_association_rule_min_support,
            min_confidence=config.product_association_rule_min_confidence,
            max_length=config.product_association_rule_max_length)

        cls.save([cls.from_rule(rule) for rule in rules])

    @classmethod
    def from_rule(cls, rule):
        return cls(
            antecedents=rule.lhs,
            consequents=rule.rhs,
            confidence=rule.confidence,
            support=rule.support,
            lift=rule.lift,
            conviction=rule.conviction)

    @classmethod
    def _find_rules(cls, products, domain, lift='DESC'):
        product_ids = {p.id for p in products}
        key = (sorted(product_ids), domain, lift)
        rules = cls._find_rules_cache.get(key)
        if rules is not None:
            rules = cls.browse(rules)
        else:
            rules = cls.search([
                    ('antecedents', 'in', list(product_ids)),
                    domain,
                    ],
                order=[('lift', lift), ('conviction', 'ASC')])
            rules = [
                r for r in rules
                if set(map(int, r.antecedents)) <= product_ids]
            cls._find_rules_cache.set(key, [r.id for r in rules])

        products = set(products)
        for rule in rules:
            yield from (set(rule.consequents) - products)
            products.update(rule.consequents)

    @classmethod
    def recommend(cls, products):
        return cls._find_rules(products, [('lift', '>', 1)], lift='DESC')

    @classmethod
    def substitute(cls, products):
        return cls._find_rules(products, [('lift', '<', 1)], lift='DESC')


class ProductAssociationRuleAntecedent(ModelSQL):
    __name__ = 'sale.product.association.rule.antecedent'

    rule = fields.Many2One(
        'sale.product.association.rule', "Rule",
        required=True, ondelete='CASCADE')
    product = fields.Many2One(
        'product.product', "Product", required=True, ondelete='CASCADE')


class ProductAssociationRuleConsequent(ModelSQL):
    __name__ = 'sale.product.association.rule.consequent'

    rule = fields.Many2One(
        'sale.product.association.rule', "Rule",
        required=True, ondelete='CASCADE')
    product = fields.Many2One(
        'product.product', "Product", required=True, ondelete='CASCADE')


class ProductAssociationRulePOS(metaclass=PoolMeta):
    __name__ = 'sale.product.association.rule'

    @classmethod
    def transactions(cls):
        yield from super().transactions()
        yield from cls.transactions_pos()

    @classmethod
    def transactions_pos(cls, domain=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Sale = pool.get('sale.point.sale')
        SaleLine = pool.get('sale.point.sale.line')
        Configuration = pool.get('sale.configuration')

        config = Configuration(1)
        today = Date.today()
        date = today
        if not config.product_association_rule_transactions_up_to:
            return
        date -= config.product_association_rule_transactions_up_to

        lines = SaleLine.search([
                ('sale.date', '>=', date),
                ('sale.state', 'not in', ['open', 'cancelled']),
                domain or [],
                ],
            order=[('sale.id', 'DESC')])
        for sale, lines in groupby(lines, lambda l: l.sale):
            yield {
                l.product.id for l in lines
                if l.product and Sale._is_recommendable_product(l.product)}

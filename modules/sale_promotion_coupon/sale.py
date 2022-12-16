# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal
from sql.aggregate import Count
from sql.conditionals import Case, Coalesce

from trytond.i18n import gettext
from trytond.model import (
    ModelSQL, ModelView, Workflow, fields, DeactivableMixin)
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction

from .exceptions import DuplicateError


class Promotion(metaclass=PoolMeta):
    __name__ = 'sale.promotion'

    coupons = fields.One2Many('sale.promotion.coupon', 'promotion', "Coupons")

    def get_pattern(self, sale):
        pattern = super(Promotion, self).get_pattern(sale)
        if sale.coupons:
            pattern['coupons'] = [c.coupon.id for c in sale.coupons]
        return pattern

    def match(self, pattern):
        if self.coupons:
            pattern = pattern.copy()
            coupons = pattern.pop('coupons', [])
            if not set(coupons).intersection({c.id for c in self.coupons}):
                return False
        return super(Promotion, self).match(pattern)


class PromotionCoupon(ModelSQL, ModelView):
    "Promotion Coupon"
    __name__ = 'sale.promotion.coupon'

    name = fields.Char("Name", required=True)
    number_of_use = fields.Integer(
        "Number of Use", required=True,
        help="How much times a coupon number can be used.\n"
        "0 or below for no limit.")
    per_party = fields.Boolean(
        "Per Party", help="Check to count usage per party.")
    numbers = fields.One2Many(
        'sale.promotion.coupon.number', 'coupon', "Numbers")
    promotion = fields.Many2One('sale.promotion', "Promotion", required=True)

    @classmethod
    def default_number_of_use(cls):
        return 0

    @classmethod
    def default_per_party(cls):
        return False


class PromotionCouponNumber(DeactivableMixin, ModelSQL, ModelView):
    "Promotion Coupon Number"
    __name__ = 'sale.promotion.coupon.number'
    _rec_name = 'number'

    number = fields.Char("Number", required=True)
    coupon = fields.Many2One(
        'sale.promotion.coupon', "Coupon", select=True, required=True)

    @classmethod
    def __setup__(cls):
        super(PromotionCouponNumber, cls).__setup__()
        cls.active = fields.Function(
            fields.Boolean("Active"), 'get_active', searcher='search_active')

    @classmethod
    def _active_query(cls):
        pool = Pool()
        Coupon = pool.get('sale.promotion.coupon')
        Sale = pool.get('sale.sale')
        Sale_Number = pool.get('sale.sale-sale.promotion.coupon.number')
        table = cls.__table__()
        coupon = Coupon.__table__()
        sale = Sale.__table__()
        sale_number = Sale_Number.__table__()
        context = Transaction().context
        party = context.get('party')

        query = (table
            .join(sale_number, 'LEFT',
                condition=table.id == sale_number.number)
            .join(coupon, condition=table.coupon == coupon.id))

        if party:
            query = query.join(sale, 'LEFT',
                condition=(sale_number.sale == sale.id)
                & (sale.party == party))
            active = Case(
                ((coupon.number_of_use > 0) & (coupon.per_party),
                    Count(sale.id) < coupon.number_of_use),
                ((coupon.number_of_use > 0)
                    & ~Coalesce(coupon.per_party, False),
                    Count(sale_number.sale) < coupon.number_of_use),
                else_=Literal(True))
        else:
            active = Case(
                ((coupon.number_of_use > 0)
                    & ~Coalesce(coupon.per_party, False),
                    Count(sale_number.sale) < coupon.number_of_use),
                else_=Literal(True))

        query = query.select(
            group_by=[table.id, coupon.number_of_use, coupon.per_party])
        return query, table, active

    @classmethod
    def get_active(cls, numbers, name):
        cursor = Transaction().connection.cursor()

        query, table, active = cls._active_query()
        query.columns = [table.id, active]

        result = {}
        for sub_numbers in grouped_slice(numbers):
            query.where = reduce_ids(table.id, map(int, sub_numbers))
            cursor.execute(*query)
            result.update(dict(cursor.fetchall()))
        return result

    @classmethod
    def search_active(cls, name, clause):
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        query, table, active = cls._active_query()
        query.columns = [table.id]
        query.having = Operator(active, value)
        return [('id', 'in', query)]

    @classmethod
    def validate(cls, numbers):
        super(PromotionCouponNumber, cls).validate(numbers)
        cls.check_unique(numbers)

    @classmethod
    def check_unique(cls, numbers):
        duplicates = []
        for sub_numbers in grouped_slice(numbers):
            domain = ['OR']
            for number in sub_numbers:
                domain.append([
                        ('number', '=', number.number),
                        ('id', '!=', number.id),
                        ('coupon.promotion.company', '=',
                            number.coupon.promotion.company.id),
                        ])
            duplicates.extend(cls.search(domain))
        if duplicates:
            numbers = ', '.join(n.number for n in duplicates[:5])
            if len(duplicates) > 5:
                numbers += '...'
            raise DuplicateError(
                gettext('sale_promotion_coupon.msg_duplicate_numbers',
                    numbers=numbers))


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    coupons = fields.Many2Many(
        'sale.sale-sale.promotion.coupon.number', 'sale', 'number', "Coupons",
        domain=[
            ('coupon.promotion.company', '=', Eval('company', -1)),
            ],
        context={
            'party': Eval('party', -1),
            },
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state', 'company', 'party'])

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, sales):
        for sale in sales:
            if sale.coupons:
                sale.coupons = []
        cls.save(sales)
        super(Sale, cls).cancel(sales)


class Sale_PromotionCouponNumber(ModelSQL):
    "Sale - Promotion Coupon Number"
    __name__ = 'sale.sale-sale.promotion.coupon.number'

    sale = fields.Many2One(
        'sale.sale', "Sale", required=True, select=True, ondelete='CASCADE')
    number = fields.Many2One(
        'sale.promotion.coupon.number', "Number",
        required=True, ondelete='RESTRICT')

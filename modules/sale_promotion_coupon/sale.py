# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from sql import Literal
from sql.aggregate import Count
from sql.conditionals import Case, Coalesce
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Exclude, ModelSQL, ModelView, Workflow, fields)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.sql.functions import DateRange
from trytond.sql.operators import RangeOverlap
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction

from .exceptions import PromotionCouponNumberDatesError


class Promotion(metaclass=PoolMeta):
    __name__ = 'sale.promotion'

    coupons = fields.One2Many(
        'sale.promotion.coupon', 'promotion', "Coupons",
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    def get_pattern(self, sale):
        pattern = super().get_pattern(sale)
        if sale.coupons:
            pattern['coupons'] = [c.coupon.id for c in sale.coupons]
        return pattern

    def match(self, pattern):
        if self.coupons:
            pattern = pattern.copy()
            coupons = pattern.pop('coupons', [])
            if not set(coupons).intersection({c.id for c in self.coupons}):
                return False
        return super().match(pattern)

    @classmethod
    def on_modification(cls, mode, promotions, field_names=None):
        pool = Pool()
        Number = pool.get('sale.promotion.coupon.number')
        super().on_modification(mode, promotions, field_names=field_names)
        if mode == 'write' and field_names & {'start_date', 'end_date'}:
            Number.save(list(cls._update_coupon_number_dates(promotions)))

    @classmethod
    def _update_coupon_number_dates(cls, promotions):
        for promotion in promotions:
            for coupon in promotion.coupons:
                for number in coupon.numbers:
                    number.on_change_coupon()
                    yield number


class PromotionCoupon(ModelSQL, ModelView):
    __name__ = 'sale.promotion.coupon'

    number_of_use = fields.Integer(
        "Number of Use", required=True,
        help="How much times a coupon number can be used.\n"
        "0 or below for no limit.")
    per_party = fields.Boolean(
        "Per Party", help="Check to count usage per party.")
    numbers = fields.One2Many(
        'sale.promotion.coupon.number', 'coupon', "Numbers",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        filter=[
            ('active', 'in', [True, False]),  # Show inactive numbers
            ])
    promotion = fields.Many2One(
        'sale.promotion', "Promotion", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    company = fields.Many2One('company.company', "Company", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('promotion')

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Promotion = pool.get('sale.promotion.coupon')
        table = cls.__table__()
        promotion = Promotion.__table__()
        table_h = cls.__table_handler__(module)
        cursor = Transaction().connection.cursor()

        company_exist = table_h.column_exist('company')

        super().__register__(module)

        # Migration from 7.2: add company
        if not company_exist:
            cursor.execute(*table.update(
                    [table.company],
                    [promotion.select(
                            promotion.company,
                            where=promotion.id == table.promotion)]))

        # Migration from 7.4: remove name
        table_h.not_null_action('name', 'remove')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_number_of_use(cls):
        return 0

    @classmethod
    def default_per_party(cls):
        return False

    def get_rec_name(self, name):
        return self.promotion.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('promotion.rec_name', *clause[1:])]


class PromotionCouponNumber(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'sale.promotion.coupon.number'
    _rec_name = 'number'

    number = fields.Char("Number", required=True)
    coupon = fields.Many2One(
        'sale.promotion.coupon', "Coupon", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    company = fields.Many2One('company.company', "Company", required=True)
    start_date = fields.Date("Start Date",
        domain=['OR',
            ('start_date', '<=', If(~Eval('end_date', None),
                    dt.date.max,
                    Eval('end_date', dt.date.max))),
            ('start_date', '=', None),
            ])
    end_date = fields.Date("End Date",
        domain=['OR',
            ('end_date', '>=', If(~Eval('start_date', None),
                    dt.date.min,
                    Eval('start_date', dt.date.min))),
            ('end_date', '=', None),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('dates_number_overlap',
                Exclude(t,
                    (t.company, Equal),
                    (t.number, Equal),
                    (DateRange(t.start_date, t.end_date, '[]'), RangeOverlap)),
                'sale_promotion_coupon.msg_duplicate_numbers'),
            ]
        cls.__access__.add('coupon')
        cls.active = fields.Function(
            cls.active, 'get_active', searcher='search_active')

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Coupon = pool.get('sale.promotion.coupon')
        Promotion = pool.get('sale.promotion')
        table = cls.__table__()
        coupon = Coupon.__table__()
        promotion = Promotion.__table__()
        table_h = cls.__table_handler__(module)
        cursor = Transaction().connection.cursor()

        start_date_exists = table_h.column_exist('start_date')
        end_date_exists = table_h.column_exist('end_date')
        company_exist = table_h.column_exist('company')

        super().__register__(module)

        # Migration from 7.2: add start_date and end_date
        if not start_date_exists:
            cursor.execute(*table.update(
                    [table.start_date],
                    [coupon
                        .join(promotion,
                            condition=coupon.promotion == promotion.id)
                        .select(
                            promotion.start_date,
                            where=coupon.id == table.coupon)]))
        if not end_date_exists:
            cursor.execute(*table.update(
                    [table.end_date],
                    [coupon
                        .join(promotion,
                            condition=coupon.promotion == promotion.id)
                        .select(
                            promotion.end_date,
                            where=coupon.id == table.coupon)]))

        # Migration from 7.2: add company
        if not company_exist:
            cursor.execute(*table.update(
                    [table.company],
                    [coupon
                        .join(promotion,
                            condition=coupon.promotion == promotion.id)
                        .select(
                            promotion.company,
                            where=coupon.id == table.coupon)]))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_start_date(cls):
        return Pool().get('ir.date').today()

    @fields.depends(
        'coupon', '_parent_coupon.promotion',
        '_parent_coupon._parent_promotion.start_date',
        '_parent_coupon._parent_promotion.end_date',
        'start_date', 'end_date')
    def on_change_coupon(self):
        if self.coupon and self.coupon.promotion:
            if start_date := self.coupon.promotion.start_date:
                if not self.start_date or self.start_date < start_date:
                    self.start_date = start_date
            if end_date := self.coupon.promotion.end_date:
                if not self.end_date or self.end_date > end_date:
                    self.end_date = end_date

    @classmethod
    def _active_query(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        Coupon = pool.get('sale.promotion.coupon')
        Sale = pool.get('sale.sale')
        Sale_Number = pool.get('sale.sale-sale.promotion.coupon.number')
        table = cls.__table__()
        coupon = Coupon.__table__()
        sale = Sale.__table__()
        sale_number = Sale_Number.__table__()
        context = Transaction().context
        party = context.get('party')
        if isinstance(party, int):
            party = [party]
        today = Date.today()

        query = (table
            .join(sale_number, 'LEFT',
                condition=table.id == sale_number.number)
            .join(coupon, condition=table.coupon == coupon.id))

        if party:
            query = query.join(sale, 'LEFT',
                condition=(sale_number.sale == sale.id)
                & (sale.party.in_(party)))
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

        active &= Coalesce(table.start_date, dt.date.min) <= today
        active &= Coalesce(table.end_date, dt.date.max) >= today

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
            result.update(dict(cursor))
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
        super().validate(numbers)
        cls.check_dates(numbers)

    @classmethod
    def check_dates(cls, numbers):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        for number in numbers:
            start_date = number.coupon.promotion.start_date or dt.date.min
            end_date = number.coupon.promotion.end_date or dt.date.max
            if number.start_date and number.start_date < start_date:
                raise PromotionCouponNumberDatesError(gettext(
                        'sale_promotion_coupon'
                        '.msg_promotion_coupon_number_start_date',
                        number=number.rec_name,
                        start_date=lang.strftime(start_date)))
            if number.end_date and number.end_date > end_date:
                raise PromotionCouponNumberDatesError(gettext(
                        'sale_promotion_coupon'
                        '.msg_promotion_coupon_number_end_date',
                        number=number.rec_name,
                        end_date=lang.strftime(end_date)))


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    coupons = fields.Many2Many(
        'sale.sale-sale.promotion.coupon.number', 'sale', 'number', "Coupons",
        domain=[
            ('coupon.promotion.company', '=', Eval('company', -1)),
            ],
        context={
            'party': Eval('coupon_parties', []),
            },
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends={'coupon_parties'})
    coupon_parties = fields.Function(fields.Many2Many(
            'party.party', None, None, "Coupon Parties",
            context={
                'company': Eval('company', -1),
                }),
        'on_change_with_coupon_parties')

    @fields.depends(methods=['_coupon_parties'])
    def on_change_with_coupon_parties(self, name=None):
        return list(self._coupon_parties())

    @fields.depends('party')
    def _coupon_parties(self):
        parties = set()
        if self.party:
            parties.add(self.party)
        return parties

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, sales):
        for sale in sales:
            if sale.coupons:
                sale.coupons = []
        cls.save(sales)
        super().cancel(sales)


class Sale_PromotionCouponNumber(ModelSQL):
    __name__ = 'sale.sale-sale.promotion.coupon.number'

    sale = fields.Many2One(
        'sale.sale', "Sale", required=True, ondelete='CASCADE')
    number = fields.Many2One(
        'sale.promotion.coupon.number', "Number",
        required=True, ondelete='RESTRICT')

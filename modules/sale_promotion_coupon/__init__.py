# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import sale

__all__ = ['register']


def register():
    Pool.register(
        sale.Promotion,
        sale.PromotionCoupon,
        sale.PromotionCouponNumber,
        sale.Sale,
        sale.Sale_PromotionCouponNumber,
        module='sale_promotion_coupon', type_='model')
    Pool.register(
        module='sale_promotion_coupon', type_='wizard')
    Pool.register(
        module='sale_promotion_coupon', type_='report')

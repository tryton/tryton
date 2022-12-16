# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class SalePromotionCouponPaymentTestCase(ModuleTestCase):
    "Test Sale Promotion Coupon Payment module"
    module = 'sale_promotion_coupon_payment'


del ModuleTestCase

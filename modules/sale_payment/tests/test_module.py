# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class AccountPaymentTestCase(ModuleTestCase):
    'Test Sale Payment module'
    module = 'sale_payment'

    @with_transaction()
    def test_sale_payment_confirm_cron(self):
        "Test running sale payment_confirm without sales"
        pool = Pool()
        Sale = pool.get('sale.sale')

        Sale.payment_confirm()


del ModuleTestCase

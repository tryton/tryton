# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class WebShopTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Web Shop module'
    module = 'web_shop'
    extras = [
        'account_tax_rule_country', 'product_attribute', 'product_image',
        'sale_price_list']

    @with_transaction()
    def test_cancel_abandoned(self):
        "Test cancel abandoned sale"
        pool = Pool()
        WebShop = pool.get('web.shop')
        Party = pool.get('party.party')
        Sale = pool.get('sale.sale')

        guest = Party(name="Guest")
        guest.save()
        company = create_company()
        with set_company(company):
            web_shop = WebShop(
                name="Test",
                guest_party=guest,
                sale_draft_abandon_delay=dt.timedelta(),
                )
            web_shop.save()

            sale = web_shop.get_sale()
            sale.save()
            self.assertEqual(sale.state, 'draft')

            Sale.web_cancel_draft_abandoned()

            sale = Sale(sale.id)
            self.assertEqual(sale.state, 'cancelled')

    @with_transaction()
    def test_not_cancel_abandoned_no_delay(self):
        "Test not cancel abandoned sale without delay"
        pool = Pool()
        WebShop = pool.get('web.shop')
        Party = pool.get('party.party')
        Sale = pool.get('sale.sale')

        guest = Party(name="Guest")
        guest.save()
        company = create_company()
        with set_company(company):
            web_shop = WebShop(
                name="Test",
                guest_party=guest,
                sale_draft_abandon_delay=None,
                )
            web_shop.save()

            sale = web_shop.get_sale()
            sale.save()
            self.assertEqual(sale.state, 'draft')

            Sale.web_cancel_draft_abandoned()

            sale = Sale(sale.id)
            self.assertEqual(sale.state, 'draft')


del ModuleTestCase

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import MagicMock

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class SaleInvoiceDateTestCase(ModuleTestCase):
    'Test Sale Invoice Date module'
    module = 'sale_invoice_date'
    extras = ['sale_invoice_grouping']

    @with_transaction()
    def test_invoice_grouping(self):
        "Test fields to group invoice"
        pool = Pool()
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')

        sale = Sale()
        invoice = MagicMock(spec=Invoice)

        fields = sale._get_invoice_grouping_fields(invoice)

        self.assertIn('invoice_date', fields)
        self.assertLessEqual(fields, Invoice._fields.keys())


del ModuleTestCase

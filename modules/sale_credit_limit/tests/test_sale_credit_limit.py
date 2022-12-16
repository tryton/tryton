# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool
from trytond.exceptions import UserWarning

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart, get_fiscalyear
from trytond.modules.account_invoice.tests import set_invoice_sequences


class SaleCreditLimitTestCase(ModuleTestCase):
    'Test SaleCreditLimit module'
    module = 'sale_credit_limit'

    @with_transaction()
    def test_check_credit_limit(self):
        'Test check_credit_limit'
        pool = Pool()
        Account = pool.get('account.account')
        Move = pool.get('account.move')
        Journal = pool.get('account.journal')
        Party = pool.get('party.party')
        Sale = pool.get('sale.sale')
        PaymentTerm = pool.get('account.invoice.payment_term')
        Configuration = pool.get('account.configuration')
        FiscalYear = pool.get('account.fiscalyear')
        Invoice = pool.get('account.invoice')

        company = create_company()
        with set_company(company):
            create_chart(company)
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            period = fiscalyear.periods[0]

            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ])
            revenue, = Account.search([
                    ('type.revenue', '=', True),
                    ])
            journal, = Journal.search([], limit=1)
            party, = Party.create([{
                        'name': 'Party',
                        'addresses': [
                            ('create', [{}]),
                            ],
                        'credit_limit_amount': Decimal('100'),
                        }])
            Move.create([{
                        'journal': journal.id,
                        'period': period.id,
                        'date': period.start_date,
                        'lines': [
                            ('create', [{
                                        'debit': Decimal('100'),
                                        'account': receivable.id,
                                        'party': party.id,
                                        }, {
                                        'credit': Decimal('100'),
                                        'account': revenue.id,
                                        }]),
                            ],
                        }])
            payment_term, = PaymentTerm.create([{
                        'name': 'Test',
                        'lines': [
                            ('create', [{
                                        'type': 'remainder',
                                        }])
                            ],
                        }])
            config = Configuration(1)
            config.default_category_account_revenue = revenue
            config.save()
            sale, = Sale.create([{
                        'party': party.id,
                        'company': company.id,
                        'payment_term': payment_term.id,
                        'currency': company.currency.id,
                        'invoice_address': party.addresses[0].id,
                        'shipment_address': party.addresses[0].id,
                        'lines': [
                            ('create', [{
                                        'description': 'Test',
                                        'quantity': 1,
                                        'unit_price': Decimal('50'),
                                        }]),
                            ],
                        }])
            self.assertEqual(party.credit_amount, Decimal('100'))
            Sale.quote([sale])
            # Test limit reaches
            self.assertRaises(UserWarning, Sale.confirm, [sale])
            self.assertEqual(party.credit_amount, Decimal('100'))
            # Increase limit
            party.credit_limit_amount = Decimal('200')
            party.save()
            # process should work
            Sale.confirm([sale])
            self.assertEqual(sale.state, 'confirmed')
            self.assertEqual(party.credit_amount, Decimal('150'))

            # Process
            Sale.process([sale])
            # Decrease limit
            party.credit_limit_amount = Decimal('100')
            party.save()
            # process should still work as sale is already processing
            Sale.process([sale])

            # Increase quantity invoiced does not change the credit amount
            invoice, = sale.invoices
            invoice_line, = invoice.lines
            invoice_line.quantity += 1
            invoice_line.save()
            Invoice.post([invoice])
            self.assertEqual(party.credit_amount, Decimal('150'))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        SaleCreditLimitTestCase))
    return suite

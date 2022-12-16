#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import unittest
import doctest
from itertools import chain
from lxml import etree
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class AccountPaymentSepaTestCase(unittest.TestCase):
    'Test Account Payment SEPA module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('account_payment_sepa')
        self.bank = POOL.get('bank')
        self.bank_account = POOL.get('bank.account')
        self.bank_number = POOL.get('bank.account.number')
        self.company = POOL.get('company.company')
        self.currency = POOL.get('currency.currency')
        self.date = POOL.get('ir.date')
        self.mandate = POOL.get('account.payment.sepa.mandate')
        self.party = POOL.get('party.party')
        self.payment = POOL.get('account.payment')
        self.payment_group = POOL.get('account.payment.group')
        self.payment_journal = POOL.get('account.payment.journal')
        self.process_payment = POOL.get('account.payment.process',
            type='wizard')
        self.user = POOL.get('res.user')

    def test0005views(self):
        'Test views'
        test_view('account_payment_sepa')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def validate_file(self, flavor, kind):
        'Test generated files are valid'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            euro, = self.currency.create([{
                        'name': 'Euro',
                        'symbol': 'EUR',
                        'code': 'EUR',
                        }])
            company.currency = euro
            company.party.sepa_creditor_identifier = 'BE68539007547034'
            company.party.save()
            company.save()
            bank_party = self.party(name='European Bank')
            bank_party.save()
            bank = self.bank(party=bank_party, bic='BICODEBBXXX')
            bank.save()
            customer = self.party(name='Customer')
            customer.save()
            company_account, customer_account = self.bank_account.create([{
                        'bank': bank,
                        'owners': [('add', [company.party])],
                        'numbers': [('create', [{
                                        'type': 'iban',
                                        'number': 'ES8200000000000000000000',
                                        }])]}, {
                        'bank': bank,
                        'owners': [('add', [customer])],
                        'numbers': [('create', [{
                                        'type': 'iban',
                                        'number': 'ES3600000000050000000001',
                                        }])]}])
            customer_account_number, = customer_account.numbers
            self.mandate.create([{
                        'company': company,
                        'party': customer,
                        'account_number': customer_account_number,
                        'identification': 'MANDATE',
                        'type': 'recurrent',
                        'signature_date': self.date.today(),
                        'state': 'validated',
                        }])

            company_bank_number, = company_account.numbers
            journal = self.payment_journal()
            journal.name = flavor
            journal.company = company
            journal.currency = company.currency
            journal.process_method = 'sepa'
            journal.sepa_bank_account_number = company_bank_number
            journal.sepa_payable_flavor = 'pain.001.001.03'
            journal.sepa_receivable_flavor = 'pain.008.001.02'
            setattr(journal, 'sepa_%s_flavor' % kind, flavor)
            journal.save()

            payment, = self.payment.create([{
                        'company': company,
                        'party': customer,
                        'journal': journal,
                        'kind': kind,
                        'amount': Decimal('1000.0'),
                        'state': 'approved',
                        'description': 'PAYMENT',
                        'date': self.date.today(),
                        }])

            session_id, _, _ = self.process_payment.create()
            process_payment = self.process_payment(session_id)
            with Transaction().set_context(active_ids=[payment.id]):
                _, data = process_payment.do_process(None)
            group, = self.payment_group.browse(data['res_id'])
            sepa_string = group.sepa_message.encode('utf-8')
            sepa_file = etree.fromstring(sepa_string)
            schema_file = os.path.join(os.path.dirname(__file__),
                '%s.xsd' % flavor)
            schema = etree.XMLSchema(etree.parse(schema_file))
            schema.assertValid(sepa_file)

    def test_pain001_001_03(self):
        'Test pain001.001.03 xsd validation'
        self.validate_file('pain.001.001.03', 'payable')

    def test_pain001_001_05(self):
        'Test pain001.001.05 xsd validation'
        self.validate_file('pain.001.001.05', 'payable')

    def test_pain008_001_02(self):
        'Test pain008.001.02 xsd validation'
        self.validate_file('pain.008.001.02', 'receivable')

    def test_pain008_001_04(self):
        'Test pain008.001.04 xsd validation'
        self.validate_file('pain.008.001.04', 'receivable')


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    from trytond.modules.account.tests import test_account
    for test in chain(test_company.suite(), test_account.suite()):
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountPaymentSepaTestCase))
    return suite

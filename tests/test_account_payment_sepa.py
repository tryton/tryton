#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import unittest
import doctest
from itertools import chain
from lxml import etree
from decimal import Decimal
from io import BytesIO

from mock import Mock, patch

import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.modules.account_payment_sepa.payment import CAMT054


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

    def setup_environment(self):
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
        return {
            'company': company,
            'bank': bank,
            'customer': customer,
            }

    def setup_accounts(self, bank, company, customer):
        return self.bank_account.create([{
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

    def setup_mandate(self, company, customer, account):
        return self.mandate.create([{
                    'company': company,
                    'party': customer,
                    'account_number': account.numbers[0],
                    'identification': 'MANDATE',
                    'type': 'recurrent',
                    'signature_date': self.date.today(),
                    'state': 'validated',
                    }])[0]

    def setup_journal(self, flavor, kind, company, account):
        journal = self.payment_journal()
        journal.name = flavor
        journal.company = company
        journal.currency = company.currency
        journal.process_method = 'sepa'
        journal.sepa_bank_account_number = account.numbers[0]
        journal.sepa_payable_flavor = 'pain.001.001.03'
        journal.sepa_receivable_flavor = 'pain.008.001.02'
        setattr(journal, 'sepa_%s_flavor' % kind, flavor)
        journal.save()
        return journal

    def validate_file(self, flavor, kind):
        'Test generated files are valid'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            environment = self.setup_environment()
            company = environment['company']
            bank = environment['bank']
            customer = environment['customer']
            company_account, customer_account = self.setup_accounts(bank,
                company, customer)
            self.setup_mandate(company, customer, customer_account)
            journal = self.setup_journal(flavor, kind, company,
                company_account)

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
            message, = group.sepa_messages
            sepa_string = message.message.encode('utf-8')
            sepa_xml = etree.fromstring(sepa_string)
            schema_file = os.path.join(os.path.dirname(__file__),
                '%s.xsd' % flavor)
            schema = etree.XMLSchema(etree.parse(schema_file))
            schema.assertValid(sepa_xml)

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

    def test_sepa_mandate_sequence(self):
        'Test SEPA mandate sequence'
        Configuration = POOL.get('account.configuration')
        Sequence = POOL.get('ir.sequence')
        Party = POOL.get('party.party')
        Mandate = POOL.get('account.payment.sepa.mandate')
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            party = Party(name='Test')
            party.save()
            mandate = Mandate(party=party)
            mandate.save()
            self.assertFalse(mandate.identification)

            sequence = Sequence(name='Test',
                code='account.payment.sepa.mandate')
            sequence.save()
            config = Configuration(1)
            config.sepa_mandate_sequence = sequence
            config.save()

            mandate = Mandate(party=party)
            mandate.save()
            self.assertTrue(mandate.identification)

    def test_identification_unique(self):
        'Test unique identification constraint'
        Party = POOL.get('party.party')
        Mandate = POOL.get('account.payment.sepa.mandate')
        same_id = '1'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            party = Party(name='Test')
            party.save()
            mandate = Mandate(party=party, identification=same_id)
            mandate.save()

            for i in range(2):
                mandate = Mandate(party=party)
                mandate.save()

            mandate = Mandate(party=party, identification='')
            mandate.save()
            self.assertEqual(mandate.identification, None)

            Mandate.write([mandate], {
                    'identification': '',
                    })
            self.assertEqual(mandate.identification, None)

            self.assertRaises(UserError, Mandate.create, [{
                        'party': party.id,
                        'identification': same_id,
                        }])

    def test_payment_sepa_bank_account_number(self):
        'Test Payment.sepa_bank_account_number'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            Payment = POOL.get('account.payment')
            Mandate = POOL.get('account.payment.sepa.mandate')
            AccountNumber = POOL.get('bank.account.number')
            Party = POOL.get('party.party')
            BankAccount = POOL.get('bank.account')

            account_number = AccountNumber()
            mandate = Mandate(account_number=account_number)
            payment = Payment(kind='receivable', sepa_mandate=mandate)

            self.assertEqual(id(payment.sepa_bank_account_number),
                id(account_number))

            other_account_number = AccountNumber(type='other')
            iban_account_number = AccountNumber(type='iban')
            bank_account = BankAccount(
                numbers=[other_account_number, iban_account_number])
            party = Party(
                bank_accounts=[bank_account])
            payment = Payment(kind='payable', party=party)

            self.assertEqual(id(payment.sepa_bank_account_number),
                id(iban_account_number))

    def test_payment_sequence_type(self):
        'Test payment sequence type'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            environment = self.setup_environment()
            company = environment['company']
            bank = environment['bank']
            customer = environment['customer']
            company_account, customer_account = self.setup_accounts(bank,
                company, customer)
            self.setup_mandate(company, customer, customer_account)
            journal = self.setup_journal('pain.008.001.02', 'receivable',
                company, company_account)

            payment, = self.payment.create([{
                        'company': company,
                        'party': customer,
                        'journal': journal,
                        'kind': 'receivable',
                        'amount': Decimal('1000.0'),
                        'state': 'approved',
                        'description': 'PAYMENT',
                        'date': self.date.today(),
                        }])

            session_id, _, _ = self.process_payment.create()
            process_payment = self.process_payment(session_id)
            with Transaction().set_context(active_ids=[payment.id]):
                _, data = process_payment.do_process(None)

            self.assertEqual(payment.sepa_mandate_sequence_type, 'FRST')

            payments = self.payment.create([{
                        'company': company,
                        'party': customer,
                        'journal': journal,
                        'kind': 'receivable',
                        'amount': Decimal('2000.0'),
                        'state': 'approved',
                        'description': 'PAYMENT',
                        'date': self.date.today(),
                        }, {
                        'company': company,
                        'party': customer,
                        'journal': journal,
                        'kind': 'receivable',
                        'amount': Decimal('3000.0'),
                        'state': 'approved',
                        'description': 'PAYMENT',
                        'date': self.date.today(),
                        },
                    ])

            session_id, _, _ = self.process_payment.create()
            process_payment = self.process_payment(session_id)
            payment_ids = [p.id for p in payments]
            with Transaction().set_context(active_ids=payment_ids):
                _, data = process_payment.do_process(None)

            for payment in payments:
                self.assertEqual(payment.sepa_mandate_sequence_type, 'RCUR')

    def handle_camt054(self, flavor):
        'Handle camt.054'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            Message = POOL.get('account.payment.sepa.message')

            message_file = os.path.join(os.path.dirname(__file__),
                '%s.xml' % flavor)
            message = open(message_file).read()
            namespace = Message.get_namespace(message)
            self.assertEqual(namespace,
                'urn:iso:std:iso:20022:tech:xsd:%s' % flavor)

            payment = Mock()
            Payment = Mock()
            Payment.search.return_value = [payment]

            handler = CAMT054(BytesIO(message), Payment)

            self.assertEqual(handler.msg_id, 'AAAASESS-FP-00001')
            Payment.search.assert_called_with([
                    ('sepa_end_to_end_id', '=', 'MUELL/FINP/RA12345'),
                    ('kind', '=', 'payable'),
                    ])
            Payment.succeed.assert_called_with([payment])

            payment.reset_mock()
            Payment.reset_mock()
            with patch.object(CAMT054, 'is_returned') as is_returned:
                is_returned.return_value = True
                handler = CAMT054(BytesIO(message), Payment)

                payment.save.assert_called_with()
                Payment.fail.assert_called_with([payment])

    def test_camt054_001_01(self):
        'Test camt.054.001.01 handling'
        self.handle_camt054('camt.054.001.01')

    def test_camt054_001_02(self):
        'Test camt.054.001.02 handling'
        self.handle_camt054('camt.054.001.02')

    def test_camt054_001_03(self):
        'Test camt.054.001.03 handling'
        self.handle_camt054('camt.054.001.03')

    def test_camt054_001_04(self):
        'Test camt.054.001.04 handling'
        self.handle_camt054('camt.054.001.04')


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

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import unittest
from decimal import Decimal
from io import BytesIO, open
from lxml import etree
from unittest.mock import Mock, patch

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.modules.account_payment_sepa.payment import CAMT054
from trytond.pool import Pool

from trytond.modules.currency.tests import create_currency
from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart


def setup_environment():
    pool = Pool()
    Address = pool.get('party.address')
    Party = pool.get('party.party')
    Bank = pool.get('bank')
    Identifier = pool.get('party.identifier')

    currency = create_currency('EUR')
    company = create_company(currency=currency)
    sepa = Identifier(party=company.party, code='ES23ZZZ47690558N',
        type='eu_at_02')
    sepa.save()
    bank_party = Party(name='European Bank')
    bank_party.save()
    bank = Bank(party=bank_party, bic='BICODEBBXXX')
    bank.save()
    customer = Party(name='Customer')
    address = Address(street='street', zip='1234', city='City')
    customer.addresses = [address]
    customer.save()
    return {
        'company': company,
        'bank': bank,
        'customer': customer,
        }


def setup_accounts(bank, company, customer):
    pool = Pool()
    Account = pool.get('bank.account')
    return Account.create([{
                'bank': bank,
                'owners': [('add', [company.party])],
                'currency': company.currency.id,
                'numbers': [('create', [{
                                'type': 'iban',
                                'number': 'ES8200000000000000000000',
                                }])]}, {
                'bank': bank,
                'owners': [('add', [customer])],
                'currency': company.currency.id,
                'numbers': [('create', [{
                                'type': 'iban',
                                'number': 'ES3600000000050000000001',
                                }])]}])


def setup_mandate(company, customer, account):
    pool = Pool()
    Mandate = pool.get('account.payment.sepa.mandate')
    Date = pool.get('ir.date')
    return Mandate.create([{
                'company': company,
                'party': customer,
                'account_number': account.numbers[0],
                'identification': 'MANDATE',
                'type': 'recurrent',
                'sequence_type_rcur': False,
                'signature_date': Date.today(),
                'state': 'validated',
                }])[0]


def setup_journal(flavor, kind, company, account):
    pool = Pool()
    Journal = pool.get('account.payment.journal')
    journal = Journal()
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


def validate_file(flavor, kind, xsd=None):
    'Test generated files are valid'
    pool = Pool()
    Payment = pool.get('account.payment')
    PaymentGroup = pool.get('account.payment.group')
    Date = pool.get('ir.date')
    ProcessPayment = pool.get('account.payment.process', type='wizard')

    if xsd is None:
        xsd = flavor

    environment = setup_environment()
    company = environment['company']
    bank = environment['bank']
    customer = environment['customer']
    with set_company(company):
        company_account, customer_account = setup_accounts(
            bank, company, customer)
        setup_mandate(company, customer, customer_account)
        journal = setup_journal(flavor, kind, company, company_account)

        payment, = Payment.create([{
                    'company': company,
                    'party': customer,
                    'journal': journal,
                    'kind': kind,
                    'amount': Decimal('1000.0'),
                    'state': 'approved',
                    'description': 'PAYMENT',
                    'date': Date.today(),
                    }])

        session_id, _, _ = ProcessPayment.create()
        process_payment = ProcessPayment(session_id)
        with Transaction().set_context(
                active_model=Payment.__name__, active_ids=[payment.id]):
            _, data = process_payment.do_process(None)
        group, = PaymentGroup.browse(data['res_id'])
        message, = group.sepa_messages
        assert message.type == 'out', message.type
        assert message.state == 'waiting', message.state
        sepa_string = bytes(message.message)
        sepa_xml = etree.fromstring(sepa_string)
        schema_file = os.path.join(os.path.dirname(__file__),
            '%s.xsd' % xsd)
        schema = etree.XMLSchema(etree.parse(schema_file))
        schema.assertValid(sepa_xml)


class AccountPaymentSepaTestCase(ModuleTestCase):
    'Test Account Payment SEPA module'
    module = 'account_payment_sepa'

    @with_transaction()
    def test_pain001_001_03(self):
        'Test pain001.001.03 xsd validation'
        validate_file('pain.001.001.03', 'payable')

    @with_transaction()
    def test_pain001_001_05(self):
        'Test pain001.001.05 xsd validation'
        validate_file('pain.001.001.05', 'payable')

    @with_transaction()
    def test_pain001_003_03(self):
        'Test pain001.003.03 xsd validation'
        validate_file('pain.001.003.03', 'payable')

    @with_transaction()
    def test_pain008_001_02(self):
        'Test pain008.001.02 xsd validation'
        validate_file('pain.008.001.02', 'receivable')

    @with_transaction()
    def test_pain008_001_04(self):
        'Test pain008.001.04 xsd validation'
        validate_file('pain.008.001.04', 'receivable')

    @with_transaction()
    def test_pain008_003_02(self):
        'Test pain008.003.02 xsd validation'
        validate_file('pain.008.003.02', 'receivable')

    @with_transaction()
    def test_sepa_mandate_sequence(self):
        'Test SEPA mandate sequence'
        pool = Pool()
        Configuration = pool.get('account.configuration')
        Sequence = pool.get('ir.sequence')
        Party = pool.get('party.party')
        Mandate = pool.get('account.payment.sepa.mandate')

        party = Party(name='Test')
        party.save()

        company = create_company()
        with set_company(company):
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

    @with_transaction()
    def test_identification_unique(self):
        'Test unique identification constraint'
        pool = Pool()
        Party = pool.get('party.party')
        Mandate = pool.get('account.payment.sepa.mandate')

        same_id = '1'

        party = Party(name='Test')
        party.save()

        company = create_company()
        with set_company(company):
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

    @with_transaction()
    def test_payment_sepa_bank_account_number(self):
        'Test Payment.sepa_bank_account_number'
        pool = Pool()
        Payment = pool.get('account.payment')
        Mandate = pool.get('account.payment.sepa.mandate')
        AccountNumber = pool.get('bank.account.number')
        Party = pool.get('party.party')
        BankAccount = pool.get('bank.account')

        company = create_company()
        with set_company(company):
            create_chart(company)
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

    @with_transaction()
    def test_payment_sequence_type(self):
        'Test payment sequence type'
        pool = Pool()
        Date = pool.get('ir.date')
        Payment = pool.get('account.payment')
        ProcessPayment = pool.get('account.payment.process', type='wizard')

        environment = setup_environment()
        company = environment['company']
        bank = environment['bank']
        customer = environment['customer']
        with set_company(company):
            company_account, customer_account = setup_accounts(
                bank, company, customer)
            mandate = setup_mandate(company, customer, customer_account)
            journal = setup_journal('pain.008.001.02', 'receivable',
                company, company_account)

            self.assertFalse(mandate.has_payments)
            self.assertEqual(mandate.sequence_type, 'FRST')
            mandate.sequence_type_rcur = True
            self.assertEqual(mandate.sequence_type, 'RCUR')
            mandate.sequence_type_rcur = False

            payment, = Payment.create([{
                        'company': company,
                        'party': customer,
                        'journal': journal,
                        'kind': 'receivable',
                        'amount': Decimal('1000.0'),
                        'state': 'approved',
                        'description': 'PAYMENT',
                        'date': Date.today(),
                        }])

            session_id, _, _ = ProcessPayment.create()
            process_payment = ProcessPayment(session_id)
            with Transaction().set_context(
                    active_model=Payment.__name__, active_ids=[payment.id]):
                _, data = process_payment.do_process(None)

            self.assertEqual(payment.sepa_mandate_sequence_type, 'FRST')
            self.assertTrue(payment.sepa_mandate.has_payments)

            payments = Payment.create([{
                        'company': company,
                        'party': customer,
                        'journal': journal,
                        'kind': 'receivable',
                        'amount': Decimal('2000.0'),
                        'state': 'approved',
                        'description': 'PAYMENT',
                        'date': Date.today(),
                        }, {
                        'company': company,
                        'party': customer,
                        'journal': journal,
                        'kind': 'receivable',
                        'amount': Decimal('3000.0'),
                        'state': 'approved',
                        'description': 'PAYMENT',
                        'date': Date.today(),
                        },
                    ])

            session_id, _, _ = ProcessPayment.create()
            process_payment = ProcessPayment(session_id)
            payment_ids = [p.id for p in payments]
            with Transaction().set_context(
                    active_model=Payment.__name__, active_ids=payment_ids):
                _, data = process_payment.do_process(None)

            for payment in payments:
                self.assertEqual(payment.sepa_mandate_sequence_type, 'RCUR')

    @with_transaction()
    def handle_camt054(self, flavor):
        'Handle camt.054'
        pool = Pool()
        Message = pool.get('account.payment.sepa.message')

        message_file = os.path.join(os.path.dirname(__file__),
            '%s.xml' % flavor)
        with open(message_file, 'rb') as fp:
            message = fp.read()
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

            Payment.save.assert_called_with([payment])
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

    @with_transaction()
    def test_sepa_mandate_report(self):
        'Test sepa mandate report'
        pool = Pool()
        Report = pool.get('account.payment.sepa.mandate', type='report')

        environment = setup_environment()
        company = environment['company']
        bank = environment['bank']
        customer = environment['customer']
        with set_company(company):
            company_account, customer_account = setup_accounts(
                bank, company, customer)
            mandate = setup_mandate(company, customer, customer_account)

            oext, content, _, _ = Report.execute([mandate.id], {})
            self.assertEqual(oext, 'odt')
            self.assertTrue(content)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountPaymentSepaTestCase))
    return suite

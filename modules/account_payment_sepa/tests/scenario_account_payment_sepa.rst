=============================
Account Payment SEPA Scenario
=============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Report
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     'account_payment_sepa', create_company, create_chart, create_fiscalyear)

    >>> Bank = Model.get('bank')
    >>> BankAccount = Model.get('bank.account')
    >>> Mandate = Model.get('account.payment.sepa.mandate')
    >>> Message = Model.get('account.payment.sepa.message')
    >>> Party = Model.get('party.party')
    >>> Payment = Model.get('account.payment')
    >>> PaymentJournal = Model.get('account.payment.journal')

    >>> company = get_company()
    >>> accounts = get_accounts()

Create parties::

    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Setup SEPA Identifier::

    >>> identifier = company.party.identifiers.new()
    >>> identifier.type = 'eu_at_02'
    >>> identifier.code = 'ES23ZZZ47690558N'
    >>> company.party.save()

Create bank accounts::

    >>> bank_party = Party(name="EU Bank")
    >>> bank_party.save()

    >>> company_bank = Bank(party=bank_party, bic='CTBKBEBX')
    >>> company_bank.save()
    >>> company_account = BankAccount(bank=company_bank)
    >>> company_account.owners.append(company.party)
    >>> company_account_number = company_account.numbers.new()
    >>> company_account_number.type = 'iban'
    >>> company_account_number.number = 'BE70953368654125'
    >>> company_account.save()

    >>> customer_bank = Bank(party=bank_party, bic='KREDBEBB')
    >>> customer_bank.save()
    >>> customer_account = BankAccount(bank=customer_bank)
    >>> customer_account.owners.append(customer)
    >>> customer_account_number = customer_account.numbers.new()
    >>> customer_account_number.type = 'iban'
    >>> customer_account_number.number = 'BE85735556927306'
    >>> customer_account.save()

    >>> supplier_account = BankAccount(bank=company_bank)
    >>> supplier_account.owners.append(supplier)
    >>> supplier_account_number = supplier_account.numbers.new()
    >>> supplier_account_number.type = 'iban'
    >>> supplier_account_number.number = 'BE07131673267766'
    >>> supplier_account.save()

Create mandate::

    >>> mandate = Mandate(party=customer)
    >>> mandate.account_number = customer_account.numbers[0]
    >>> mandate.identification = 'MANDATE'
    >>> mandate.type = 'recurrent'
    >>> mandate.click('request')
    >>> mandate.state
    'requested'

    >>> mandate_report = Report('account.payment.sepa.mandate')
    >>> _ = mandate_report.execute([mandate])

    >>> mandate.signature_date = today
    >>> mandate.click('validate_mandate')
    >>> mandate.state
    'validated'

Create payment journal::

    >>> payment_journal = PaymentJournal(name="Journal")
    >>> payment_journal.process_method = 'sepa'
    >>> payment_journal.sepa_bank_account_number = company_account.numbers[0]
    >>> payment_journal.sepa_payable_flavor = 'pain.001.001.03'
    >>> payment_journal.sepa_receivable_flavor = 'pain.008.001.02'
    >>> payment_journal.save()

Create payments::

    >>> payments = []
    >>> payment = Payment(party=customer, kind='receivable')
    >>> payment.journal = payment_journal
    >>> payment.amount = Decimal('100.00')
    >>> payment.date = today
    >>> payment.save()
    >>> payment.click('submit')
    >>> payments.append(payment)

    >>> payment = Payment(party=supplier, kind='payable')
    >>> payment.journal = payment_journal
    >>> payment.amount = Decimal('500.00')
    >>> payment.date = today
    >>> payment.save()
    >>> payment.click('submit')
    >>> payment.click('approve')
    >>> payments.append(payment)

Process payments::

    >>> process_payment = Payment.click(payments, 'process_wizard')
    >>> groups, = process_payment.actions
    >>> len(groups)
    2
    >>> messages = [m for g in groups for m in g.sepa_messages]
    >>> len(messages)
    2

    >>> message_report = Report('account.payment.sepa.message')
    >>> _ = message_report.execute(messages)

    >>> Message.click(messages, 'do')
    >>> [m.state for m in messages]
    ['done', 'done']

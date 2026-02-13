==============================
Invoice Payment Means Scenario
==============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['account_payment_sepa', 'account_invoice'], create_company, create_chart)

    >>> Bank = Model.get('bank')
    >>> BankAccount = Model.get('bank.account')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> PaymentJournal = Model.get('account.payment.journal')

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create party::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

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

    >>> supplier_bank1 = Bank(party=bank_party, bic='KREDBEBB')
    >>> supplier_bank1.save()
    >>> supplier_account1 = BankAccount(bank=supplier_bank1)
    >>> supplier_account1.owners.append(Party(supplier.id))
    >>> supplier_account1_number = supplier_account1.numbers.new()
    >>> supplier_account1_number.type = 'iban'
    >>> supplier_account1_number.number = 'BE85735556927306'
    >>> supplier_account1.save()
    >>> supplier_bank2 = Bank(party=bank_party, bic='CITIBEBX')
    >>> supplier_bank2.save()
    >>> supplier_account2 = BankAccount(bank=supplier_bank2)
    >>> supplier_account2.owners.append(Party(supplier.id))
    >>> supplier_account2_number = supplier_account2.numbers.new()
    >>> supplier_account2_number.type = 'iban'
    >>> supplier_account2_number.number = 'BE96570728435605'
    >>> supplier_account2.save()

Create payment journal::

    >>> payment_journal = PaymentJournal(name="SEPA", process_method='sepa')
    >>> payment_journal.sepa_bank_account_number = company_account.numbers[0]
    >>> payment_journal.sepa_payable_flavor = 'pain.001.001.03'
    >>> payment_journal.sepa_receivable_flavor = 'pain.008.001.02'
    >>> payment_journal.save()

Create a supplier invoice with a payment means::

    >>> invoice = Invoice(type='in')
    >>> invoice.invoice_date = today
    >>> invoice.party = supplier
    >>> line = invoice.lines.new()
    >>> line.account = accounts['expense']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('10.0000')
    >>> _ = invoice.payment_means.new(instrument=supplier_account2)
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Try to pay with a different bank account::

    >>> line_to_pay, = invoice.lines_to_pay
    >>> pay_line = Wizard('account.move.line.pay', [line_to_pay])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = pay_line.actions[0]
    >>> payment.sepa_payable_bank_account_number, = supplier_account1.numbers
    >>> payment.click('submit')
    Traceback (most recent call last):
        ...
    PaymentMeanWarning: ...

Pay with no bank account::

    >>> payment.sepa_payable_bank_account_number = None
    >>> payment.click('submit')
    >>> payment.state
    'submitted'
    >>> payment.click('approve')
    >>> _ = payment.click('process_wizard')
    >>> assertEqual(
    ...     payment.sepa_payable_bank_account_number,
    ...     supplier_account2.numbers[0])

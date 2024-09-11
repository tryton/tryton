==================================
Invoice Alternative Payee Scenario
==================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('account_invoice', create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> Journal = Model.get('account.journal')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()

    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])

    >>> payment_method = PaymentMethod()
    >>> payment_method.name = "Cash"
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = accounts['cash']
    >>> payment_method.debit_account = accounts['cash']
    >>> payment_method.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> party1 = Party(name="Party 1")
    >>> party1.save()
    >>> party2 = Party(name="Party 2")
    >>> party2.save()
    >>> party3 = Party(name="Party 3")
    >>> party3.save()

Post customer invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party1
    >>> invoice.alternative_payees.append(Party(party2.id))
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(10)
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> len(invoice.lines_to_pay)
    1
    >>> invoice.amount_to_pay
    Decimal('10.00')

    >>> party1.reload()
    >>> party1.receivable
    Decimal('0.0')
    >>> party2.reload()
    >>> party2.receivable
    Decimal('10.00')
    >>> party3.reload()
    >>> party3.receivable
    Decimal('0.0')

Copying invoice with single alternative payee is kept::

    >>> duplicate_inv, = invoice.duplicate()
    >>> assertEqual(duplicate_inv.alternative_payees, invoice.alternative_payees)

Set another payee::

    >>> delegate = Wizard(
    ...     'account.invoice.lines_to_pay.delegate', [invoice])
    >>> delegate_lines, = delegate.actions
    >>> delegate_lines.form.party = party3
    >>> delegate_lines.execute('delegate')

    >>> invoice.reload()
    >>> invoice.state
    'posted'
    >>> len(invoice.lines_to_pay)
    3
    >>> invoice.amount_to_pay
    Decimal('10.00')

    >>> party1.reload()
    >>> party1.receivable
    Decimal('0.0')
    >>> party2.reload()
    >>> party2.receivable
    Decimal('0.0')
    >>> party3.reload()
    >>> party3.receivable
    Decimal('10.00')

Pay the invoice::

    >>> pay = invoice.click('pay')
    >>> pay.form.payee = party3
    >>> pay.form.amount = Decimal('10.00')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> pay.state
    'end'
    >>> invoice.state
    'paid'
    >>> len(invoice.payment_lines)
    1
    >>> len(invoice.reconciliation_lines)
    1

Copying invoice with many alternative payees remove them::

    >>> duplicate_inv, = invoice.duplicate()
    >>> duplicate_inv.alternative_payees
    []

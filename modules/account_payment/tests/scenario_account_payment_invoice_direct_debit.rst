===========================================
Account Payment Party Direct Debit Scenario
===========================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> payment_direct_debit = globals().get('payment_direct_debit', False)
    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['account_payment', 'account_invoice'], create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> Invoice = Model.get('account.invoice')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create party::

    >>> party = Party(name='Supplier')
    >>> party.payment_direct_debit = payment_direct_debit
    >>> party.save()

Create supplier invoice::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> assertEqual(invoice.payment_direct_debit, payment_direct_debit)
    >>> line = invoice.lines.new()
    >>> line.account = accounts['expense']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('50.0000')
    >>> invoice.click('post')
    >>> line_to_pay, = invoice.lines_to_pay
    >>> assertEqual(line_to_pay.payment_direct_debit, payment_direct_debit)

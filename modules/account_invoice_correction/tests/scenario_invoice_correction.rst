===========================
Invoice Correction Scenario
===========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     'account_invoice_correction', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.description = "Revenue 1"
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('30')
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.description = "Revenue 2"
    >>> line.quantity = 10
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Correct invoice::

    >>> correct = invoice.click('correct')
    >>> correct.form.lines.extend(correct.form.lines.find(
    ...         [('description', '=', "Revenue 1")]))
    >>> correct.execute('correct')
    >>> invoices, = correct.actions
    >>> invoice, = invoices
    >>> [(l.quantity, l.unit_price) for l in invoice.lines]
    [(-5.0, Decimal('30')), (5.0, Decimal('30'))]

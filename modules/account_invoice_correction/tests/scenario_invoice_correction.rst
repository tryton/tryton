===========================
Invoice Correction Scenario
===========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Install account_invoice::

    >>> config = activate_modules('account_invoice_correction')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> company.party.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
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
    u'posted'

Correct invoice::

    >>> correct = Wizard('account.invoice.correct', [invoice])
    >>> correct.form.lines.extend(correct.form.lines.find(
    ...         [('description', '=', "Revenue 1")]))
    >>> correct.execute('correct')
    >>> invoices, = correct.actions
    >>> invoice, = invoices
    >>> [(l.quantity, l.unit_price) for l in invoice.lines]
    [(-5.0, Decimal('30')), (5.0, Decimal('30'))]

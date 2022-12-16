=================================
Invoice Reschedule Lines Scenario
=================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

Activate modules::

    >>> config = activate_modules('account_invoice')

    >>> Invoice = Model.get('account.invoice')
    >>> Journal = Model.get('account.journal')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])

    >>> payment_method = PaymentMethod()
    >>> payment_method.name = "Cash"
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = accounts['cash']
    >>> payment_method.debit_account = accounts['cash']
    >>> payment_method.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Post customer invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
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

Reschedule line::

    >>> reschedule = Wizard(
    ...     'account.invoice.lines_to_pay.reschedule', [invoice])
    >>> reschedule_lines, = reschedule.actions
    >>> reschedule_lines.form.total_amount
    Decimal('10.00')
    >>> reschedule_lines.form.start_date = period.end_date
    >>> reschedule_lines.form.frequency ='monthly'
    >>> reschedule_lines.form.number = 2
    >>> reschedule_lines.execute('preview')
    >>> reschedule_lines.execute('reschedule')

    >>> invoice.reload()
    >>> invoice.state
    'posted'
    >>> len(invoice.lines_to_pay)
    4
    >>> len([l for l in invoice.lines_to_pay if not l.reconciliation])
    2
    >>> invoice.amount_to_pay
    Decimal('10.00')

Pay the invoice::

    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.amount = Decimal('10.00')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> pay.state
    'end'
    >>> invoice.state
    'paid'
    >>> len(invoice.reconciliation_lines)
    1

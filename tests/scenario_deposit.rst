================
Deposit Scenario
================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.modules.account_deposit.tests.tools import \
    ...     add_deposit_accounts
    >>> today = datetime.date.today()

Install account_deposit::

    >>> config = activate_modules('account_deposit')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = add_deposit_accounts(get_accounts(company))

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create payment_term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create deposit invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice(party=party, payment_term=payment_term)
    >>> line = invoice.lines.new()
    >>> line.account = accounts['deposit']
    >>> line.description = 'Deposit'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(100)
    >>> invoice.click('post')
    >>> invoice.untaxed_amount
    Decimal('100.00')

Check party deposit::

    >>> party.reload()
    >>> party.deposit
    Decimal('100.00')

Create final invoice::

    >>> invoice = Invoice(party=party, payment_term=payment_term)
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.description = 'Revenue'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(500)
    >>> invoice.save()
    >>> invoice.untaxed_amount
    Decimal('500.00')

Recall deposit::

    >>> recall_deposit = Wizard('account.invoice.recall_deposit', [invoice])
    >>> recall_deposit.form.account = accounts['deposit']
    >>> recall_deposit.form.description = 'Recall Deposit'
    >>> recall_deposit.execute('recall')
    >>> invoice.reload()
    >>> deposit_line, = [l for l in invoice.lines
    ...     if l.account == accounts['deposit']]
    >>> deposit_line.amount
    Decimal('-100.00')
    >>> invoice.untaxed_amount
    Decimal('400.00')

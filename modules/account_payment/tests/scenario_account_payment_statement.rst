=======================================
Account Payment with Statement Scenario
=======================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(['account_payment', 'account_statement'])

    >>> AccountJournal = Model.get('account.journal')
    >>> Party = Model.get('party.party')
    >>> Payment = Model.get('account.payment')
    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')

Create company::

    >>> _ = create_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart()
    >>> accounts = get_accounts()

Create journals::

    >>> payment_journal = PaymentJournal(
    ...     name="Check", process_method='manual')
    >>> payment_journal.save()

    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)

    >>> statement_journal = StatementJournal(
    ...     name="Statement",
    ...     journal=account_journal,
    ...     validation='amount',
    ...     account=accounts['cash'])
    >>> statement_journal.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Receive payment::

    >>> payment = Payment(kind='receivable')
    >>> payment.journal = payment_journal
    >>> payment.party = customer
    >>> payment.amount = Decimal('100.00')
    >>> payment.click('submit')
    >>> process_payment = payment.click('process_wizard')
    >>> payment.state
    'processing'

Validate statement related to payment::

    >>> statement = Statement(
    ...     name='001',
    ...     journal=statement_journal,
    ...     total_amount=Decimal('90.00'))
    >>> line = statement.lines.new()
    >>> line.date = today
    >>> line.amount = Decimal('90.00')
    >>> line.account = accounts['receivable']
    >>> line.related_to = payment
    >>> statement.click('validate_statement')
    >>> statement.state
    'validated'

Check payment is succeeded::

    >>> payment.reload()
    >>> payment.state
    'succeeded'

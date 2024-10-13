============================================
Account Payment with Statement Rule Scenario
============================================

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

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['account_payment', 'account_statement', 'account_statement_rule'],
    ...     create_company, create_chart)

    >>> AccountJournal = Model.get('account.journal')
    >>> Party = Model.get('party.party')
    >>> Payment = Model.get('account.payment')
    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')
    >>> StatementRule = Model.get('account.statement.rule')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

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

Create statement rules for payment::

    >>> statement_rule = StatementRule(name="Rule Payment")
    >>> statement_rule.description = r"Payment: *(?P<payment>.*)"
    >>> statement_line = statement_rule.lines.new()
    >>> statement_line.amount = "pending"
    >>> statement_rule.save()

Receive a payments::

    >>> payment = Payment(kind='receivable')
    >>> payment.journal = payment_journal
    >>> payment.party = customer
    >>> payment.amount = Decimal('100.00')
    >>> payment.click('submit')
    >>> process_payment = payment.click('process_wizard')
    >>> payment.state
    'processing'

Create a statement with payment and group as origins::

    >>> statement = Statement(
    ...     name="001",
    ...     journal=statement_journal,
    ...     total_amount=Decimal('100.00'))
    >>> origin = statement.origins.new()
    >>> origin.date = today
    >>> origin.amount = Decimal('100.00')
    >>> origin.description = "Payment: %s" % payment.rec_name
    >>> statement.click('apply_rules')
    >>> line, = statement.lines
    >>> assertEqual(line.related_to, payment)

Check payments are succeeded after validation::

    >>> statement.click('validate_statement')
    >>> statement.state
    'validated'
    >>> payment.reload()
    >>> payment.state
    'succeeded'

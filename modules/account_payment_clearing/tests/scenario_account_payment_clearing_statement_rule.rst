=====================================================
Account Payment Clearing with Statement Rule Scenario
=====================================================

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
    ...     ['account_payment_clearing',
    ...         'account_statement', 'account_statement_rule'],
    ...     create_company, create_chart)

    >>> Account = Model.get('account.account')
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

    >>> bank_clearing = Account(parent=accounts['payable'].parent)
    >>> bank_clearing.name = "Bank Clearing"
    >>> bank_clearing.type = accounts['payable'].type
    >>> bank_clearing.reconcile = True
    >>> bank_clearing.deferral = True
    >>> bank_clearing.save()

Create journals::

    >>> expense_journal, = AccountJournal.find([('code', '=', 'EXP')])

    >>> payment_journal = PaymentJournal(
    ...     name="Manual",
    ...     process_method='manual',
    ...     clearing_journal=expense_journal,
    ...     clearing_account=bank_clearing)
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

Create statement rules for payment and group::

    >>> statement_rule = StatementRule(name="Rule Payment")
    >>> statement_rule.description = r"Payment: *(?P<payment>.*)"
    >>> statement_line = statement_rule.lines.new()
    >>> statement_line.amount = "pending"
    >>> statement_rule.save()

    >>> statement_rule = StatementRule(name="Rule Payment Group")
    >>> statement_rule.description = r"Payment Group: *(?P<payment_group>.*)"
    >>> statement_line = statement_rule.lines.new()
    >>> statement_line.amount = "pending"
    >>> statement_rule.save()

Receive 2 payments::

    >>> payment1 = Payment(kind='receivable')
    >>> payment1.journal = payment_journal
    >>> payment1.party = customer
    >>> payment1.amount = Decimal('100.00')
    >>> payment1.click('submit')
    >>> process1_payment = payment1.click('process_wizard')
    >>> payment1.state
    'processing'

    >>> payment2 = Payment(kind='receivable')
    >>> payment2.journal = payment_journal
    >>> payment2.party = customer
    >>> payment2.amount = Decimal('200.00')
    >>> payment2.click('submit')
    >>> process2_payment = payment2.click('process_wizard')
    >>> payment2.state
    'processing'

Create a statement with payment and group as origins::

    >>> statement = Statement(
    ...     name="001",
    ...     journal=statement_journal,
    ...     total_amount=Decimal('300.00'))
    >>> origin = statement.origins.new()
    >>> origin.date = today
    >>> origin.amount = Decimal('100.00')
    >>> origin.description = "Payment: %s" % payment1.rec_name
    >>> origin = statement.origins.new()
    >>> origin.date = today
    >>> origin.amount = Decimal('200.00')
    >>> origin.description = "Payment Group: %s" % payment2.group.rec_name
    >>> statement.click('apply_rules')
    >>> line1, line2 = statement.lines
    >>> assertEqual(line1.account, bank_clearing)
    >>> assertEqual(line1.related_to, payment1)
    >>> assertEqual(line1.account, bank_clearing)
    >>> assertEqual(line2.related_to, payment2.group)

Check payments are succeeded after validation::

    >>> statement.click('validate_statement')
    >>> statement.state
    'validated'
    >>> payment1.reload()
    >>> payment1.state
    'succeeded'
    >>> payment2.reload()
    >>> payment2.state
    'succeeded'

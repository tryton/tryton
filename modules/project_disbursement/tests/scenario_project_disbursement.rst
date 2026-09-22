=============================
Project Disbursement Scenario
=============================

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

    >>> config = activate_modules('project_disbursement', create_company, create_chart)

    >>> Account = Model.get('account.account')
    >>> AccountJournal = Model.get('account.journal')
    >>> Disbursement = Model.get('project.disbursement')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')
    >>> Work = Model.get('project.work')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> account_disbursement, = Account.find([('code', '=', '1.2.3')])
    >>> account_disbursement_type = account_disbursement.type
    >>> account_disbursement_type.template_override = True
    >>> account_disbursement_type.disbursement = True
    >>> account_disbursement_type.save()

Create payment journal::

    >>> payment_journal = PaymentJournal(name='Manual', process_method='manual')
    >>> payment_journal.save()

Create statement journal::

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
    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create a project with a task::

    >>> project = Work(type='project')
    >>> project.name = "Project"
    >>> project.party = customer
    >>> project.project_invoice_method = 'effort'
    >>> project.account_disbursement = account_disbursement
    >>> disbursement_journal = project.disbursement_journals.new()
    >>> disbursement_journal.currency = project.company.currency
    >>> disbursement_journal.journal = payment_journal
    >>> task = project.children.new()
    >>> task.name = "Task"
    >>> project.save()
    >>> task, = project.children

Add and validate a disbursement to the task::

    >>> disbursement = Disbursement()
    >>> disbursement.work = task
    >>> disbursement.payee = supplier
    >>> disbursement.amount = Decimal('100.00')
    >>> disbursement.payment_date = today
    >>> disbursement.click('validate_disbursement')
    >>> disbursement.state
    'validated'

Pay partially the disbursement::

    >>> payment, = disbursement.payments
    >>> payment.amount
    Decimal('100.00')
    >>> payment.amount = Decimal('50.00')
    >>> payment.click('submit')
    >>> payment.state
    'submitted'
    >>> payment.click('approve')
    >>> payment.state
    'approved'
    >>> process_payment = payment.click('process_wizard')
    >>> payment.state
    'processing'
    >>> payment.click('succeed')
    >>> payment.state
    'succeeded'

    >>> disbursement.reload()
    >>> len(disbursement.payments)
    2

Fail the remaining disbursement::

    >>> payment, = [p for p in disbursement.payments if p.state == 'draft']
    >>> payment.click('submit')
    >>> payment.click('approve')
    >>> process_payment = payment.click('process_wizard')
    >>> payment.click('fail')
    >>> payment.state
    'failed'

    >>> disbursement.reload()
    >>> len(disbursement.payments)
    3

Pay totally the disbursement::

    >>> payment, = [p for p in disbursement.payments if p.state == 'draft']
    >>> payment.click('submit')
    >>> payment.click('approve')
    >>> process_payment = payment.click('process_wizard')
    >>> payment.click('succeed')
    >>> payment.state
    'succeeded'

    >>> disbursement.reload()
    >>> len(disbursement.payments)
    3

Create and validate a statement for the payments::

    >>> payments = [p for p in disbursement.payments if p.state == 'succeeded']

    >>> statement = Statement(
    ...     name="001",
    ...     journal=statement_journal,
    ...     total_amount=Decimal('-100.00'))
    >>> line = statement.lines.new()
    >>> line.date = today
    >>> line.amount = Decimal('-50.00')
    >>> line.related_to = payments[0]
    >>> assertEqual(line.party, supplier)
    >>> assertEqual(line.account, account_disbursement)
    >>> line = statement.lines.new()
    >>> line.date = today
    >>> line.amount = Decimal('-50.00')
    >>> line.related_to = payments[1]
    >>> statement.click('validate_statement')
    >>> statement.state
    'validated'

    >>> account_disbursement.reload()
    >>> account_disbursement.balance
    Decimal('100.00')

Check disbursement is paid::

    >>> disbursement.reload()
    >>> disbursement.state
    'paid'

    >>> project.reload()
    >>> project.amount_to_invoice
    Decimal('100.00')

Invoice the project::

    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')

    >>> invoice, = Invoice.find([])
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

    >>> account_disbursement.reload()
    >>> account_disbursement.balance
    Decimal('0.00')

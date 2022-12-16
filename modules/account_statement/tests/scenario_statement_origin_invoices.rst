==========================================
Account Statement Origin Invoices Scenario
==========================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('account_statement')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> cash = accounts['cash']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create 2 customer invoices::

    >>> Invoice = Model.get('account.invoice')
    >>> customer_invoice1 = Invoice(type='out')
    >>> customer_invoice1.party = customer
    >>> invoice_line = customer_invoice1.lines.new()
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('100')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test'
    >>> customer_invoice1.click('post')
    >>> customer_invoice1.state
    'posted'

    >>> customer_invoice2 = Invoice(type='out')
    >>> customer_invoice2.party = customer
    >>> invoice_line = customer_invoice2.lines.new()
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('150')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test'
    >>> customer_invoice2.click('post')
    >>> customer_invoice2.state
    'posted'

Create Account Journal::

    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> AccountJournal = Model.get('account.journal')

    >>> sequence_type, = SequenceType.find([('name', '=', "Account Journal")])
    >>> sequence = Sequence(name="Satement",
    ...     sequence_type=sequence_type,
    ...     company=company,
    ...     )
    >>> sequence.save()
    >>> account_journal = AccountJournal(name="Statement",
    ...     type='statement',
    ...     sequence=sequence,
    ...     )
    >>> account_journal.save()

Create a statement with origins::

    >>> StatementJournal = Model.get('account.statement.journal')
    >>> Statement = Model.get('account.statement')
    >>> journal_number = StatementJournal(name="Number",
    ...     journal=account_journal,
    ...     account=cash,
    ...     validation='number_of_lines',
    ...     )
    >>> journal_number.save()

    >>> statement = Statement(name="number origins")
    >>> statement.journal = journal_number
    >>> statement.number_of_lines = 1
    >>> origin = statement.origins.new()
    >>> origin.date = today
    >>> origin.amount = Decimal('180.00')
    >>> statement.click('validate_statement')

Pending amount is used to fill all invoices::

    >>> origin, = statement.origins
    >>> line = origin.lines.new()
    >>> line.invoice = customer_invoice1
    >>> line.amount
    Decimal('100.00')
    >>> line.party == customer
    True
    >>> line.account == receivable
    True
    >>> origin.pending_amount
    Decimal('80.00')
    >>> line = origin.lines.new()
    >>> line.invoice = customer_invoice2
    >>> line.amount
    Decimal('80.00')
    >>> line.party == customer
    True
    >>> line.account == receivable
    True

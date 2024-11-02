================================
Account Export WinBooks Scenario
================================

Imports::

    >>> import datetime as dt
    >>> import io
    >>> import zipfile
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertMultiLineEqual
    >>> from trytond.tools import file_open

Activate modules::

    >>> config = activate_modules(
    ...     ['account_export_winbooks', 'account_statement'],
    ...     create_company, create_chart)
    >>> config.skip_warning = True

    >>> Invoice = Model.get('account.invoice')
    >>> Journal = Model.get('account.journal')
    >>> MoveExport = Model.get('account.move.export')
    >>> Party = Model.get('party.party')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')

Get accounts::

    >>> accounts = get_accounts()

    >>> accounts['payable'].winbooks_code = '440000'
    >>> accounts['payable'].save()
    >>> accounts['expense'].code = '600000'
    >>> accounts['expense'].save()
    >>> accounts['receivable'].winbooks_code = '400000'
    >>> accounts['receivable'].save()
    >>> accounts['revenue'].code = '700000'
    >>> accounts['revenue'].save()
    >>> accounts['cash'].code = '550000'
    >>> accounts['cash'].save()

Create taxes::

    >>> supplier_tax = create_tax(Decimal('.21'))
    >>> supplier_tax.winbooks_code = '112104'
    >>> supplier_tax.invoice_account, = accounts['tax'].duplicate(
    ...     default={'winbooks_code': '411'})
    >>> supplier_tax.credit_note_account = supplier_tax.invoice_account
    >>> supplier_tax.save()

    >>> customer_tax = create_tax(Decimal('.21'))
    >>> customer_tax.winbooks_code = '211400'
    >>> customer_tax.invoice_account, = accounts['tax'].duplicate(
    ...     default={'winbooks_code': '451'})
    >>> customer_tax.credit_note_account = customer_tax.invoice_account
    >>> customer_tax.save()

    >>> customer_tax_intra = create_tax(Decimal(0))
    >>> customer_tax_intra.winbooks_code = '221000'
    >>> customer_tax_intra.save()

Create statement journal::

    >>> statement_journal = StatementJournal(name="Bank")
    >>> statement_journal.journal, = Journal.find(
    ...     [('code', '=', 'STA')], limit=1)
    >>> statement_journal.account = accounts['cash']
    >>> statement_journal.validation = 'balance'
    >>> statement_journal.save()
    >>> statement_journal.journal.winbooks_code = 'STAT'
    >>> statement_journal.journal.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.start_date = dt.date(2023, 1, 1)
    >>> fiscalyear.end_date = dt.date(2023, 12, 31)
    >>> fiscalyear.winbooks_code = '3'
    >>> fiscalyear.click('create_period')

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> identifier = supplier.identifiers.new(type='winbooks_supplier')
    >>> identifier.code = 'SUPP'
    >>> supplier.save()
    >>> supplier.winbooks_supplier_identifier.code
    'SUPP'
    >>> supplier.winbooks_customer_identifier
    >>> customer = Party(name="Customer")
    >>> identifier = customer.identifiers.new(type='winbooks_customer')
    >>> identifier.code = 'CUST'
    >>> customer.save()
    >>> customer.winbooks_supplier_identifier
    >>> customer.winbooks_customer_identifier.code
    'CUST'

Create supplier invoice::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = supplier
    >>> invoice.invoice_date = dt.date(2023, 1, 20)
    >>> invoice.payment_term_date = dt.date(2023, 2, 28)
    >>> line = invoice.lines.new()
    >>> line.account = accounts['expense']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('500.00')
    >>> line.taxes.append(supplier_tax)
    >>> invoice.save()
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.total_amount
    Decimal('605.00')

    >>> invoice.journal.winbooks_code = 'EXP'
    >>> invoice.journal.save()

Create customer invoice::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = customer
    >>> invoice.description = "Services"
    >>> invoice.invoice_date = dt.date(2023, 2, 20)
    >>> invoice.payment_term_date = dt.date(2023, 3, 31)
    >>> line = invoice.lines.new()
    >>> line.description = "Product"
    >>> line.account = accounts['revenue']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('1000.00')
    >>> line.taxes.append(customer_tax)
    >>> invoice.save()
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.total_amount
    Decimal('1210.00')

    >>> invoice.journal.winbooks_code = 'REV'
    >>> invoice.journal.save()

Create customer intra-community invoice::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = customer
    >>> invoice.invoice_date = dt.date(2023, 3, 1)
    >>> invoice.payment_term_date = dt.date(2023, 3, 1)
    >>> line = invoice.lines.new()
    >>> line.description = "Service"
    >>> line.account = accounts['revenue']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('50.00')
    >>> line.taxes.append(customer_tax_intra)
    >>> invoice.save()
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.total_amount
    Decimal('50.00')

Fill a statement::

    >>> statement = Statement(name="Bank")
    >>> statement.journal = statement_journal
    >>> statement.start_balance = Decimal('0.00')
    >>> statement.end_balance = Decimal('100.00')
    >>> line = statement.lines.new()
    >>> line.number = '1'
    >>> line.date = dt.date(2023, 3, 31)
    >>> line.amount = Decimal('100.00')
    >>> line.party = customer
    >>> statement.click('validate_statement')
    >>> statement.click('post')
    >>> statement.state
    'posted'

Export moves to WinBooks::

    >>> move_export = MoveExport(type='winbooks')
    >>> move_export.click('select_moves')
    >>> len(move_export.moves)
    4
    >>> move_export.click('wait')
    >>> move_export.state
    'waiting'
    >>> with zipfile.ZipFile(io.BytesIO(move_export.file)) as file:
    ...     with file.open('ACT.txt') as act1, \
    ...             file_open('account_export_winbooks/tests/ACT.txt') as act2:
    ...         assertMultiLineEqual(io.TextIOWrapper(act1).read(), act2.read())

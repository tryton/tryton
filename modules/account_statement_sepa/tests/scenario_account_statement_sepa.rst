===============================
Account Statement Sepa Scenario
===============================

Imports::

    >>> from functools import partial

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

Activate modules::

    >>> config = activate_modules(
    ...     'account_statement_sepa',
    ...     partial(create_company, currency='EUR'), create_chart)

    >>> AccountJournal = Model.get('account.journal')
    >>> Bank = Model.get('bank')
    >>> BankAccount = Model.get('bank.account')
    >>> Party = Model.get('party.party')
    >>> StatementJournal = Model.get('account.statement.journal')

Get company::

    >>> company = get_company()

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()
    >>> bank_party = Party(name="Bank")
    >>> bank_party.save()

Create Bank Accounts::

    >>> bank = Bank()
    >>> bank.party = bank_party
    >>> bank.save()
    >>> bank_account = BankAccount()
    >>> bank_account.bank = bank
    >>> bank_account.owners.append(Party(company.party.id))
    >>> bank_account.currency = company.currency
    >>> bank_account_number = bank_account.numbers.new()
    >>> bank_account_number.type = 'iban'
    >>> bank_account_number.number = 'BE55442968847144'
    >>> bank_account.save()

    >>> supplier_bank_account = BankAccount()
    >>> supplier_bank_account.owners.append(Party(supplier.id))
    >>> supplier_bank_account.currency = company.currency
    >>> supplier_bank_account_number = supplier_bank_account.numbers.new()
    >>> supplier_bank_account_number.type = 'iban'
    >>> supplier_bank_account_number.number = 'DE79370400440123619900'
    >>> supplier_bank_account.save()

Create Statement Journal::

    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)
    >>> journal = StatementJournal(name="Bank",
    ...     journal=account_journal,
    ...     account=accounts['cash'],
    ...     bank_account=bank_account,
    ...     )
    >>> journal.save()

Import CAMT.053 file::

    >>> statement_import = Wizard('account.statement.import')
    >>> with file_open(
    ...         'account_statement_sepa/tests/camt.053.001.02.xml', mode='rb') as fp:
    ...     camt = fp.read()
    >>> statement_import.form.file_ = camt
    >>> statement_import.form.file_format = 'camt_053_001'
    >>> statement_import.execute('import_')

Check Statement::

    >>> statement, = statement_import.actions[0]
    >>> statement.name
    'Example_2009-05-12T00:00:00'
    >>> statement.date
    datetime.date(2009, 5, 12)
    >>> statement.start_balance
    Decimal('2000.00')
    >>> statement.end_balance
    Decimal('1900.00')
    >>> statement.total_amount
    Decimal('-100.00')
    >>> statement.number_of_lines
    1
    >>> len(statement.origins)
    1
    >>> origin, = statement.origins
    >>> origin.number
    >>> origin.date
    datetime.date(2009, 4, 29)
    >>> origin.amount
    Decimal('-100.00')
    >>> assertEqual(origin.party, supplier)
    >>> origin.description
    >>> origin.information['camt_creditor_name']
    'Supplier'
    >>> origin.information['camt_creditor_iban']
    'DE79370400440123619900'
    >>> origin.information['camt_remittance_information']
    'INV 2150135'

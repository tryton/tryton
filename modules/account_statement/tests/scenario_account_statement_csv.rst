==============================
Account Statement CSV Scenario
==============================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

Activate modules::

    >>> config = activate_modules(
    ...     'account_statement',
    ...     create_company, create_chart)

    >>> AccountJournal = Model.get('account.journal')
    >>> Bank = Model.get('bank')
    >>> BankAccount = Model.get('bank.account')
    >>> CSV = Model.get('account.statement.import.csv')
    >>> Party = Model.get('party.party')
    >>> StatementJournal = Model.get('account.statement.journal')

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()
    >>> bank_party = Party(name="Bank")
    >>> bank_party.save()

Create bank account::

    >>> bank = Bank()
    >>> bank.party = bank_party
    >>> bank.save()
    >>> bank_account = BankAccount()
    >>> bank_account.bank = bank
    >>> bank_account.owners.append(customer)
    >>> bank_account_number = bank_account.numbers.new()
    >>> bank_account_number.type = 'iban'
    >>> bank_account_number.number = 'BE47435000000080'
    >>> bank_account.save()

Setup statement journal::

    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)
    >>> journal = StatementJournal(
    ...     name="Bank",
    ...     journal=account_journal,
    ...     account=accounts['cash'],
    ...     validation='amount')
    >>> journal.save()

Setup CSV import::

    >>> csv = CSV(name="CSV Bank")
    >>> csv.lines_to_skip = 1
    >>> csv.date_format = '%d/%m/%Y'
    >>> csv.decimal_point = ','
    >>> csv.thousands_sep = '.'
    >>> csv.number_column = 0
    >>> csv.date_column = 1
    >>> csv.amount_column = 2
    >>> csv.account_column = 3
    >>> csv.party_column = 4
    >>> csv.description_column = 5
    >>> csv.save()

Import CSV file::

    >>> statement_import = Wizard('account.statement.import')
    >>> with file_open('account_statement/tests/statement.csv', mode='rb') as fp:
    ...     statement_import.form.file_ = fp.read()
    >>> statement_import.form.file_name = '001.csv'
    >>> statement_import.form.file_format = 'csv'
    >>> statement_import.form.csv_format = csv
    >>> statement_import.form.csv_journal = journal
    >>> statement_import.execute('import_')

Check statement::

    >>> (statement,), = statement_import.actions
    >>> statement.name
    '001'
    >>> statement.total_amount
    Decimal('980.50')
    >>> statement.number_of_lines
    2
    >>> len(statement.origins)
    2

    >>> origin = statement.origins[0]
    >>> origin.number
    '0001'
    >>> origin.date
    datetime.date(2026, 1, 1)
    >>> origin.amount
    Decimal('1000.50')
    >>> assertEqual(origin.party, customer)
    >>> origin.description
    'description'
    >>> origin.information['csv_row']
    '0001,01/01/2026,1.000\\,50,BE47435000000080,unknown,description'

    >>> origin = statement.origins[1]
    >>> origin.number
    '0002'
    >>> origin.date
    datetime.date(2026, 1, 1)
    >>> origin.amount
    Decimal('-20')
    >>> assertEqual(origin.party, customer)
    >>> origin.description
    ''
    >>> origin.information['csv_row']
    '0002,01/01/2026,-20,,Customer,'

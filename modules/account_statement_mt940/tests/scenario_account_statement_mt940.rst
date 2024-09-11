================================
Account Statement MT940 Scenario
================================

Imports::

    >>> from functools import partial

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

Activate modules::

    >>> config = activate_modules(
    ...     'account_statement_mt940',
    ...     partial(create_company, currency='EUR'), create_chart)

    >>> AccountJournal = Model.get('account.journal')
    >>> Bank = Model.get('bank')
    >>> BankAccount = Model.get('bank.account')
    >>> Party = Model.get('party.party')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')

Get company::

    >>> company = get_company()

Get accounts::

    >>> accounts = get_accounts(company)

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()
    >>> bank_party = Party(name="Bank")
    >>> bank_party.save()

Create Bank Accounts::

    >>> bank = Bank()
    >>> bank.party = bank_party
    >>> bank.save()

    >>> bank_account = BankAccount()
    >>> bank_account.bank = bank
    >>> bank_account.owners.append(Party(customer.id))
    >>> bank_account.currency = company.currency
    >>> bank_account_number = bank_account.numbers.new()
    >>> bank_account_number.type = 'other'
    >>> bank_account_number.number = '987654321'
    >>> bank_account.save()

    >>> bank_account = BankAccount()
    >>> bank_account.bank = bank
    >>> bank_account.owners.append(Party(company.party.id))
    >>> bank_account.currency = company.currency
    >>> bank_account_number = bank_account.numbers.new()
    >>> bank_account_number.type = 'other'
    >>> bank_account_number.number = '1234567890'
    >>> bank_account.save()

Create Statement Journal::

    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)
    >>> journal = StatementJournal(
    ...     name="Bank",
    ...     journal=account_journal,
    ...     account=accounts['cash'],
    ...     bank_account=bank_account,
    ...     )
    >>> journal.save()

Import MT940 file::

    >>> statement_import = Wizard('account.statement.import')
    >>> with file_open('account_statement_mt940/tests/MT940.txt', mode='rb') as fp:
    ...     mt940 = fp.read()
    >>> statement_import.form.file_ = mt940
    >>> statement_import.form.file_format = 'mt940'
    >>> statement_import.form.mt940_bank = 'abn_amro'
    >>> statement_import.execute('import_')

Check Statement::

    >>> statement, = Statement.find([])
    >>> statement.name
    '001'
    >>> statement.date
    datetime.date(2019, 7, 31)
    >>> statement.start_balance
    Decimal('0.00')
    >>> statement.end_balance
    Decimal('100.00')
    >>> statement.total_amount
    Decimal('100.00')
    >>> statement.number_of_lines
    1
    >>> len(statement.origins)
    1
    >>> origin, = statement.origins
    >>> origin.number
    'FFPC'
    >>> origin.date
    datetime.date(2019, 7, 31)
    >>> origin.amount
    Decimal('100.00')
    >>> assertEqual(origin.party, customer)
    >>> origin.description
    '98.76.54.321 John Doe'
    >>> origin.information['mt940_reference']
    '913000381'

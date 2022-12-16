===============================
Account Statement Coda Scenario
===============================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.tools import file_open
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts

Activate modules::

    >>> config = activate_modules('account_statement_coda')

Create company::

    >>> _ = create_company(currency=get_currency('EUR'))
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> cash = accounts['cash']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
    >>> customer.save()
    >>> bank_party = Party(name="Bank")
    >>> bank_party.save()

Create Bank Account::

    >>> Bank = Model.get('bank')
    >>> BankAccount = Model.get('bank.account')

    >>> bank = Bank()
    >>> bank.party = bank_party
    >>> bank.save()
    >>> bank_account = BankAccount()
    >>> bank_account.bank = bank
    >>> bank_account.owners.append(Party(company.party.id))
    >>> bank_account.currency = company.currency
    >>> bank_account_number = bank_account.numbers.new()
    >>> bank_account_number.type = 'iban'
    >>> bank_account_number.number = 'BE47435000000080'
    >>> bank_account.save()

Create Account Journal::

    >>> Sequence = Model.get('ir.sequence')
    >>> AccountJournal = Model.get('account.journal')

    >>> sequence = Sequence(name="Satement",
    ...     code='account.journal',
    ...     company=company,
    ...     )
    >>> sequence.save()
    >>> account_journal = AccountJournal(name="Statement",
    ...     type='statement',
    ...     sequence=sequence,
    ... )
    >>> account_journal.save()

Create Statement Journal::

    >>> StatementJournal = Model.get('account.statement.journal')

    >>> journal = StatementJournal(name="Bank",
    ...     journal=account_journal,
    ...     account=cash,
    ...     bank_account=bank_account,
    ...     )
    >>> journal.save()

Import CODA file::

    >>> statement_import = Wizard('account.statement.import')
    >>> with file_open('account_statement_coda/tests/CODA.txt', mode='rb') as fp:
    ...     coda = fp.read()
    >>> statement_import.form.file_ = coda
    >>> statement_import.form.file_format = 'coda'
    >>> statement_import.execute('import_')

Check Statement::

    >>> Statement = Model.get('account.statement')
    >>> statement, = Statement.find([])
    >>> statement.name
    '001'
    >>> statement.date
    datetime.date(2017, 8, 1)
    >>> statement.start_balance
    Decimal('0')
    >>> statement.end_balance
    Decimal('100')
    >>> statement.total_amount
    Decimal('100')
    >>> statement.number_of_lines
    1
    >>> len(statement.origins)
    1
    >>> origin, = statement.origins
    >>> origin.number
    '0001'
    >>> origin.date
    datetime.date(2017, 7, 19)
    >>> origin.amount
    Decimal('100')
    >>> origin.description
    'COMMUNICATION'
    >>> origin.information['coda_bank_reference']
    'REF BANK             '

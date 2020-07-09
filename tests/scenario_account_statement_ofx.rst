==============================
Account Statement OFX Scenario
==============================

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

    >>> config = activate_modules('account_statement_ofx')

Create company::

    >>> _ = create_company(currency=get_currency('EUR'))
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> cash = accounts['cash']

Create parties::

    >>> Party = Model.get('party.party')
    >>> michael_scott_paper = Party(name="Michael Scott Paper Company")
    >>> michael_scott_paper.save()
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
    >>> bank_account_number.type = 'other'
    >>> bank_account_number.number = '01234567890'
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
    ...     validation='amount',
    ...     )
    >>> journal.save()

Import OFX file::

    >>> statement_import = Wizard('account.statement.import')
    >>> with file_open('account_statement_ofx/tests/OFX.txt', mode='rb') as fp:
    ...     ofx = fp.read()
    >>> statement_import.form.file_ = ofx
    >>> statement_import.form.file_format = 'ofx'
    >>> statement_import.execute('import_')

Check Statement::

    >>> Statement = Model.get('account.statement')
    >>> statement, = Statement.find([])
    >>> statement.name
    '01234567890'
    >>> statement.date
    datetime.date(2018, 2, 22)
    >>> statement.total_amount
    Decimal('100.00')
    >>> statement.number_of_lines
    1
    >>> statement.start_balance
    Decimal('400.00')
    >>> statement.end_balance
    Decimal('500.00')
    >>> len(statement.origins)
    1
    >>> origin, = statement.origins
    >>> origin.number
    '0001'
    >>> origin.date
    datetime.date(2018, 2, 21)
    >>> origin.amount
    Decimal('100.00')
    >>> origin.party == michael_scott_paper
    True
    >>> origin.description
    'COMMUNICATION'
    >>> origin.information['ofx_type']
    'credit'

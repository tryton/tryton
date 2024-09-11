=======================================
Account Statement Bank Account Scenario
=======================================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('account_statement', create_company, create_chart)

    >>> AccountJournal = Model.get('account.journal')
    >>> Bank = Model.get('bank')
    >>> BankAccount = Model.get('bank.account')
    >>> Party = Model.get('party.party')
    >>> StatementJournal = Model.get('account.statement.journal')

Get currencies and company::

    >>> eur = get_currency('EUR')
    >>> usd = get_currency('USD')

    >>> company = get_company()

Get accounts::

    >>> accounts = get_accounts()

Create bank account::

    >>> bank_party = Party(name="Bank")
    >>> bank_party.save()
    >>> bank = Bank(party=bank_party)
    >>> bank.save()
    >>> bank_account = BankAccount(bank=bank)
    >>> bank_account.owners.append(Party(company.party.id))
    >>> bank_account.currency = eur
    >>> number = bank_account.numbers.new(type='iban')
    >>> number.number = 'BE82068896274468'
    >>> bank_account.save()

Create statement journal::

    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)
    >>> statement_journal = StatementJournal(
    ...     name="Test",
    ...     account=accounts['cash'],
    ...     journal=account_journal,
    ...     currency=eur,
    ...     bank_account=bank_account)
    >>> statement_journal.save()

Change currency of bank account::

    >>> bank_account.currency = usd
    >>> bank_account.save()
    Traceback (most recent call last):
        ...
    AccountValidationError: ...

Get journal by bank account::

    >>> assertEqual(
    ...     StatementJournal.get_by_bank_account(
    ...         company.id, 'BE82068896274468', context={}),
    ...     statement_journal.id)
    >>> assertEqual(
    ...     StatementJournal.get_by_bank_account(
    ...         company.id, 'BE82068896274468', 'EUR', context={}),
    ...     statement_journal.id)
    >>> StatementJournal.get_by_bank_account(company.id, 'foo', context={})
    >>> StatementJournal.get_by_bank_account(
    ...     company.id, 'BE82068896274468', 'USD', context={})

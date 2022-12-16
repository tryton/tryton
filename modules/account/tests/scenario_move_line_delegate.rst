=======================
Delegate Lines Scenario
=======================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules('account')

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')

Create company::

    >>> usd = get_currency('USD')
    >>> eur = get_currency('EUR')
    >>> _ = create_company(currency=usd)
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create parties::

    >>> party1 = Party(name="Party 1")
    >>> party1.save()
    >>> party2 = Party(name="Party 2")
    >>> party2.save()

Create lines to delegate::

    >>> journal, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])

    >>> move = Move(journal=journal)
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal('100.00')
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.party = party1
    >>> line.debit = Decimal('80.00')
    >>> line.second_currency = eur
    >>> line.amount_second_currency = Decimal('100.00')
    >>> line.maturity_date = period.end_date
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.party = party1
    >>> line.debit = Decimal('20.00')
    >>> move.save()

    >>> receivable_lines = [
    ...     l for l in move.lines if l.account == accounts['receivable']]
    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('100.00')
    >>> party1.reload()
    >>> party1.receivable
    Decimal('100.00')
    >>> party2.reload()
    >>> party2.receivable
    Decimal('0.0')

Delegate lines::

    >>> delegate = Wizard('account.move.line.delegate', receivable_lines)
    >>> delegate.form.journal == journal
    True
    >>> delegate.form.party = party2
    >>> delegate.form.description = "Delegate lines"
    >>> delegate.execute('delegate')

    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('100.00')
    >>> party1.reload()
    >>> party1.receivable
    Decimal('0.0')
    >>> party2.reload()
    >>> party2.receivable
    Decimal('100.00')

    >>> all(l.reconciliation.delegate_to for l in receivable_lines)
    True

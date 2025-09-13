=======================
Delegate Lines Scenario
=======================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')

Get currencies::

    >>> usd = get_currency('USD')
    >>> eur = get_currency('EUR')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()

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
    Decimal('0')

Delegate lines::

    >>> delegate = Wizard('account.move.line.delegate', receivable_lines)
    >>> assertEqual(delegate.form.journal, journal)
    >>> delegate.form.party = party2
    >>> delegate.form.description = "Delegate lines"
    >>> delegate.execute('delegate')

    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('100.00')
    >>> party1.reload()
    >>> party1.receivable
    Decimal('0')
    >>> party2.reload()
    >>> party2.receivable
    Decimal('100.00')

    >>> all(l.reconciliation.delegate_to for l in receivable_lines)
    True

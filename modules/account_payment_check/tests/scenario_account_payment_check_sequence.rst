=======================================
Account Payment Check Sequence Scenario
=======================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     'account_payment_check', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')

Create a fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')

Get accounts and journals::

    >>> accounts = get_accounts()
    >>> expense_journal, = Journal.find([('code', '=', 'EXP')])

Create a payment journal for checks::

    >>> sequence_type, = SequenceType.find([('name', '=', "Account Payment Check")])
    >>> sequence = SequenceStrict(name="Checks", sequence_type=sequence_type)
    >>> sequence.padding = 6
    >>> sequence.save()

    >>> payment_journal = PaymentJournal(
    ...     name="Checks", process_method='check', check_sequence=sequence)
    >>> payment_journal.save()

Create a party::

    >>> party = Party(name="Party")
    >>> party.save()

Create a payable move::

    >>> move = Move()
    >>> move.journal = expense_journal
    >>> line = move.lines.new()
    >>> line.account = accounts['payable']
    >>> line.maturity_date = today
    >>> line.credit = Decimal('42.00')
    >>> line.party = party
    >>> line = move.lines.new()
    >>> line.account = accounts['expense']
    >>> line.debit = Decimal('42.00')
    >>> move.click('post')
    >>> move.state
    'posted'

Pay the line::

    >>> line, = [l for l in move.lines if l.account == accounts['payable']]
    >>> pay_line = line.click('pay')
    >>> pay_line.execute('next_')
    >>> pay_line.form.journal = payment_journal
    >>> pay_line.execute('next_')
    >>> payment, = pay_line.actions[0]
    >>> payment.click('submit')
    >>> payment.click('approve')
    >>> process_payment = payment.click('process_wizard')
    >>> group, = process_payment.actions[0]

Print the check::

    >>> bool(group.check_printed)
    False
    >>> check_print = group.click('check_print')

    >>> bool(group.check_printed)
    True
    >>> payment.reload()
    >>> payment.check_number
    '000001'

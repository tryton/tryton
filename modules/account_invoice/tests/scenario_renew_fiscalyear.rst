=========================
Renew Fiscalyear Scenario
=========================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_invoice', create_company)

Create fiscal year::

    >>> InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
    >>> fiscalyear = create_fiscalyear(today=today)
    >>> fiscalyear = set_fiscalyear_invoice_sequences(fiscalyear)
    >>> fiscalyear.click('create_period')
    >>> inv_seq, = fiscalyear.invoice_sequences
    >>> seq = inv_seq.out_invoice_sequence
    >>> for period in fiscalyear.periods:
    ...     seq, = seq.duplicate()
    ...     _ = inv_seq.duplicate(default={
    ...             'period': period.id,
    ...             'out_invoice_sequence': seq.id,
    ...             'in_invoice_sequence': seq.id,
    ...             'out_credit_note_sequence': seq.id,
    ...             'in_credit_note_sequence': seq.id,
    ...             })
    >>> period = fiscalyear.periods.new()
    >>> period.name = 'Adjustment'
    >>> period.start_date = fiscalyear.end_date
    >>> period.end_date = fiscalyear.end_date
    >>> period.type = 'adjustment'
    >>> fiscalyear.save()

Set the sequence number::

    >>> sequence = fiscalyear.post_move_sequence
    >>> sequence.number_next = 10
    >>> sequence.save()

    >>> for i, seq in enumerate(fiscalyear.invoice_sequences):
    ...     seq.out_invoice_sequence.number_next = i
    ...     seq.out_invoice_sequence.save()

Renew fiscal year using the wizard::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = False
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> len(new_fiscalyear.periods)
    12
    >>> int(new_fiscalyear.post_move_sequence.number_next)
    10
    >>> [int(seq.out_invoice_sequence.number_next)
    ...     for seq in fiscalyear.invoice_sequences]
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

Renew fiscal year resetting sequences::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = True
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> int(new_fiscalyear.post_move_sequence.number_next)
    1
    >>> [int(seq.out_invoice_sequence.number_next)
    ...     for seq in new_fiscalyear.invoice_sequences]
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]


Set the sequence name::

    >>> for seq in new_fiscalyear.invoice_sequences:
    ...     seq.out_invoice_sequence.name = ('Sequence %s' %
    ...         new_fiscalyear.name)
    ...     seq.out_invoice_sequence.save()

Renew fiscalyear and test sequence name is updated::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = True
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> for sequence in new_fiscalyear.invoice_sequences:
    ...     assertEqual(
    ...         sequence.out_invoice_sequence.name,
    ...         'Sequence %s' % new_fiscalyear.name)

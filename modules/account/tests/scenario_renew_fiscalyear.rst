=================================
Account Renew Fiscalyear Scenario
=================================

Imports::

    >>> from proteus import Wizard
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('account', create_company)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
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

Renew fiscalyear using the wizard::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = False
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> len(new_fiscalyear.periods)
    12
    >>> int(new_fiscalyear.post_move_sequence.number_next)
    10

Renew fiscalyear resetting sequences::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = True
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> int(new_fiscalyear.post_move_sequence.number_next)
    1

Set the sequence name::

    >>> sequence = new_fiscalyear.post_move_sequence
    >>> sequence.name = 'Sequence %s' % new_fiscalyear.name
    >>> sequence.save()

Renew fiscalyear and test sequence name is updated::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = True
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> assertEqual(new_fiscalyear.post_move_sequence.name,
    ...     'Sequence %s' % new_fiscalyear.name)

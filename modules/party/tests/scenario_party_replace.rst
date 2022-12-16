======================
Party Replace Scenario
======================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('party')

Create a party::

    >>> Party = Model.get('party.party')
    >>> party1 = Party(name='Pam')
    >>> party1.save()
    >>> address1, = party1.addresses

Create a second party similar party::

    >>> party2 = Party(name='Pam')
    >>> party2.save()
    >>> address2, = party2.addresses

Replace the second by the first party::

    >>> replace = Wizard('party.replace', models=[party2])
    >>> replace.form.source == party2
    True
    >>> replace.form.destination = party1
    >>> replace.execute('replace')

    >>> party2.reload()
    >>> bool(party2.active)
    False

    >>> address2.reload()
    >>> address2.party == party1
    True
    >>> bool(address2.active)
    False

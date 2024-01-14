======================
Party Replace Scenario
======================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertFalse

Activate modules::

    >>> config = activate_modules('party')

Create a party::

    >>> Party = Model.get('party.party')
    >>> party1 = Party(name='Pam')
    >>> identifier1 = party1.identifiers.new()
    >>> identifier1.type = 'eu_vat'
    >>> identifier1.code = 'BE0897290877'
    >>> party1.save()
    >>> address1, = party1.addresses
    >>> identifier1, = party1.identifiers

Create a second party similar party::

    >>> party2 = Party(name='Pam')
    >>> identifier2 = party2.identifiers.new()
    >>> identifier2.type = 'eu_vat'
    >>> identifier2.code = 'BE0897290877'
    >>> party2.save()
    >>> address2, = party2.addresses
    >>> identifier2, = party2.identifiers

Replace the second by the first party::

    >>> replace = Wizard('party.replace', models=[party2])
    >>> assertEqual(replace.form.source, party2)
    >>> replace.form.destination = party1
    >>> replace.execute('replace')

    >>> party2.reload()
    >>> bool(party2.active)
    False

    >>> identifier2.reload()
    >>> assertEqual(identifier2.party, party1)
    >>> assertFalse(identifier2.active)

    >>> address2.reload()
    >>> assertEqual(address2.party, party1)
    >>> assertFalse(address2.active)

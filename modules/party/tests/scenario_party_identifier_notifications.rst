==============================
Party Identifier Notifications
==============================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('party')

    >>> Party = Model.get('party.party')

Create first party::

    >>> party1 = Party(name="Party 1")
    >>> identifier = party1.identifiers.new(type='be_vat')
    >>> identifier.code = "500923836"
    >>> party1.save()

Create second party::

    >>> party2 = Party(name="Party 2")
    >>> identifier = party2.identifiers.new(type='be_vat')
    >>> identifier.code = "500923836"

Check notifications::

    >>> len(identifier.notifications())
    1

Change identifier::

    >>> identifier.type = None
    >>> identifier.code = "foo"

Check notifications::

    >>> len(identifier.notifications())
    0

=====================================
Party Contact Mechanism Notifications
=====================================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('party')

    >>> Party = Model.get('party.party')

Create first party::

    >>> party1 = Party(name="Party 1")
    >>> contact_mechanism = party1.contact_mechanisms.new(type='email')
    >>> contact_mechanism.value = "test@example.com"
    >>> party1.save()

Create second party::

    >>> party2 = Party(name="Party 2")
    >>> contact_mechanism = party2.contact_mechanisms.new(type='email')
    >>> contact_mechanism.value = "test@example.com"

Check notifications::

    >>> len(contact_mechanism.notifications())
    1

Change contact mechanism value::

    >>> contact_mechanism.value = "foo@example.com"

Check notifications::

    >>> len(contact_mechanism.notifications())
    0

Change contact mechanism type::

    >>> contact_mechanism.type = 'other'
    >>> contact_mechanism.value = "test@example.com"

Check notifications::

    >>> len(contact_mechanism.notifications())
    0

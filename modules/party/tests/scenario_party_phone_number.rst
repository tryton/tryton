===========================
Party Phone Number Scenario
===========================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('party')

Create a country::

    >>> Country = Model.get('country.country')
    >>> spain = Country(name='Spain', code='ES')
    >>> spain.save()

Create a party related to the country::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Pam')
    >>> address, = party.addresses
    >>> address.country = spain

The country phone prefix is set when creating a phone of this party::

    >>> local_phone = party.contact_mechanisms.new()
    >>> local_phone.type = 'phone'
    >>> local_phone.value = '666666666'
    >>> local_phone.value
    '+34 666 66 66 66'

The phone prefix is respected when using international prefix::

    >>> international_phone = party.contact_mechanisms.new()
    >>> international_phone.type = 'phone'
    >>> international_phone.value = '+442083661178'
    >>> international_phone.value
    '+44 20 8366 1178'

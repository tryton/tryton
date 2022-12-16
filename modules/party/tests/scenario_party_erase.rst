====================
Party Erase Scenario
====================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules

Install party::

    >>> config = activate_modules('party')

Create a party::

    >>> Party = Model.get('party.party')
    >>> Attachment = Model.get('ir.attachment')
    >>> party = Party(name='Pam')
    >>> _ = party.identifiers.new(code="Identifier")
    >>> _ = party.contact_mechanisms.new(type='other', value="mechanism")
    >>> party.save()
    >>> address, = party.addresses
    >>> address.street = "St sample, 15"
    >>> address.city = "City"
    >>> address.save()
    >>> identifier, = party.identifiers
    >>> contact_mechanism, = party.contact_mechanisms
    >>> attachment = Attachment()
    >>> attachment.resource = party
    >>> attachment.name = "Attachment"
    >>> attachment.save()

Try erase active party::

    >>> erase = Wizard('party.erase', models=[party])
    >>> erase.form.party == party
    True
    >>> erase.execute('erase')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Erase inactive party::

    >>> party.active = False
    >>> party.save()

    >>> erase = Wizard('party.erase', models=[party])
    >>> erase.form.party == party
    True
    >>> erase.execute('erase')

Check fields have been erased::

    >>> party.name
    >>> identifier.reload()
    >>> identifier.code
    u'****'
    >>> address.reload()
    >>> address.street
    >>> address.city
    >>> contact_mechanism.reload()
    >>> contact_mechanism.value
    >>> Attachment.find()
    []

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from proteus import Model

from . import avatar


def setup(config, modules):
    Party = Model.get('party.party')
    Address = Model.get('party.address')
    Country = Model.get('country.country')
    Subdivision = Model.get('country.subdivision')
    ContactMechanism = Model.get('party.contact_mechanism')

    customers, suppliers = [], []

    try:
        us, = Country.find([('code', '=', 'US')])
    except ValueError:
        us = None
    try:
        pennsylvania, = Subdivision.find([('code', '=', 'US-PA')])
    except ValueError:
        pennsylvania = None

    name = 'Electric City Trolley Museum Association'
    try:
        party, = Party.find([('name', '=', name)])
    except ValueError:
        party = Party(name=name)
        party.addresses.pop()
        party.addresses.append(Address(street='300 Cliff Street',
                postal_code='18503', city='Scranton', country=us,
                subdivision=pennsylvania))
        party.contact_mechanisms.append(ContactMechanism(type='phone',
                value='+1 570-963-6590'))
        party.contact_mechanisms.append(ContactMechanism(type='website',
                value='http://www.ectma.org/'))
        party.save()
    customers.append(party)

    name = 'Albright Memorial Library'
    try:
        party, = Party.find([('name', '=', name)])
    except ValueError:
        party = Party(name=name)
        party.addresses.pop()
        party.addresses.append(Address(street='500 Vine Street',
                postal_code='18509', city='Scranton', country=us,
                subdivision=pennsylvania))
        party.contact_mechanisms.append(ContactMechanism(type='phone',
                value='+1 570-348-3000'))
        party.contact_mechanisms.append(ContactMechanism(type='website',
                value='http://www.albright.org/'))
        party.save()
    customers.append(party)

    name = "Cooper's Seafood House"
    try:
        party, = Party.find([('name', '=', name)])
    except ValueError:
        party = Party(name=name)
        party.addresses.pop()
        party.addresses.append(Address(street='701 North Washington Avenue',
                postal_code='18509', city='Scranton', country=us,
                subdivision=pennsylvania))
        party.contact_mechanisms.append(ContactMechanism(type='phone',
                value='+1 570-346-6883'))
        party.save()
    customers.append(party)

    name = "Saber"
    try:
        party, = Party.find([('name', '=', name)])
    except ValueError:
        party = Party(name=name)
        if 'party_avatar' in modules:
            party.avatar = avatar.get('saber.jpg')
        party.save()
    suppliers.append(party)

    return customers, suppliers

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from decimal import Decimal

from proteus import Model, Wizard

from . import avatar


def setup(config, modules):
    Party = Model.get('party.party')
    Company = Model.get('company.company')
    Currency = Model.get('currency.currency')

    usd, = Currency.find([('code', '=', 'USD')])
    rate = usd.rates.new()
    rate.date = dt.date(dt.date.today().year, 1, 1)
    rate.rate = Decimal('1')
    usd.save()

    company_config = Wizard('company.company.config')
    company_config.execute('company')
    company = company_config.form
    party = Party(name='Michael Scott Paper Company')
    if 'party_avatar' in modules:
        party.avatar = avatar.get('michael-scott-paper-inc.jpg')
    party.save()
    company.party = party
    company.currency = usd
    company_config.execute('add')

    # Reload context
    User = Model.get('res.user')
    config._context = User.get_preferences(True, {})

    company, = Company.find()
    return company


def setup_post(config, modules, company):
    Party = Model.get('party.party')
    Company = Model.get('company.company')
    Currency = Model.get('currency.currency')
    Address = Model.get('party.address')
    Country = Model.get('country.country')
    Subdivision = Model.get('country.subdivision')
    Employee = Model.get('company.employee')

    party_avatar = 'party_avatar' in modules

    usd, = Currency.find([('code', '=', 'USD')])
    try:
        us, = Country.find([('code', '=', 'US')])
    except ValueError:
        us = None

    party_scott = Party(name='Michael Scott')
    if party_avatar:
        party_scott.avatar = avatar.get('michael-scott.jpg')
    party_scott.save()
    Employee(party=party_scott, company=company).save()
    party_beesly = Party(name='Pam Beesly')
    if party_avatar:
        party_beesly.avatar = avatar.get('pam-beesly.jpg')
    party_beesly.save()
    Employee(party=party_beesly, company=company).save()
    party_howard = Party(name='Ryan Howard')
    if party_avatar:
        party_howard.avatar = avatar.get('ryan-howard.jpg')
    party_howard.save()
    Employee(party=party_howard, company=company).save()

    dmi = Company()
    party_dmi = Party(name='Dunder Mifflin inc')
    address = Address()
    party_dmi.addresses.append(address)
    address.city = 'New York'
    address.country = us
    try:
        address.subdivision, = Subdivision.find([('code', '=', 'US-NY')])
    except ValueError:
        pass
    if party_avatar:
        party_dmi.avatar = avatar.get('dunder-mifflin.jpg')
    party_dmi.save()
    dmi.party = party_dmi
    dmi.currency = usd
    dmi.save()

    dms = Company()
    party_dms = Party(name='Dunder Mifflin Scranton')
    address = Address()
    party_dms.addresses.append(address)
    address.city = 'Scranton'
    address.country = us
    try:
        address.subdivision, = Subdivision.find([('code', '=', 'US-PA')])
    except ValueError:
        pass
    party_dms.save()
    dms.party = party_dms
    dms.currency = usd
    dms.save()

    party_halper = Party(name='Jim Halper')
    if party_avatar:
        party_halper.avatar = avatar.get('jim-halper.jpg')
    party_halper.save()
    Employee(party=party_halper, company=dms).save()
    party_schrute = Party(name='Dwight Schrute')
    if party_avatar:
        party_schrute.avatar = avatar.get('dwight-schrute.jpg')
    party_schrute.save()
    Employee(party=party_schrute, company=dms).save()
    party_martin = Party(name='Angela Martin')
    if party_avatar:
        party_martin.avatar = avatar.get('angela-martin.jpg')
    party_martin.save()
    Employee(party=party_martin, company=dms).save()
    party_miner = Party(name='Charles Miner')
    if party_avatar:
        party_miner.avatar = avatar.get('charles-miner.jpg')
    party_miner.save()
    Employee(party=party_miner, company=dms).save()


def get():
    Company = Model.get('company.company')
    company, = Company.find([
            ('party.name', '=', 'Michael Scott Paper Company'),
            ])
    return company

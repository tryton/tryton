# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from decimal import Decimal

from proteus import Model, Wizard

from . import avatar


def setup(config, modules):
    Address = Model.get('party.address')
    Company = Model.get('company.company')
    Country = Model.get('country.country')
    Currency = Model.get('currency.currency')
    Party = Model.get('party.party')
    Subdivision = Model.get('country.subdivision')

    usd, = Currency.find([('code', '=', 'USD')])
    rate = usd.rates.new()
    rate.date = dt.date(dt.date.today().year, 1, 1)
    rate.rate = Decimal('1')
    usd.save()
    try:
        us, = Country.find([('code', '=', 'US')])
    except ValueError:
        us = None

    company_config = Wizard('company.company.config')
    company_config.execute('company')
    company = company_config.form
    party = Party(name="Dunder Mifflin")
    address = Address()
    party.addresses.append(address)
    address.street = "1725 Slough Avenue"
    address.city = "Scranton"
    address.country = us
    try:
        address.subdivision, = Subdivision.find([('code', '=', 'US-PA')])
    except ValueError:
        pass
    if 'party_avatar' in modules:
        party.avatar = avatar.get('dunder-mifflin.jpg')
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
    Company = Model.get('company.company')
    Employee = Model.get('company.employee')
    Group = Model.get('res.group')
    Party = Model.get('party.party')
    User = Model.get('res.user')

    party_avatar = 'party_avatar' in modules

    party_scott = Party(name="Michael Scott")
    if party_avatar:
        party_scott.avatar = avatar.get('michael-scott.jpg')
    party_scott.save()
    employee_scott = Employee(party=party_scott, company=company)
    employee_scott.save()
    user_scott = User()
    user_scott.name = "Michael Scott"
    user_scott.login = 'michael'
    user_scott.groups.extend(Group.find([
                ('name', 'not ilike', "%Admin%"),
                ]))
    user_scott.companies.append(Company(company.id))
    user_scott.company = company
    user_scott.employees.append(employee_scott)
    user_scott.employee = employee_scott
    user_scott.avatar = avatar.get('michael-scott.jpg')
    user_scott.save()

    party_beesly = Party(name="Pam Beesly")
    if party_avatar:
        party_beesly.avatar = avatar.get('pam-beesly.jpg')
    party_beesly.save()
    employee_beesly = Employee(party=party_beesly, company=company)
    employee_beesly.save()
    user_beesly = User()
    user_beesly.name = "Pam Beesly"
    user_beesly.login = 'pam'
    user_beesly.groups.extend(Group.find(['OR',
                ('name', 'ilike', "Party%"),
                ('name', 'ilike', "Employee%"),
                ('name', 'ilike', "Timesheet%"),
                ('name', 'ilike', "Project%"),
                ]))
    user_beesly.companies.append(Company(company.id))
    user_beesly.company = company
    user_beesly.employees.append(employee_beesly)
    user_beesly.employee = employee_beesly
    user_beesly.avatar = avatar.get('pam-beesly.jpg')
    user_beesly.save()

    party_howard = Party(name="Ryan Howard")
    if party_avatar:
        party_howard.avatar = avatar.get('ryan-howard.jpg')
    party_howard.save()
    employee_howard = Employee(party=party_howard, company=company)
    employee_howard.save()
    user_howard = User()
    user_howard.name = "Ryan Howard"
    user_howard.login = 'ryan'
    user_howard.companies.append(Company(company.id))
    user_howard.company = company
    user_howard.employees.append(employee_howard)
    user_howard.employee = employee_howard
    user_howard.avatar = avatar.get('ryan-howard.jpg')
    user_howard.save()

    party_halper = Party(name="Jim Halper")
    if party_avatar:
        party_halper.avatar = avatar.get('jim-halper.jpg')
    party_halper.save()
    employee_halper = Employee(party=party_halper, company=company)
    employee_halper.save()
    user_halper = User()
    user_halper.name = "Jim Halper"
    user_halper.login = 'jim'
    user_halper.groups.extend(Group.find(['OR',
                ('name', '=', "Sales"),
                ('name', 'ilike', "Project%"),
                ]))
    user_halper.companies.append(Company(company.id))
    user_halper.company = company
    user_halper.employees.append(employee_halper)
    user_halper.employee = employee_halper
    user_halper.avatar = avatar.get('jim-halper.jpg')
    user_halper.save()

    party_schrute = Party(name="Dwight Schrute")
    if party_avatar:
        party_schrute.avatar = avatar.get('dwight-schrute.jpg')
    party_schrute.save()
    employee_schrute = Employee(party=party_schrute, company=company)
    employee_schrute.save()
    user_schrute = User()
    user_schrute.name = "Dwight Schrute"
    user_schrute.login = 'dwight'
    user_schrute.groups.extend(Group.find(['OR',
                ('name', '=', "Sales"),
                ('name', 'ilike', "Project%"),
                ('name', 'ilike', "Product%"),
                ]))
    user_schrute.companies.append(Company(company.id))
    user_schrute.company = company
    user_schrute.employees.append(employee_schrute)
    user_schrute.employee = employee_schrute
    user_schrute.avatar = avatar.get('dwight-schrute.jpg')
    user_schrute.save()

    party_martin = Party(name="Angela Martin")
    if party_avatar:
        party_martin.avatar = avatar.get('angela-martin.jpg')
    party_martin.save()
    employee_martin = Employee(party=party_martin, company=company)
    employee_martin.save()
    user_martin = User()
    user_martin.name = "Angela Martin"
    user_martin.login = 'angela'
    user_martin.groups.extend(Group.find(['OR',
                ('name', 'ilike', "Account%"),
                ('name', 'ilike', "Bank%"),
                ('name', 'ilike', "Currency%"),
                ('name', 'ilike', "Payment%"),
                ('name', 'ilike', "Statement%"),
                ]))
    user_martin.companies.append(Company(company.id))
    user_martin.company = company
    user_martin.employees.append(employee_martin)
    user_martin.employee = employee_martin
    user_martin.avatar = avatar.get('angela-martin.jpg')
    user_martin.save()

    party_philbin = Party(name="Darryl Philbin")
    if party_avatar:
        party_philbin.avatar = avatar.get('darryl-philbin.jpg')
    party_philbin.save()
    employee_philbin = Employee(party=party_philbin, company=company)
    employee_philbin.save()
    user_philbin = User()
    user_philbin.name = "Darryl Philbin"
    user_philbin.login = 'darryl'
    user_philbin.groups.extend(Group.find(['OR',
                ('name', 'ilike', "Stock%"),
                ]))
    user_philbin.companies.append(Company(company.id))
    user_philbin.company = company
    user_philbin.employees.append(employee_philbin)
    user_philbin.employee = employee_philbin
    user_philbin.avatar = avatar.get('darryl-philbin.jpg')
    user_philbin.save()


def get():
    Company = Model.get('company.company')
    company, = Company.find([
            ('party.name', '=', "Dunder Mifflin"),
            ])
    return company

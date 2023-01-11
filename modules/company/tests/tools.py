# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model, Wizard
from proteus.config import get_config
from trytond.modules.currency.tests.tools import get_currency

__all__ = ['create_company', 'get_company']


def create_company(party=None, currency=None, config=None):
    "Create the company using the proteus config"
    Party = Model.get('party.party', config=config)
    User = Model.get('res.user', config=config)

    company_config = Wizard('company.company.config', config=config)
    company_config.execute('company')
    company = company_config.form
    if not party:
        party = Party(name='Dunder Mifflin')
        party.save()
    company.party = party
    if not currency:
        currency = get_currency(config=config)
    company.currency = currency
    company_config.execute('add')

    if not config:
        config = get_config()
    config._context = User.get_preferences(True, {})
    return company_config


def get_company(config=None):
    "Return the only company"
    Company = Model.get('company.company', config=config)
    company, = Company.find()
    return company

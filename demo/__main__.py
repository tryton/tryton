#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

from proteus import Model, Wizard
from proteus import config as pconfig

from . import account, account_invoice, account_payment, account_statement
from . import company as company_
from . import (
    country, currency, party, product, production, project, purchase, sale,
    stock, timesheet)


def set_config(database, config_file):
    return pconfig.set_trytond(database, config_file=config_file)


def activate_modules(config, modules):
    Module = Model.get('ir.module')
    modules = Module.find([
            ('name', 'in', modules),
            ])
    for module in modules:
        if module.state == 'activated':
            module.click('upgrade')
        else:
            module.click('activate')
    modules = [x.name for x in Module.find([('state', '=', 'to activate')])]
    Wizard('ir.module.activate_upgrade').execute('upgrade')

    ConfigWizardItem = Model.get('ir.module.config_wizard.item')
    for item in ConfigWizardItem.find([('state', '!=', 'done')]):
        item.state = 'done'
        item.save()

    activated_modules = [m.name
        for m in Module.find([('state', '=', 'activated')])]
    return modules, activated_modules


def setup_languages(config, demo_password, company=None):
    Lang = Model.get('ir.lang')
    User = Model.get('res.user')
    Group = Model.get('res.group')
    Action = Model.get('ir.action')

    langs = Lang.find()
    Lang.click(langs, 'load_translations')

    admin = config.user
    # Use root to skip password validation
    config.user = 0

    menu, = Action.find([('usage', '=', 'menu')])
    for lang in langs:
        if lang.code == 'en':
            name = 'Demo'
            login = 'demo'
        else:
            if lang.code[:2] != lang.code[-2:].lower():
                continue
            name = 'Demo %s' % lang.name
            login = 'demo_%s' % lang.code[:2]
        try:
            user, = User.find([('login', '=', login)])
        except ValueError:
            user = User()
        user.name = name
        user.login = login
        user.password = demo_password
        groups = Group.find([
                ('name', 'not ilike', '%Admin%'),
                ])
        user.groups.extend(groups)
        user.language = lang
        user.menu = menu
        if company:
            Company = Model.get('company.company')
            user.companies.append(Company(company.id))
            user.company = company
        user.save()

    config.user = admin


def main(database, modules, demo_password, config_file=None):
    config = set_config(database, config_file)
    to_activate, activated = activate_modules(config, modules)

    if 'country' in to_activate:
        country.do_import()

    if 'currency' in to_activate:
        currency.do_import()

    if ('party' in to_activate
            or 'sale' in to_activate
            or 'purchase' in to_activate
            or 'stock' in activated):
        customers, suppliers = party.setup(config, modules)

    if 'company' in to_activate:
        company = company_.setup(config, activated)
    elif 'company' in activated:
        company = company.get()
    else:
        company = None

    if 'account' in to_activate:
        account.setup(config, activated, company)

    if 'company' in to_activate:
        company_.setup_post(config, activated, company)

    if 'product' in to_activate:
        product.setup(config, activated, company=company)

    if 'account_invoice' in to_activate:
        account_invoice.setup(config, activated, company)

    if 'sale' in to_activate:
        sale.setup(config, activated, company, customers)

    if 'purchase' in to_activate:
        purchase.setup(config, activated, company, suppliers)

    if 'stock' in to_activate:
        stock.setup(config, activated, company, suppliers)

    if 'account_invoice' in activated:
        account_invoice.setup_post(config, activated, company)

    if 'account_payment' in activated:
        account_payment.setup(config, activated, company)

    if 'account_statement' in activated:
        account_statement.setup(config, activated, company)

    if 'project' in activated:
        project.setup(config, activated, company, customers)

    if 'timesheet' in activated:
        timesheet.setup(config, activated, company)

    if 'production' in to_activate:
        production.setup(config, activated, company)

    setup_languages(config, demo_password, company=company)


if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', dest='config_file')
    parser.add_argument('-m', '--module', dest='modules', nargs='+',
        help='module to activate', default=[
            'account',
            'account_invoice',
            'account_payment',
            'account_statement',
            'company',
            'party',
            'party_avatar',
            'product',
            'purchase',
            'sale',
            'stock',
            'project',
            'timesheet',
            'production',
            'production_routing',
            'production_work',
            ])
    parser.add_argument('--demo_password', dest='demo_password',
        default='demo', help='demo password')
    parser.add_argument('-d', '--database', dest='database',
        default='demo', help="database name")
    options = parser.parse_args()
    main(options.database, options.modules, options.demo_password,
        config_file=options.config_file)

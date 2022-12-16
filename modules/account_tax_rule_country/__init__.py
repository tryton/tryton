# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account
from . import sale
from . import purchase
from . import stock


def register():
    Pool.register(
        account.TaxRule,
        account.TaxRuleLineTemplate,
        account.TaxRuleLine,
        module='account_tax_rule_country', type_='model')
    Pool.register(
        account.InvoiceLine,
        module='account_tax_rule_country', type_='model',
        depends=['account_invoice'])
    Pool.register(
        sale.Sale,
        sale.Line,
        module='account_tax_rule_country', type_='model',
        depends=['sale'])
    Pool.register(
        purchase.Purchase,
        purchase.Line,
        module='account_tax_rule_country', type_='model',
        depends=['purchase'])
    Pool.register(
        stock.Move,
        module='account_tax_rule_country', type_='model',
        depends=['stock'])

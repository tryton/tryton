# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import (
    account, company, configuration, opportunity, party, product, sale)


def register():
    Pool.register(
        opportunity.SaleOpportunity,
        opportunity.SaleOpportunityLine,
        opportunity.SaleOpportunityEmployee,
        opportunity.SaleOpportunityEmployeeContext,
        opportunity.SaleOpportunityMonthly,
        opportunity.SaleOpportunityEmployeeMonthly,
        configuration.Configuration,
        configuration.ConfigurationSequence,
        sale.Sale,
        party.Party,
        party.Address,
        account.PaymentTerm,
        account.PaymentTermLine,
        product.Template,
        product.Product,
        company.Company,
        company.Employee,
        module='sale_opportunity', type_='model')
    Pool.register(
        party.Replace,
        module='sale_opportunity', type_='wizard')

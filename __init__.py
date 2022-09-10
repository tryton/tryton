# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import (
    account, company, configuration, opportunity, opportunity_reporting, party,
    product, sale)


def register():
    Pool.register(
        opportunity.SaleOpportunity,
        opportunity.SaleOpportunityLine,
        opportunity_reporting.Context,
        opportunity_reporting.Main,
        opportunity_reporting.MainTimeseries,
        opportunity_reporting.Conversion,
        opportunity_reporting.ConversionTimeseries,
        opportunity_reporting.ConversionEmployee,
        opportunity_reporting.ConversionEmployeeTimeseries,
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

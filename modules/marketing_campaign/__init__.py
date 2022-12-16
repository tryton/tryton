# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

try:
    from trytond.modules.sale.sale_reporting import Abstract as SaleAbstract
except ImportError:
    SaleAbstract = None
try:
    from trytond.modules.sale_opportunity.opportunity_reporting import \
        Abstract as OpportunityAbstract
except ImportError:
    OpportunityAbstract = None

from . import marketing, sale, sale_opportunity_reporting, sale_reporting
from .marketing import MarketingCampaignMixin, Parameter

__all__ = ['register', 'Parameter', 'MarketingCampaignMixin']


def register():
    Pool.register(
        marketing.Campaign,
        marketing.Medium,
        marketing.Source,
        module='marketing_campaign', type_='model')
    Pool.register(
        sale.Sale,
        sale_reporting.Context,
        sale_reporting.MarketingContext,
        sale_reporting.Marketing,
        module='marketing_campaign', type_='model', depends=['sale'])
    Pool.register(
        sale.Opportunity,
        sale_opportunity_reporting.Context,
        sale_opportunity_reporting.MarketingContext,
        sale_opportunity_reporting.Marketing,
        module='marketing_campaign', type_='model',
        depends=['sale_opportunity'])
    Pool.register(
        sale.POSSale,
        module='marketing_campaign', type_='model', depends=['sale_point'])
    if SaleAbstract:
        Pool.register_mixin(
            sale_reporting.AbstractMarketingCampaign, SaleAbstract,
            module='marketing_campaign')
    if OpportunityAbstract:
        Pool.register_mixin(
            sale_opportunity_reporting.AbstractMarketingCampaign,
            OpportunityAbstract,
            module='marketing_campaign')

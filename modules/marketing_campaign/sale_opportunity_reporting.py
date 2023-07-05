# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Column, Literal

from trytond.i18n import lazy_gettext
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

try:
    from trytond.modules.sale_opportunity.opportunity_reporting import Abstract
    from trytond.modules.sale_opportunity.opportunity_reporting import \
        Context as BaseContext
except ImportError:
    Abstract = object
    BaseContext = object

from .marketing import MarketingCampaignMixin


class AbstractMarketingCampaign:
    __slots__ = ()

    @classmethod
    def _marketing_campaign_fields(cls):
        pool = Pool()
        Context = pool.get('sale.opportunity.reporting.context')
        if hasattr(Context, 'marketing_campaign_fields'):
            yield from Context.marketing_campaign_fields()

    @classmethod
    def _columns(cls, tables, withs):
        context = Transaction().context
        opportunity = tables['opportunity']
        return super()._columns(tables, withs) + [
            (Column(opportunity, fname)
                if context.get('group_by_%s' % fname)
                else Literal(None)).as_(fname)
            for fname in cls._marketing_campaign_fields()]

    @classmethod
    def _where(cls, tables, withs):
        context = Transaction().context
        where = super()._where(tables, withs)
        opportunity = tables['opportunity']
        for fname in cls._marketing_campaign_fields():
            value = context.get(fname)
            if value:
                where &= Column(opportunity, fname) == value
        return where


class Context(MarketingCampaignMixin, metaclass=PoolMeta):
    __name__ = 'sale.opportunity.reporting.context'

    @classmethod
    def default_get(cls, fields_names, with_rec_name=True):
        transaction = Transaction()
        context = transaction.context
        default = super().default_get(
            fields_names, with_rec_name=with_rec_name)
        for fname in cls.marketing_campaign_fields():
            if isinstance(context.get(fname), (int, float)):
                default.setdefault(fname, int(context[fname]))
        return default


class MarketingContext(BaseContext, metaclass=PoolMeta):
    "Sale Opportunity Reporting Context"
    __name__ = 'sale.opportunity.reporting.marketing.context'

    group_by_marketing_campaign = fields.Boolean(
        lazy_gettext('marketing_campaign.msg_marketing_campaign'))
    group_by_marketing_medium = fields.Boolean(
        lazy_gettext('marketing_campaign.msg_marketing_medium'))
    group_by_marketing_source = fields.Boolean(
        lazy_gettext('marketing_campaign.msg_marketing_source'))


class Marketing(MarketingCampaignMixin, ModelView, Abstract):
    "Sale Opportunity Reporting per Marketing"
    __name__ = 'sale.opportunity.reporting.marketing'

    @classmethod
    def _group_by(cls, tables, withs):
        context = Transaction().context
        opportunity = tables['opportunity']
        return super()._group_by(tables, withs) + [
            Column(opportunity, fname).as_(fname)
            for fname in cls._marketing_campaign_fields()
            if context.get('group_by_%s' % fname)]

    def get_rec_name(self, name):
        return ', '.join(
            getattr(self, fname).rec_name
            for fname in self._marketing_campaign_fields()
            if getattr(self, fname))

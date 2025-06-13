# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Column, Literal

from trytond.i18n import lazy_gettext
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

try:
    from trytond.modules.sale.sale_reporting import Abstract
    from trytond.modules.sale.sale_reporting import Context as BaseContext
except ImportError:
    Abstract = object
    BaseContext = object

from .marketing import MarketingCampaignMixin


class AbstractMarketingCampaign:
    __slots__ = ()

    @classmethod
    def _marketing_campaign_fields(cls):
        pool = Pool()
        Context = pool.get('sale.reporting.context')
        if hasattr(Context, 'marketing_campaign_fields'):
            yield from Context.marketing_campaign_fields()

    @classmethod
    def _sale_line_columns(cls, line, sale):
        return super()._sale_line_columns(line, sale) + [
            Column(sale, fname).as_(fname)
            for fname in cls._marketing_campaign_fields()]

    @classmethod
    def _pos_sale_line_columns(cls, line, point, sale, currency):
        return super()._pos_sale_line_columns(line, point, sale, currency) + [
            Column(sale, fname).as_(fname)
            for fname in cls._marketing_campaign_fields()]

    @classmethod
    def _where(cls, tables, withs):
        context = Transaction().context
        where = super()._where(tables, withs)
        line = tables['line']
        for fname in cls._marketing_campaign_fields():
            value = context.get(fname)
            if value:
                where &= Column(line, fname) == value
        return where


class Context(MarketingCampaignMixin, metaclass=PoolMeta):
    __name__ = 'sale.reporting.context'

    @classmethod
    def default_get(
            cls, fields_names=None, with_rec_name=True, with_default=True):
        transaction = Transaction()
        context = transaction.context
        default = super().default_get(
            fields_names=fields_names,
            with_rec_name=with_rec_name,
            with_default=with_default)
        for fname in cls.marketing_campaign_fields():
            if isinstance(context.get(fname), (int, float)):
                default.setdefault(fname, int(context[fname]))
        return default


class MarketingContext(BaseContext):
    __name__ = 'sale.reporting.marketing.context'

    group_by_marketing_campaign = fields.Boolean(
        lazy_gettext('marketing_campaign.msg_marketing_campaign'))
    group_by_marketing_medium = fields.Boolean(
        lazy_gettext('marketing_campaign.msg_marketing_medium'))
    group_by_marketing_source = fields.Boolean(
        lazy_gettext('marketing_campaign.msg_marketing_source'))


class Marketing(MarketingCampaignMixin, ModelView, Abstract):
    __name__ = 'sale.reporting.marketing'

    @classmethod
    def _columns(cls, tables, withs):
        context = Transaction().context
        line = tables['line']
        return super()._columns(tables, withs) + [
            (Column(line, fname)
                if context.get('group_by_%s' % fname)
                else Literal(None)).as_(fname)
            for fname in cls._marketing_campaign_fields()]

    @classmethod
    def _group_by(cls, tables, withs):
        context = Transaction().context
        line = tables['line']
        return super()._group_by(tables, withs) + [
            Column(line, fname).as_(fname)
            for fname in cls._marketing_campaign_fields()
            if context.get('group_by_%s' % fname)]

    def get_rec_name(self, name):
        return ', '.join(
            getattr(self, fname).rec_name
            for fname in self._marketing_campaign_fields()
            if getattr(self, fname))

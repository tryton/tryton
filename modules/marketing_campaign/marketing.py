# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sql.functions import Lower
from sql.operators import Equal

from trytond.i18n import lazy_gettext
from trytond.model import (
    DeactivableMixin, Exclude, Model, ModelSQL, ModelView, fields)
from trytond.pool import PoolMeta
from trytond.transaction import Transaction, inactive_records


class Parameter(DeactivableMixin, ModelSQL, ModelView):

    name = fields.Char("Name", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_unique', Exclude(t, (Lower(t.name), Equal)),
                'marketing_campaign.msg_parameter_name_unique'),
            ]
        # TODO: index on name

    def get_rec_name(self, name):
        return self.name.title()

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if values.get('name'):
            values['name'] = values['name'].lower()
        return values

    @classmethod
    def from_name(cls, name, create=True):
        name = name.strip().lower()
        with inactive_records():
            records = cls.search([
                    ('name', '=', name),
                    ])
        if records:
            record, = records
        elif create:
            record = cls(name=name)
            record.save()
        else:
            record = None
        return record


class Campaign(Parameter):
    __name__ = 'marketing.campaign'


class Medium(Parameter):
    __name__ = 'marketing.medium'


class Source(Parameter):
    __name__ = 'marketing.source'


class MarketingCampaignUTM:
    __slots__ = ()

    @property
    def utm_campaign(self):
        if campaign := getattr(self, 'marketing_campaign', None):
            return campaign.name

    @property
    def utm_medium(self):
        if medium := getattr(self, 'marketing_medium', None):
            return medium.name

    @property
    def utm_source(self):
        if source := getattr(self, 'marketing_source', None):
            return source.name

    def add_utm_parameters(self, url):
        params = {}
        for name in ['utm_campaign', 'utm_medium', 'utm_source']:
            if value := getattr(self, name):
                params[name] = value
        if params:
            url_parts = list(urlparse(url))
            query = dict(parse_qsl(url_parts[4]))
            query.update(params)
            url_parts[4] = urlencode(query)
            url = urlunparse(url_parts)
        return url


class MarketingCampaignMixin(Model):

    marketing_campaign = fields.Many2One(
        'marketing.campaign',
        lazy_gettext('marketing_campaign.msg_marketing_campaign'),
        ondelete='RESTRICT')
    marketing_medium = fields.Many2One(
        'marketing.medium',
        lazy_gettext('marketing_campaign.msg_marketing_medium'),
        ondelete='RESTRICT')
    marketing_source = fields.Many2One(
        'marketing.source',
        lazy_gettext('marketing_campaign.msg_marketing_source'),
        ondelete='RESTRICT')

    @classmethod
    def marketing_campaign_fields(cls):
        for fname, field in cls._fields.items():
            if field._type == 'many2one':
                Target = field.get_target()
                if issubclass(Target, Parameter):
                    yield fname

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
            if (isinstance(context.get(fname), str)
                    and context[fname]
                    and not default.get(fname)):
                field = getattr(cls, fname)
                Target = field.get_target()
                target = Target.from_name(
                    context[fname], not transaction.readonly)
                if target:
                    default[fname] = target.id
                    if with_rec_name:
                        default.setdefault(
                            fname + '.', {})['rec_name'] = target.rec_name
        return default


class EmailMessage(MarketingCampaignUTM, MarketingCampaignMixin):
    __name__ = 'marketing.email.message'


class AutomationActivity(MarketingCampaignMixin):
    __name__ = 'marketing.automation.activity'


class AutomationRecordActivity(MarketingCampaignUTM, metaclass=PoolMeta):
    __name__ = 'marketing.automation.record.activity'

    @property
    def utm_campaign(self):
        if campaign := getattr(self.activity, 'marketing_campaign', None):
            return campaign.name

    @property
    def utm_medium(self):
        if medium := getattr(self.activity, 'marketing_medium', None):
            return medium.name

    @property
    def utm_source(self):
        if source := getattr(self.activity, 'marketing_source', None):
            return source.name

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.functions import Lower
from sql.operators import Equal

from trytond.i18n import lazy_gettext
from trytond.model import (
    DeactivableMixin, Exclude, Model, ModelSQL, ModelView, fields)
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
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if values.get('name'):
                values['name'] = values['name'].lower()
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for parameters, values in zip(actions, actions):
            if values.get('name'):
                values = values.copy()
                values['name'] = values['name'].lower()
            args.extend((parameters, values))
        super().write(*args)

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
    "Marketing Campaign"
    __name__ = 'marketing.campaign'


class Medium(Parameter):
    "Marketing Medium"
    __name__ = 'marketing.medium'


class Source(Parameter):
    "Marketing Source"
    __name__ = 'marketing.source'


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
    def default_get(cls, fields_names, with_rec_name=True):
        transaction = Transaction()
        context = transaction.context
        default = super().default_get(
            fields_names, with_rec_name=with_rec_name)
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

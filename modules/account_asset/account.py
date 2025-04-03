# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id, If

asset_bymonthday = fields.Selection([
        ('1', "First"),
        ('-1', "Last"),
        ], "Day of the Month",
    help="The day of the month to create the depreciation moves.")
asset_bymonth = fields.Selection([
        ('1', "January"),
        ('2', "February"),
        ('3', "March"),
        ('4', "April"),
        ('5', "May"),
        ('6', "June"),
        ('7', "July"),
        ('8', "August"),
        ('9', "September"),
        ('10', "October"),
        ('11', "November"),
        ('12', "December"),
        ], "Month", sort=False,
    help="The month to create the depreciation moves.")
asset_frequency = fields.Selection('get_asset_frequencies',
    "Asset Depreciation Frequency",
    required=True, help="The default depreciation frequency for new assets.")


def get_asset_selection(field_name):
    @classmethod
    def get_selection(cls):
        pool = Pool()
        Asset = pool.get('account.asset')
        return Asset.fields_get([field_name])[field_name]['selection']
    return get_selection


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    asset_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Asset Sequence", required=True,
            domain=[
                ('company', 'in', [
                        Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('account_asset', 'sequence_type_asset')),
                ]))
    asset_bymonthday = fields.MultiValue(asset_bymonthday)
    asset_bymonth = fields.MultiValue(asset_bymonth)
    asset_frequency = fields.MultiValue(asset_frequency)

    get_asset_frequencies = get_asset_selection('frequency')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'asset_bymonthday', 'asset_bymonth'}:
            return pool.get('account.configuration.asset_date')
        return super().multivalue_model(field)

    @classmethod
    def default_asset_sequence(cls, **pattern):
        return cls.multivalue_model('asset_sequence').default_asset_sequence()

    @classmethod
    def default_asset_bymonthday(cls, **pattern):
        return cls.multivalue_model(
            'asset_bymonthday').default_asset_bymonthday()

    @classmethod
    def default_asset_bymonth(cls, **pattern):
        return cls.multivalue_model('asset_bymonth').default_asset_bymonth()

    @classmethod
    def default_asset_frequency(cls, **pattern):
        return cls.multivalue_model(
            'asset_frequency').default_asset_frequency()


class ConfigurationAssetSequence(ModelSQL, CompanyValueMixin):
    __name__ = 'account.configuration.asset_sequence'
    asset_sequence = fields.Many2One(
        'ir.sequence', "Asset Reference Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('account_asset', 'sequence_type_asset')),
            ])

    @classmethod
    def default_asset_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('account_asset', 'sequence_asset')
        except KeyError:
            return None


class ConfigurationAssetDate(ModelSQL, CompanyValueMixin):
    __name__ = 'account.configuration.asset_date'
    asset_bymonthday = asset_bymonthday
    asset_bymonth = asset_bymonth

    @classmethod
    def default_asset_bymonthday(cls):
        return "-1"

    @classmethod
    def default_asset_bymonth(cls):
        return "12"


class ConfigurationAssetFrequency(ModelSQL, CompanyValueMixin):
    __name__ = 'account.configuration.asset_frequency'
    asset_frequency = asset_frequency
    get_asset_frequencies = get_asset_selection('frequency')

    @classmethod
    def default_asset_frequency(cls):
        return 'monthly'


def AccountTypeMixin(template=False):

    class Mixin:
        __slots__ = ()
        fixed_asset = fields.Boolean(
            "Fixed Asset",
            domain=[
                If(Eval('statement') != 'balance',
                    ('fixed_asset', '=', False), ()),
                ],
            states={
                'invisible': ((Eval('statement') != 'balance')
                    | ~Eval('assets', True)),
                })
    if not template:
        for fname in dir(Mixin):
            field = getattr(Mixin, fname)
            if not isinstance(field, fields.Field):
                continue
            field.states['readonly'] = (
                Bool(Eval('template', -1)) & ~Eval('template_override', False))
    return Mixin


class AccountTypeTemplate(AccountTypeMixin(template=True), metaclass=PoolMeta):
    __name__ = 'account.account.type.template'

    def _get_type_value(self, type=None):
        values = super()._get_type_value(type=type)
        if not type or type.fixed_asset != self.fixed_asset:
            values['fixed_asset'] = self.fixed_asset
        return values


class AccountType(AccountTypeMixin(), metaclass=PoolMeta):
    __name__ = 'account.account.type'


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        origins = super()._get_origin()
        origins.append('account.asset')
        origins.append('account.asset.line')
        return origins


class Period(metaclass=PoolMeta):
    __name__ = 'account.period'

    def check_asset_line_running(self):
        """
        Check if it exists any asset line without account move for the period.
        """
        pool = Pool()
        Asset = pool.get('account.asset')
        assets = Asset.search([
            ('state', '=', 'running'),
            ('company', '=', self.company.id),
            ('lines', 'where', [
                ('date', '>=', self.start_date),
                ('date', '<=', self.end_date),
                ('move', '=', None),
                ]),
            ], limit=6)
        if assets:
            names = ', '.join(a.rec_name for a in assets[:5])
            if len(assets) > 5:
                names += '...'
            raise AccessError(
                gettext('account_asset.msg_asset_running_close_period',
                    period=self.rec_name,
                    assets=names))

    @classmethod
    def close(cls, periods):
        for period in periods:
            period.check_asset_line_running()
        super().close(periods)


class Journal(metaclass=PoolMeta):
    __name__ = 'account.journal'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('asset', "Asset"))

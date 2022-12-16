# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import CompanyValueMixin

__all__ = ['Configuration', 'ConfigurationAssetSequence',
    'ConfigurationAssetDate', 'Move', 'Period', 'Journal']

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


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    asset_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Asset Reference Sequence", required=True,
            domain=[
                ('company', 'in', [
                        Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'account.asset'),
                ]))
    asset_bymonthday = fields.MultiValue(asset_bymonthday)
    asset_bymonth = fields.MultiValue(asset_bymonth)

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'asset_bymonthday', 'asset_bymonth'}:
            return pool.get('account.configuration.asset_date')
        return super(Configuration, cls).multivalue_model(field)

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


class ConfigurationAssetSequence(ModelSQL, CompanyValueMixin):
    "Account Configuration Asset Sequence"
    __name__ = 'account.configuration.asset_sequence'
    asset_sequence = fields.Many2One(
        'ir.sequence', "Asset Reference Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'account.asset'),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationAssetSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('asset_sequence')
        value_names.append('asset_sequence')
        fields.append('company')
        migrate_property(
            'account.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_asset_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('account_asset', 'sequence_asset')
        except KeyError:
            return None


class ConfigurationAssetDate(ModelSQL, CompanyValueMixin):
    "Account Configuration Asset Date"
    __name__ = 'account.configuration.asset_date'
    asset_bymonthday = asset_bymonthday
    asset_bymonth = asset_bymonth

    @classmethod
    def default_asset_bymonthday(cls):
        return "-1"

    @classmethod
    def default_asset_bymonth(cls):
        return "12"


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        origins = super(Move, cls)._get_origin()
        origins.append('account.asset')
        origins.append('account.asset.line')
        return origins


class Period(metaclass=PoolMeta):
    __name__ = 'account.period'

    @classmethod
    def __setup__(cls):
        super(Period, cls).__setup__()
        cls._error_messages.update({
            'running_assets_close': ('Some asset lines "%(names)s" are still '
                'running for this period "%(period)s".'),
            })

    def check_asset_line_running(self):
        """
        Check if it exist some asset lines without account move for the curent
        period.
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
            self.raise_user_error('running_assets_close', {
                    'period': self.rec_name,
                    'names': names,
                    })

    @classmethod
    def close(cls, periods):
        for period in periods:
            period.check_asset_line_running()
        super(Period, cls).close(periods)


class Journal(metaclass=PoolMeta):
    __name__ = 'account.journal'

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        cls.type.selection.append(('asset', "Asset"))

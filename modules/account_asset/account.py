# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import CompanyValueMixin

__all__ = ['Configuration', 'ConfigurationAssetSequence', 'Move']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'
    asset_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Asset Reference Sequence", required=True,
            domain=[
                ('company', 'in', [
                        Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'account.asset'),
                ]))

    @classmethod
    def default_asset_sequence(cls, **pattern):
        return cls.multivalue_model('asset_sequence').default_asset_sequence()


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


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        origins = super(Move, cls)._get_origin()
        origins.append('account.asset')
        origins.append('account.asset.line')
        return origins

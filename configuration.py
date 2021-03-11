# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pool import Pool
from trytond.pyson import Eval, Id
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Production Configuration'
    __name__ = 'production.configuration'

    production_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Production Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('production', 'sequence_type_production')),
                ]))

    @classmethod
    def default_production_sequence(cls, **pattern):
        return cls.multivalue_model(
            'production_sequence').default_production_sequence()


class ConfigurationProductionSequence(ModelSQL, CompanyValueMixin):
    "Production Configuration Production Sequence"
    __name__ = 'production.configuration.production_sequence'
    production_sequence = fields.Many2One(
        'ir.sequence', "Production Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('production', 'sequence_type_production')),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ConfigurationProductionSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('production_sequence')
        value_names.append('production_sequence')
        fields.append('company')
        migrate_property(
            'production.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_production_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('production', 'sequence_production')
        except KeyError:
            return None

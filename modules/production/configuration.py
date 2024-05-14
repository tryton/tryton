# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton, ModelSQL, ModelView, fields
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.pool import Pool
from trytond.pyson import Eval, Id


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
    bom_sequence = fields.Many2One(
        'ir.sequence', "BOM Sequence",
        domain=[
            ('sequence_type', '=', Id('production', 'sequence_type_bom')),
            ],
        help="Used to generate the BOM code.")

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
            ])

    @classmethod
    def default_production_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('production', 'sequence_production')
        except KeyError:
            return None

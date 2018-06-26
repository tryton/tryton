# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

__all__ = ['Configuration', 'ConfigurationSequence']


class Configuration(metaclass=PoolMeta):
    'Sale Configuration'
    __name__ = 'sale.configuration'
    sale_opportunity_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Opportunity Sequence", required=True,
            domain=[
                ('company', 'in', [Eval('context', {}).get('company', -1),
                        None]),
                ('code', '=', 'sale.opportunity'),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'sale_opportunity_sequence':
            return pool.get('sale.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_sale_opportunity_sequence(cls, **pattern):
        return cls.multivalue_model(
            'sale_opportunity_sequence').default_sale_opportunity_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sequence'
    sale_opportunity_sequence = fields.Many2One(
        'ir.sequence', "Opportunity Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'sale.opportunity'),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)
        if exist:
            table = TableHandler(cls, module_name)
            exist &= table.column_exist('sale_opportunity_sequence')

        super(ConfigurationSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('sale_opportunity_sequence')
        value_names.append('sale_opportunity_sequence')
        super(ConfigurationSequence, cls)._migrate_property(
            field_names, value_names, fields)

    @classmethod
    def default_sale_opportunity_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'sale_opportunity', 'sequence_sale_opportunity')
        except KeyError:
            return None

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    complaint_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Complaint Sequence", required=True,
            domain=[
                ('sequence_type', '=',
                    Id('sale_complaint', 'sequence_type_complaint')),
                ('company', 'in', [
                        Eval('context', {}).get('company', -1), None]),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'complaint_sequence':
            return pool.get('sale.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_complaint_sequence(cls, **pattern):
        return cls.multivalue_model(
            'complaint_sequence').default_complaint_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sequence'
    complaint_sequence = fields.Many2One(
        'ir.sequence', "Complaint Sequence", required=True,
        domain=[
            ('sequence_type', '=',
                Id('sale_complaint', 'sequence_type_complaint')),
            ('company', 'in', [Eval('company', -1), None]),
            ])

    @classmethod
    def default_complaint_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('sale_complaint', 'sequence_complaint')
        except KeyError:
            return None


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['sale.complaint']

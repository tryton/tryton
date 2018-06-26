# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

__all__ = ['Configuration', 'ConfigurationSequence']


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    subscription_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Subscription Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'sale.subscription'),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'subscription_sequence':
            return pool.get('sale.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_subscription_sequence(cls, **pattern):
        return cls.multivalue_model(
            'subscription_sequence').default_subscription_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sequence'
    subscription_sequence = fields.Many2One(
        'ir.sequence', "Subscription Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'sale.subscription'),
            ],
        depends=['company'])

    @classmethod
    def default_subscription_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'sale_subscription', 'sequence_subscription')
        except KeyError:
            return None

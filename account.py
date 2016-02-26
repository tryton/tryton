# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields


__all__ = ['Configuration', 'MoveLine']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'
    default_dunning_procedure = fields.Function(fields.Many2One(
            'account.dunning.procedure', 'Default Dunning Procedure'),
        'get_dunning', setter='set_dunning')

    def get_dunning(self, name):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')
        dunning_field, = ModelField.search([
                ('model.model', '=', 'party.party'),
                ('name', '=', name[8:]),
                ], limit=1)
        properties = Property.search([
                ('field', '=', dunning_field.id),
                ('res', '=', None),
                ], limit=1)
        if properties:
            prop, = properties
            return prop.value.id

    @classmethod
    def set_dunning(cls, configurations, name, value):
        pool = Pool()
        Property = pool.get('ir.property')
        ModelField = pool.get('ir.model.field')
        dunning_field, = ModelField.search([
                ('model.model', '=', 'party.party'),
                ('name', '=', name[8:]),
                ], limit=1)
        properties = Property.search([
                ('field', '=', dunning_field.id),
                ('res', '=', None),
                ])
        Property.delete(properties)
        if value:
            Property.create([{
                        'field': dunning_field.id,
                        'value': 'account.dunning.procedure,%s' % value,
                        }])


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    dunnings = fields.One2Many('account.dunning', 'line', 'Dunnings')

    @property
    def dunning_procedure(self):
        if self.party:
            return self.party.dunning_procedure

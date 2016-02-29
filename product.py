# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

from trytond.pool import PoolMeta
from trytond.model import ModelSQL, fields


__all__ = ['Template', 'Template_Agent', 'Product']


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    principals = fields.Many2Many('product.template-commission.agent',
        'template', 'agent', 'Commission Principals',
        domain=[
            ('type_', '=', 'principal'),
            ])

    @property
    def principal(self):
        if self.principals:
            return self.principals[0]


class Template_Agent(ModelSQL):
    'Product Template - Commission Agent'
    __name__ = 'product.template-commission.agent'
    template = fields.Many2One('product.template', 'Template',
        required=True, select=True)
    agent = fields.Many2One('commission.agent', 'Agent',
        required=True, select=True,
        domain=[
            ('type_', '=', 'principal'),
            ])


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'

    @property
    def principal(self):
        return self.template.principal

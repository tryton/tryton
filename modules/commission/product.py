# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    principals = fields.Many2Many('product.template-commission.agent',
        'template', 'agent', 'Commission Principals',
        domain=[
            ('type_', '=', 'principal'),
            ],
        filter=[
            ('active', '=', True),
            ],
        help="The principals who pay a commission when the product is sold.")

    @property
    def principal(self):
        company_id = self._context.get('company')
        for agent in self.principals:
            if agent.company.id == company_id:
                return agent


class Template_Agent(ModelSQL):
    __name__ = 'product.template-commission.agent'
    template = fields.Many2One(
        'product.template', "Template", required=True)
    agent = fields.Many2One(
        'commission.agent', "Agent", required=True,
        domain=[
            ('type_', '=', 'principal'),
            ])


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @property
    def principal(self):
        return self.template.principal

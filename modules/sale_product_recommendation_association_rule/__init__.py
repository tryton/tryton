# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import ir, sale

__all__ = ['register']


def register():
    Pool.register(
        ir.Cron,
        sale.Configuration,
        sale.Sale,
        sale.ProductAssociationRule,
        sale.ProductAssociationRuleAntecedent,
        sale.ProductAssociationRuleConsequent,
        module='sale_product_recommendation_association_rule', type_='model')
    Pool.register(
        sale.ProductAssociationRulePOS,
        module='sale_product_recommendation_association_rule', type_='model',
        depends=['sale_point'])

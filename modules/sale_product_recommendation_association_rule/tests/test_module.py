# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.tests.test_tryton import ModuleTestCase


class SaleProductRecommendationAssociationRuleTestCase(ModuleTestCase):
    "Test Sale Product Recommendation Association Rule module"
    module = 'sale_product_recommendation_association_rule'
    extras = ['sale_point']


del ModuleTestCase

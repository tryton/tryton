# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval

__all__ = ['Service']


class Service(ModelSQL, ModelView):
    "Subscription Service"
    __name__ = 'sale.subscription.service'

    product = fields.Many2One(
        'product.product', "Product", required=True,
        domain=[
            ('type', '=', 'service'),
            ])
    consumption_recurrence = fields.Many2One(
        'sale.subscription.recurrence.rule.set', "Consumption Recurrence")
    consumption_delay = fields.TimeDelta("Consumption Delay",
        states={
            'invisible': ~Eval('consumption_recurrence'),
            },
        depends=['consumption_recurrence'])

    def get_rec_name(self, name):
        return self.product.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name',) + tuple(clause[1:])]

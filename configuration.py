# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton, ModelView, fields
from trytond.pyson import Eval, Get


class Configuration(ModelSingleton, ModelView):
    _name = 'stock.configuration'

    cost_price_counterpart_account = fields.Property(fields.Many2One(
            'account.account', 'Cost Price Counterpart Account', domain=[
                ('company', 'in', [Get(Eval('context', {}), 'company'), False]),
                ]))

Configuration()

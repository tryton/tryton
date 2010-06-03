#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import ModelWorkflow, ModelView, ModelSQL, fields
import copy


class Sale(ModelWorkflow, ModelSQL, ModelView):
    _name = 'sale.sale'

    price_list = fields.Many2One('product.price_list', 'Price List',
            domain=["('company', '=', company)"],
            states={
                'readonly': "state != 'draft' or bool(lines)",
            })

    def __init__(self):
        super(Sale, self).__init__()
        if 'bool(lines)' not in self.party.states['readonly']:
            self.party = copy.copy(self.party)
            self.party.states = copy.copy(self.party.states)
            self.party.states['readonly'] = \
                    '(' + self.party.states['readonly'] + ') ' \
                    'or bool(lines)'
        if 'not bool(party)' not in self.lines.states['readonly']:
            self.lines = copy.copy(self.lines)
            self.lines.states = copy.copy(self.lines.states)
            self.lines.states['readonly'] = \
                    '(' + self.lines.states['readonly'] + ') ' \
                    'or not bool(party)'
        self._reset_columns()

    def on_change_party(self, cursor, user, ids, values, context=None):
        party_obj = self.pool.get('party.party')
        price_list_obj = self.pool.get('product.price_list')
        res = super(Sale, self).on_change_party(cursor, user, ids, values,
                context=context)
        res['price_list'] = False
        if values.get('party'):
            party = party_obj.browse(cursor, user, values['party'],
                    context=context)
            res['price_list'] = party.sale_price_list and \
                    party.sale_price_list.id or False
        if res['price_list']:
            res['price_list.rec_name'] = price_list_obj.browse(cursor, user,
                    res['price_list'], context=context).rec_name
        return res

Sale()


class SaleLine(ModelSQL, ModelView):
    _name = 'sale.line'

    def __init__(self):
        super(SaleLine, self).__init__()
        if '_parent_sale.price_list' not in self.quantity.on_change:
            self.quantity = copy.copy(self.quantity)
            self.quantity.on_change = copy.copy(self.quantity.on_change)
            self.quantity.on_change.append('_parent_sale.price_list')
        if '_parent_sale.price_list' not in self.unit.on_change:
            self.unit = copy.copy(self.unit)
            self.unit.on_change = copy.copy(self.unit.on_change)
            self.unit.on_change.append('_parent_sale.price_list')
        if '_parent_sale.price_list' not in self.product.on_change:
            self.product = copy.copy(self.product)
            self.product.on_change = copy.copy(self.product.on_change)
            self.product.on_change.append('_parent_sale.price_list')
        self._reset_columns()

    def _get_context_sale_price(self, cursor, user, product, vals,
            context=None):
        res = super(SaleLine, self)._get_context_sale_price(cursor, user,
                product, vals, context=context)
        if vals.get('_parent_sale.price_list'):
            res['price_list'] = vals['_parent_sale.price_list']
        return res

SaleLine()

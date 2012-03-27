#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from trytond.model import Model, fields
from trytond.pyson import Eval, Not, Equal, Or, Bool
from trytond.pool import Pool


class Sale(Model):
    _name = 'sale.sale'

    price_list = fields.Many2One('product.price_list', 'Price List',
        domain=[('company', '=', Eval('company'))],
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines'))),
            },
        depends=['state', 'company', 'lines'])

    def __init__(self):
        super(Sale, self).__init__()
        self.party = copy.copy(self.party)
        self.party.states = copy.copy(self.party.states)
        self.party.states['readonly'] = Or(self.party.states['readonly'],
                Bool(Eval('lines')))
        if 'lines' not in self.party.depends:
            self.party.depends = copy.copy(self.party.depends)
            self.party.depends.append('lines')
        self.lines = copy.copy(self.lines)
        self.lines.states = copy.copy(self.lines.states)
        self.lines.states['readonly'] = Or(self.lines.states['readonly'],
                Not(Bool(Eval('party'))))
        if 'party' not in self.lines.depends:
            self.lines.depends = copy.copy(self.lines.depends)
            self.lines.depends.append('party')
        self._reset_columns()

    def on_change_party(self, values):
        party_obj = Pool().get('party.party')
        price_list_obj = Pool().get('product.price_list')
        res = super(Sale, self).on_change_party(values)
        res['price_list'] = None
        if values.get('party'):
            party = party_obj.browse(values['party'])
            res['price_list'] = party.sale_price_list and \
                    party.sale_price_list.id or None
        if res['price_list']:
            res['price_list.rec_name'] = price_list_obj.browse(
                    res['price_list']).rec_name
        return res

Sale()


class SaleLine(Model):
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

    def _get_context_sale_price(self, product, vals):
        res = super(SaleLine, self)._get_context_sale_price(product, vals)
        if vals.get('_parent_sale.price_list'):
            res['price_list'] = vals['_parent_sale.price_list']
        return res

SaleLine()

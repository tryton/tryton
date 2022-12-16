#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
import datetime
from trytond.model import ModelView, ModelSQL
from trytond.transaction import Transaction
from trytond.pool import Pool


class Template(ModelSQL, ModelView):
    _name = "product.template"

    def __init__(self):
        super(Template, self).__init__()
        new_sel = ('fifo', 'FIFO')
        if new_sel not in self.cost_price_method.selection:
            self.cost_price_method = copy.copy(self.cost_price_method)
            self.cost_price_method.selection.append(new_sel)
            self._reset_columns()

    def get_fifo_move(self, template_id, quantity=0.0):
        '''
        Return a list of (move, qty) where move is the move to be
        consumed and qty is the quantity (in the product default uom)
        to be consumed on this move. The list contains the "first in"
        moves for the given quantity.

        :param template_id: the product template id
        :param quantity: the quantity to be removed from the stock
        :return: list of (move, qty) where move is a browse record,
        qty is a float
        '''
        pool = Pool()
        move_obj = pool.get('stock.move')
        uom_obj = pool.get('product.uom')
        location_obj = pool.get('stock.location')

        locations = location_obj.search([
            ('type', '=', 'storage'),
            ])
        stock_date_end = datetime.date.today()

        with Transaction().set_context(locations=locations,
                stock_date_end=stock_date_end):
            template = self.browse(template_id)
        offset = 0
        limit = Transaction().cursor.IN_MAX
        avail_qty = template.quantity
        fifo_moves = []

        while avail_qty > 0.0:
            move_ids = move_obj.search([
                ('product.template.id', '=', template.id),
                ('state', '=', 'done'),
                ('from_location.type', '=', 'supplier'),
                ], offset=offset, limit=limit,
                order=[('effective_date', 'DESC'), ('id', 'DESC')])
            if not move_ids:
                break
            offset += limit

            for move in move_obj.browse(move_ids):
                qty = uom_obj.compute_qty(move.uom,
                        move.quantity - move.fifo_quantity,
                        template.default_uom, round=False)
                avail_qty -= qty

                if avail_qty <= quantity:
                    if avail_qty > 0.0:
                        fifo_moves.append(
                            (move, min(qty, quantity - avail_qty)))
                    else:
                        fifo_moves.append(
                            (move, min(quantity, qty + avail_qty)))
                        break

        fifo_moves.reverse()
        return fifo_moves

Template()

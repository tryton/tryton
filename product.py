#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
import copy
import datetime


class Template(ModelSQL, ModelView):
    _name = "product.template"

    def __init__(self):
        super(Template, self).__init__()
        new_sel = ('fifo', 'FIFO')
        if new_sel not in self.cost_price_method.selection:
            self.cost_price_method = copy.copy(self.cost_price_method)
            self.cost_price_method.selection.append(new_sel)
            self._reset_columns()

    def get_fifo_move(self, cursor, user, template_id, quantity=0.0,
            context=None):
        '''
        Return a list of (move, qty) where move is the move to be
        consumed and qty is the quantity (in the product default uom)
        to be consumed on this move. The list contains the "first in"
        moves for the given quantity.

        :param cursor: the database cursor
        :param user: the user id
        :param template_id: the product template id
        :param quantity: the quantity to be removed from the stock
        :param context: the context
        :return: list of (move, qty) where move is a browse record,
        qty is a float
        '''
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        location_obj = self.pool.get('stock.location')

        ctx = context and context.copy() or {}
        ctx['locations'] = location_obj.search(cursor, user, [
            ('type', '=', 'storage'),
            ], context=context)
        ctx['stock_date_end'] = datetime.date.today()

        template = self.browse(cursor, user, template_id, context=ctx)
        offset = 0
        limit = cursor.IN_MAX
        avail_qty = template.quantity
        fifo_moves = []

        while avail_qty > 0.0:
            move_ids = move_obj.search(cursor, user, [
                ('product.template.id', '=', template.id),
                ('state', '=', 'done'),
                ('from_location.type', '=', 'supplier'),
                ], offset=offset, limit=limit,
                order=[('effective_date', 'DESC'), ('id', 'DESC')],
                context=context)
            if not move_ids:
                break
            offset += limit

            for move in move_obj.browse(cursor, user, move_ids,
                    context=context):
                qty = uom_obj.compute_qty(cursor, user, move.uom,
                        move.quantity - move.fifo_quantity,
                        template.default_uom, round=False, context=context)
                avail_qty -= qty

                if avail_qty <= quantity:
                    if avail_qty > 0.0:
                        fifo_moves.append((move, min(qty, quantity - avail_qty)))
                    else:
                        fifo_moves.append((move, min(quantity, qty + avail_qty)))
                        break

        fifo_moves.reverse()
        return fifo_moves

Template()

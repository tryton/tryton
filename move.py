#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV


class Move(OSV):
    _name = 'stock.move'
    fifo_quantity = fields.Float('FIFO Quantity',
            digits="(16, unit_digits)")

    def __init__(self):
        super(Move, self).__init__()
        self._sql_constraints += [
            ('check_fifo_quantity_out',
                'CHECK(quantity >= fifo_quantity)',
                'FIFO quantity can not be greater than quantity!'),
        ]
        self._error_messages.update({
            'del_move_fifo': 'You can not delete move that is used ' \
                    'for FIFO cost price!',
            })

    def default_fifo_quantity_out(self, cursor, user, context=None):
        return 0.0

    def _update_fifo_out_product_cost_price(self, cursor, user, product,
            quantity, uom, context=None):
        '''
        Update the cost price for the given product for out move

        :param cursor: the database cursor
        :param user: the user id
        :param product: a BrowseRecord of the product
        :param quantity: the quantity of the outgoing product
        :param uom: the uom id or a BrowseRecord of the uom
        :param context: the context
        '''
        template_obj = self.pool.get('product.template')
        uom_obj = self.pool.get('product.uom')

        fifo_move_id = template_obj.get_fifo_move(cursor, user,
                product.template.id, context=context)
        if not fifo_move_id:
            return

        remain_quantity = quantity
        if isinstance(uom, (int, long)):
            uom = uom_obj.browse(cursor, user, uom, context=context)

        while remain_quantity > 0.0:
            fifo_move = self.browse(cursor, user, fifo_move_id, context=context)
            qty = uom_obj.compute_qty(cursor, user, uom, remain_quantity,
                    fifo_move.uom, round=False, context=context)
            if qty > (fifo_move.quantity - fifo_move.fifo_quantity):
                qty = fifo_move.quantity - fifo_move.fifo_quantity

            self._update_product_cost_price(cursor, user, product.id,
                    -qty, fifo_move.uom, fifo_move.unit_price,
                    fifo_move.currency, fifo_move.company, context=context)

            remain_quantity -= uom_obj.compute_qty(cursor, user,
                    fifo_move.uom, qty, uom, round=False,
                    context=context)

            self.write(cursor, user, fifo_move.id, {
                'fifo_quantity': fifo_move.fifo_quantity + \
                        qty
                }, context=context)

            if remain_quantity > 0.0:
                fifo_move_id = template_obj.get_fifo_move(
                        cursor, user, product.template.id,
                        uom_obj.compute_qty(cursor, user, uom,
                            quantity - remain_quantity, product.default_uom,
                            round=False, context=context), context=context)
                if not fifo_move_id:
                    return

    def create(self, cursor, user, vals, context=None):
        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')

        if vals.get('state') == 'done':
            from_location = location_obj.browse(cursor, user,
                    vals['from_location'], context=context)
            to_location = location_obj.browse(cursor, user,
                    vals['to_location'], context=context)
            product = product_obj.browse(cursor, user, vals['product'],
                    context=context)
            if from_location.type == 'supplier' \
                    and product.cost_price_method == 'fifo':
                self._update_product_cost_price(cursor, user,
                        vals['product'], vals['quantity'], vals['uom'],
                        vals['unit_price'], vals['currency'],
                        context=context)
            if to_location.type != 'storage' \
                    and product.cost_price_method == 'fifo':
                self._update_fifo_out_product_cost_price(cursor, user, product,
                        vals['quantity'], vals['uom'], context=context)
        return super(Move, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if 'state' in vals and vals['state'] == 'done':
            if isinstance(ids, (int, long)):
                ids = [ids]
            for move in self.browse(cursor, user, ids, context=context):
                if move.type == 'input' and move.state != 'done' \
                        and move.product.cost_price_method == 'fifo':
                    self._update_product_cost_price(cursor, user,
                            move.product.id, move.quantity, move.uom,
                            move.unit_price, move.currency, move.company,
                            context=context)
                if move.to_location.type != 'storage' \
                        and move.product.cost_price_method == 'fifo':
                    self._update_fifo_out_product_cost_price(cursor, user,
                            move.product, move.quantity, move.uom.id,
                            context=context)
        return super(Move, self).write(cursor, user, ids, vals, context=context)

    def delete(self, cursor, user, ids, context=None):
        if self.search(cursor, user, [
            ('id', 'in', ids),
            ('fifo_quantity', '!=', 0.0),
            ], context=context):
            self.raise_user_error(cursor, 'del_move_fifo', context=context)
        return super(Move, self).delete(cursor, user, ids, context=context)
Move()

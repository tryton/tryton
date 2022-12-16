#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from decimal import Decimal


class Move(ModelSQL, ModelView):
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

    def default_fifo_quantity(self, cursor, user, context=None):
        return 0.0

    def _update_fifo_out_product_cost_price(self, cursor, user, product,
            quantity, uom, context=None):
        '''
        Update the product cost price of the given product. Update
        fifo_quantity on the concerned incomming moves. Return the
        cost price for outputing the given product and quantity.

        :param cursor: the database cursor
        :param user: the user id
        :param product: a BrowseRecord of the product
        :param quantity: the quantity of the outgoing product
        :param uom: the uom id or a BrowseRecord of the uom
        :param context: the context
        :return: cost_price (of type decimal)
        '''

        template_obj = self.pool.get('product.template')
        uom_obj = self.pool.get('product.uom')

        if isinstance(uom, (int, long)):
            uom = uom_obj.browse(cursor, user, uom, context=context)

        total_qty = uom_obj.compute_qty(
            cursor, user, uom, quantity, product.default_uom, round=False,
            context=context)

        fifo_moves = template_obj.get_fifo_move(
            cursor, user, product.template.id, total_qty, context=context)


        cost_price = Decimal("0.0")
        consumed_qty = 0.0
        for move, move_qty in fifo_moves:
            consumed_qty += move_qty

            move_unit_price = uom_obj.compute_price(
                cursor, user, move.uom, move.unit_price,
                move.product.default_uom, context=context)
            cost_price += move_unit_price * Decimal(str(move_qty))

            self._update_product_cost_price(
                cursor, user, product.id, -move_qty, product.default_uom,
                move_unit_price, move.currency, move.company, context=context)

            move_qty = uom_obj.compute_qty(
                cursor, user, product.default_uom, move_qty, move.uom,
                round=False, context=context)
            self.write(
                cursor, user, move.id,
                {'fifo_quantity': (move.fifo_quantity or 0.0) + move_qty},
                context=context)


        if Decimal(str(consumed_qty)) != Decimal("0"):
            cost_price = cost_price / Decimal(str(consumed_qty))

        if cost_price != Decimal("0"):
            return cost_price
        else:
            return product.cost_price

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
            if to_location.type == 'supplier' \
                    and product.cost_price_method == 'fifo':
                self._update_product_cost_price(cursor, user,
                        vals['product'], -vals['quantity'], vals['uom'],
                        vals['unit_price'], vals['currency'],
                        context=context)
            if to_location.type != 'storage' \
                    and to_location.type != 'supplier' \
                    and product.cost_price_method == 'fifo':

                cost_price = self._update_fifo_out_product_cost_price(
                    cursor, user, product, vals['quantity'], vals['uom'],
                    context=context)
                if not vals.get('cost_price'):
                    vals['cost_price'] = cost_price

        return super(Move, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 'state' in vals and vals['state'] == 'done':
            for move in self.browse(cursor, user, ids, context=context):
                if vals['state'] == 'cancel':
                    if move.from_location.type == 'supplier' \
                            and move.state != 'cancel' \
                            and move.product.cost_price_method == 'fifo':
                        self._update_product_cost_price(cursor, user,
                                move.product.id, -move.quantity, move.uom,
                                move.unit_price, move.currency, move.company,
                                context=context)
                    if move.to_location.type == 'supplier' \
                            and move.state != 'cancel' \
                            and move.product.cost_price_method == 'fifo':
                        self._update_product_cost_price(cursor, user,
                                move.product.id, move.quantity, move.uom,
                                move.unit_price, move.currency, move.company,
                                context=context)
                    #XXX update cost price for out move cancelled

                elif vals['state'] == 'done':
                    if move.from_location.type == 'supplier' \
                            and move.state != 'done' \
                            and move.product.cost_price_method == 'fifo':
                        self._update_product_cost_price(cursor, user,
                                move.product.id, move.quantity, move.uom,
                                move.unit_price, move.currency, move.company,
                                context=context)
                    if move.to_location.type == 'supplier' \
                            and move.state != 'done' \
                            and move.product.cost_price_method == 'fifo':
                        self._update_product_cost_price(cursor, user,
                                move.product.id, -move.quantity, move.uom,
                                move.unit_price, move.currency, move.company,
                                context=context)
                    if move.to_location.type != 'storage' \
                            and move.to_location.type != 'supplier' \
                            and move.product.cost_price_method == 'fifo':
                        cost_price = self._update_fifo_out_product_cost_price(
                            cursor, user, move.product, move.quantity,
                            move.uom, context=context)
                        if not vals.get('cost_price'):
                            vals['cost_price'] = cost_price
        return super(Move, self).write(cursor, user, ids, vals, context=context)

    def delete(self, cursor, user, ids, context=None):
        if self.search(cursor, user, [
            ('id', 'in', ids),
            ('fifo_quantity', '!=', 0.0),
            ], context=context):
            self.raise_user_error(cursor, 'del_move_fifo', context=context)
        return super(Move, self).delete(cursor, user, ids, context=context)
Move()

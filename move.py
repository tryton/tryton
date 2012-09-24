#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta

__all__ = ['Move']
__metaclass__ = PoolMeta


class Move:
    __name__ = 'stock.move'
    fifo_quantity = fields.Float('FIFO Quantity',
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._sql_constraints += [
                ('check_fifo_quantity_out',
                    'CHECK(quantity >= fifo_quantity)',
                    'FIFO quantity can not be greater than quantity!'),
                ]
        cls._error_messages.update({
                'del_move_fifo': 'You can not delete move that is used '\
                    'for FIFO cost price!',
                })

    @staticmethod
    def default_fifo_quantity():
        return 0.0

    @classmethod
    def _update_fifo_out_product_cost_price(cls, product, quantity, uom,
            date):
        '''
        Update the product cost price of the given product. Update
        fifo_quantity on the concerned incomming moves. Return the
        cost price for outputing the given product and quantity.
        '''

        Uom = Pool().get('product.uom')

        total_qty = Uom.compute_qty(uom, quantity, product.default_uom,
                round=False)

        fifo_moves = product.template.get_fifo_move(total_qty)

        cost_price = Decimal("0.0")
        consumed_qty = 0.0
        for move, move_qty in fifo_moves:
            consumed_qty += move_qty

            move_unit_price = Uom.compute_price(move.uom, move.unit_price,
                    move.product.default_uom)
            cost_price += move_unit_price * Decimal(str(move_qty))

            cls._update_product_cost_price(product.id, -move_qty,
                    product.default_uom, move_unit_price, move.currency,
                    move.company, date)

            move_qty = Uom.compute_qty(product.default_uom, move_qty,
                    move.uom, round=False)
            cls.write([move], {
                'fifo_quantity': (move.fifo_quantity or 0.0) + move_qty,
                })

        if Decimal(str(consumed_qty)) != Decimal("0"):
            cost_price = cost_price / Decimal(str(consumed_qty))

        if cost_price != Decimal("0"):
            digits = cls.cost_price.digits
            return cost_price.quantize(
                Decimal(str(10.0 ** -digits[1])))
        else:
            return product.cost_price

    @classmethod
    def create(cls, vals):
        pool = Pool()
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')

        today = Date.today()
        effective_date = vals.get('effective_date') or today

        if vals.get('state') == 'done':
            from_location = Location(vals['from_location'])
            to_location = Location(vals['to_location'])
            product = Product(vals['product'])
            if (from_location.type in ('supplier', 'production')
                    and to_location.type == 'storage'
                    and product.cost_price_method == 'fifo'):
                cls._update_product_cost_price(vals['product'],
                        vals['quantity'], vals['uom'], vals['unit_price'],
                        vals['currency'], effective_date)
            if (to_location.type == 'supplier'
                    and from_location.type == 'storage'
                    and product.cost_price_method == 'fifo'):
                cls._update_product_cost_price(vals['product'],
                        -vals['quantity'], vals['uom'], vals['unit_price'],
                        vals['currency'], effective_date)
            if to_location.type != 'storage' \
                    and to_location.type != 'supplier' \
                    and product.cost_price_method == 'fifo':

                cost_price = cls._update_fifo_out_product_cost_price(product,
                        vals['quantity'], vals['uom'], effective_date)
                if not vals.get('cost_price'):
                    vals['cost_price'] = cost_price

        return super(Move, cls).create(vals)

    @classmethod
    def write(cls, moves, vals):
        Date = Pool().get('ir.date')

        today = Date.today()
        effective_date = vals.get('effective_date') or today

        if 'state' in vals and vals['state'] == 'done':
            for move in moves:
                if vals['state'] == 'cancel':
                    if (move.from_location.type in ('supplier', 'production')
                            and move.to_location.type == 'storage'
                            and move.state != 'cancel'
                            and move.product.cost_price_method == 'fifo'):
                        cls._update_product_cost_price(move.product.id,
                                -move.quantity, move.uom, move.unit_price,
                                move.currency, move.company, effective_date)
                    if (move.to_location.type == 'supplier'
                            and move.from_location.type == 'storage'
                            and move.state != 'cancel'
                            and move.product.cost_price_method == 'fifo'):
                        cls._update_product_cost_price(move.product.id,
                                move.quantity, move.uom, move.unit_price,
                                move.currency, move.company, effective_date)

                elif vals['state'] == 'done':
                    if (move.from_location.type in ('supplier', 'production')
                            and move.to_location.type == 'storage'
                            and move.state != 'done'
                            and move.product.cost_price_method == 'fifo'):
                        cls._update_product_cost_price(move.product.id,
                                move.quantity, move.uom, move.unit_price,
                                move.currency, move.company, effective_date)
                    if (move.to_location.type == 'supplier'
                            and move.from_location.type == 'storage'
                            and move.state != 'done'
                            and move.product.cost_price_method == 'fifo'):
                        cls._update_product_cost_price(move.product.id,
                                -move.quantity, move.uom, move.unit_price,
                                move.currency, move.company, effective_date)
                    if move.to_location.type != 'storage' \
                            and move.to_location.type != 'supplier' \
                            and move.product.cost_price_method == 'fifo':
                        cost_price = cls._update_fifo_out_product_cost_price(
                                move.product, move.quantity, move.uom,
                                effective_date)
                        if not vals.get('cost_price'):
                            vals['cost_price'] = cost_price
        super(Move, cls).write(moves, vals)

    @classmethod
    def delete(cls, moves):
        if cls.search([
                ('id', 'in', [m.id for m in moves]),
                ('fifo_quantity', '!=', 0.0),
                ]):
            cls.raise_user_error('del_move_fifo')
        super(Move, cls).delete(moves)

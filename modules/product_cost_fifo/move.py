#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.pool import Pool


class Move(ModelSQL, ModelView):
    _name = 'stock.move'
    fifo_quantity = fields.Float('FIFO Quantity',
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])

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

    def default_fifo_quantity(self):
        return 0.0

    def _update_fifo_out_product_cost_price(self, product, quantity, uom,
            date):
        '''
        Update the product cost price of the given product. Update
        fifo_quantity on the concerned incomming moves. Return the
        cost price for outputing the given product and quantity.

        :param product: a BrowseRecord of the product
        :param quantity: the quantity of the outgoing product
        :param uom: the uom id or a BrowseRecord of the uom
        :param date: the date for the currency rate calculation
        :return: cost_price (of type decimal)
        '''

        template_obj = Pool().get('product.template')
        uom_obj = Pool().get('product.uom')

        if isinstance(uom, (int, long)):
            uom = uom_obj.browse(uom)

        total_qty = uom_obj.compute_qty(uom, quantity, product.default_uom,
                round=False)

        fifo_moves = template_obj.get_fifo_move(product.template.id, total_qty)

        cost_price = Decimal("0.0")
        consumed_qty = 0.0
        for move, move_qty in fifo_moves:
            consumed_qty += move_qty

            move_unit_price = uom_obj.compute_price(move.uom, move.unit_price,
                    move.product.default_uom)
            cost_price += move_unit_price * Decimal(str(move_qty))

            self._update_product_cost_price(product.id, -move_qty,
                    product.default_uom, move_unit_price, move.currency,
                    move.company, date)

            move_qty = uom_obj.compute_qty(product.default_uom, move_qty,
                    move.uom, round=False)
            self.write(move.id, {
                'fifo_quantity': (move.fifo_quantity or 0.0) + move_qty,
                })

        if Decimal(str(consumed_qty)) != Decimal("0"):
            cost_price = cost_price / Decimal(str(consumed_qty))

        if cost_price != Decimal("0"):
            digits = self.cost_price.digits
            return cost_price.quantize(
                Decimal(str(10.0 ** -digits[1])))
        else:
            return product.cost_price

    def create(self, vals):
        pool = Pool()
        location_obj = pool.get('stock.location')
        product_obj = pool.get('product.product')
        date_obj = pool.get('ir.date')

        today = date_obj.today()
        effective_date = vals.get('effective_date') or today

        if vals.get('state') == 'done':
            from_location = location_obj.browse(vals['from_location'])
            to_location = location_obj.browse(vals['to_location'])
            product = product_obj.browse(vals['product'])
            if (from_location.type in ('supplier', 'production')
                    and to_location.type == 'storage'
                    and product.cost_price_method == 'fifo'):
                self._update_product_cost_price(vals['product'],
                        vals['quantity'], vals['uom'], vals['unit_price'],
                        vals['currency'], effective_date)
            if (to_location.type == 'supplier'
                    and from_location.type == 'storage'
                    and product.cost_price_method == 'fifo'):
                self._update_product_cost_price(vals['product'],
                        -vals['quantity'], vals['uom'], vals['unit_price'],
                        vals['currency'], effective_date)
            if to_location.type != 'storage' \
                    and to_location.type != 'supplier' \
                    and product.cost_price_method == 'fifo':

                cost_price = self._update_fifo_out_product_cost_price(product,
                        vals['quantity'], vals['uom'], effective_date)
                if not vals.get('cost_price'):
                    vals['cost_price'] = cost_price

        return super(Move, self).create(vals)

    def write(self, ids, vals):
        date_obj = Pool().get('ir.date')

        if isinstance(ids, (int, long)):
            ids = [ids]
        today = date_obj.today()
        effective_date = vals.get('effective_date') or today

        if 'state' in vals and vals['state'] == 'done':
            for move in self.browse(ids):
                if vals['state'] == 'cancel':
                    if (move.from_location.type in ('supplier', 'production')
                            and move.to_location.type == 'storage'
                            and move.state != 'cancel'
                            and move.product.cost_price_method == 'fifo'):
                        self._update_product_cost_price(move.product.id,
                                -move.quantity, move.uom, move.unit_price,
                                move.currency, move.company, effective_date)
                    if (move.to_location.type == 'supplier'
                            and move.from_location.type == 'storage'
                            and move.state != 'cancel'
                            and move.product.cost_price_method == 'fifo'):
                        self._update_product_cost_price(move.product.id,
                                move.quantity, move.uom, move.unit_price,
                                move.currency, move.company, effective_date)

                elif vals['state'] == 'done':
                    if (move.from_location.type in ('supplier', 'production')
                            and move.to_location.type == 'storage'
                            and move.state != 'done'
                            and move.product.cost_price_method == 'fifo'):
                        self._update_product_cost_price(move.product.id,
                                move.quantity, move.uom, move.unit_price,
                                move.currency, move.company, effective_date)
                    if (move.to_location.type == 'supplier'
                            and move.from_location.type == 'storage'
                            and move.state != 'done'
                            and move.product.cost_price_method == 'fifo'):
                        self._update_product_cost_price(move.product.id,
                                -move.quantity, move.uom, move.unit_price,
                                move.currency, move.company, effective_date)
                    if move.to_location.type != 'storage' \
                            and move.to_location.type != 'supplier' \
                            and move.product.cost_price_method == 'fifo':
                        cost_price = self._update_fifo_out_product_cost_price(
                                move.product, move.quantity, move.uom,
                                effective_date)
                        if not vals.get('cost_price'):
                            vals['cost_price'] = cost_price
        return super(Move, self).write(ids, vals)

    def delete(self, ids):
        if self.search([
            ('id', 'in', ids),
            ('fifo_quantity', '!=', 0.0),
            ]):
            self.raise_user_error('del_move_fifo')
        return super(Move, self).delete(ids)
Move()

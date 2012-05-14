#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, ModelView, ModelSQL, Workflow, fields
from trytond.pyson import Eval
from trytond.pool import Pool


class Lot(ModelSQL, ModelView):
    "Stock Lot"
    _name = 'stock.lot'
    _description = __doc__
    _rec_name = 'number'

    number = fields.Char('Number', required=True, select=True)
    product = fields.Many2One('product.product', 'Product', required=True)

Lot()


class LotType(ModelSQL, ModelView):
    "Stock Lot Type"
    _name = 'stock.lot.type'
    _description = __doc__

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)

LotType()


class Move(Model):
    _name = 'stock.move'

    lot = fields.Many2One('stock.lot', 'Lot',
        domain=[
            ('product', '=', Eval('product')),
            ],
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state', 'product'])

    def __init__(self):
        super(Move, self).__init__()
        self._error_messages.update({
                'lot_required': 'Lot is required for move of product "%s"!',
                })

    def check_lot(self, ids):
        "Check if lot is required"
        pool = Pool()
        product_obj = pool.get('product.product')
        for move in self.browse(ids):
            if (move.state == 'done'
                    and not move.lot
                    and product_obj.lot_is_required(move.product,
                        move.from_location, move.to_location)):
                self.raise_user_error('lot_required', (move.product.rec_name,))

    def create(self, values):
        new_id = super(Move, self).create(values)
        self.check_lot([new_id])
        return new_id

    def write(self, ids, values):
        result = super(Move, self).write(ids, values)
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check_lot(ids)
        return result

Move()


class ShipmentIn(Model):
    _name = 'stock.shipment.in'

    def _get_inventory_moves(self, incoming_move):
        result = super(ShipmentIn, self)._get_inventory_moves(incoming_move)
        if result:
            result['lot'] = incoming_move.lot.id
        return result

ShipmentIn()


class ShipmentOut(Model):
    _name = 'stock.shipment.out'

    @ModelView.button
    @Workflow.transition('packed')
    def pack(self, ids):
        pool = Pool()
        uom_obj = pool.get('product.uom')
        move_obj = pool.get('stock.move')

        super(ShipmentOut, self).pack(ids)

        shipments = self.browse(ids)

        # Unassign move to allow update
        move_obj.write([m.id for s in shipments for m in s.outgoing_moves
                if m.state not in ('done', 'cancel')], {
                'state': 'draft',
                })

        for shipment in shipments:
            outgoing_by_product = {}
            for move in shipment.outgoing_moves:
                outgoing_by_product.setdefault(move.product.id,
                    []).append(move)
            for move in shipment.inventory_moves:
                if not move.lot:
                    continue
                quantity = uom_obj.compute_qty(move.uom, move.quantity,
                    move.product.default_uom, round=False)
                outgoing_moves = outgoing_by_product[move.product.id]
                while outgoing_moves and quantity > 0:
                    out_move = outgoing_moves.pop()
                    out_quantity = uom_obj.compute_qty(out_move.uom,
                        out_move.quantity, out_move.product.default_uom,
                        round=False)
                    if quantity < out_quantity:
                        outgoing_moves.append(move_obj.browse(
                                move_obj.copy(out_move.id, default={
                                        'quantity': out_quantity - quantity,
                                        })))
                        move_obj.write(out_move.id, {
                                'quantity': quantity,
                                })
                    move_obj.write(out_move.id, {
                            'lot': move.lot.id,
                            })
                    quantity -= out_quantity
                assert quantity <= 0

        # Reset function field cache
        shipments = self.browse(ids)

        move_obj.write([m.id for s in shipments for m in s.outgoing_moves
                if m.state != 'cancel'], {
                'state': 'assigned',
                })

ShipmentOut()


class ShipmentOutReturn(Model):
    _name = 'stock.shipment.out.return'

    def _get_inventory_moves(self, incoming_move):
        result = super(ShipmentOutReturn,
            self)._get_inventory_moves(incoming_move)
        if result:
            result['lot'] = incoming_move.lot.id
        return result

ShipmentOutReturn()

#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta

__all__ = ['Lot', 'LotType', 'Move', 'ShipmentIn', 'ShipmentOut',
    'ShipmentOutReturn']
__metaclass__ = PoolMeta


class Lot(ModelSQL, ModelView):
    "Stock Lot"
    __name__ = 'stock.lot'
    _rec_name = 'number'
    number = fields.Char('Number', required=True, select=True)
    product = fields.Many2One('product.product', 'Product', required=True)


class LotType(ModelSQL, ModelView):
    "Stock Lot Type"
    __name__ = 'stock.lot.type'
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)


class Move:
    __name__ = 'stock.move'
    lot = fields.Many2One('stock.lot', 'Lot',
        domain=[
            ('product', '=', Eval('product')),
            ],
        states={
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends=['state', 'product'])

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._error_messages.update({
                'lot_required': 'Lot is required for move of product "%s".',
                })

    @classmethod
    def check_lot(cls, moves):
        "Check if lot is required"
        for move in moves:
            if (move.state == 'done'
                    and move.internal_quantity
                    and not move.lot
                    and move.product.lot_is_required(
                        move.from_location, move.to_location)):
                cls.raise_user_error('lot_required', (move.product.rec_name,))

    @classmethod
    def create(cls, vlist):
        moves = super(Move, cls).create(vlist)
        cls.check_lot(moves)
        return moves

    @classmethod
    def write(cls, moves, values):
        super(Move, cls).write(moves, values)
        cls.check_lot(moves)


class ShipmentIn:
    __name__ = 'stock.shipment.in'

    @classmethod
    def _get_inventory_moves(cls, incoming_move):
        move = super(ShipmentIn, cls)._get_inventory_moves(incoming_move)
        if move and incoming_move.lot:
            move.lot = incoming_move.lot
        return move


class ShipmentOut:
    __name__ = 'stock.shipment.out'

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        pool = Pool()
        Uom = pool.get('product.uom')
        Move = pool.get('stock.move')

        super(ShipmentOut, cls).pack(shipments)

        # Unassign move to allow update
        Move.draft([m for s in shipments for m in s.outgoing_moves])

        for shipment in shipments:
            outgoing_by_product = {}
            for move in shipment.outgoing_moves:
                outgoing_by_product.setdefault(move.product.id,
                    []).append(move)
            for move in shipment.inventory_moves:
                if not move.lot:
                    continue
                quantity = Uom.compute_qty(move.uom, move.quantity,
                    move.product.default_uom, round=False)
                outgoing_moves = outgoing_by_product[move.product.id]
                while outgoing_moves and quantity > 0:
                    out_move = outgoing_moves.pop()
                    out_quantity = Uom.compute_qty(out_move.uom,
                        out_move.quantity, out_move.product.default_uom,
                        round=False)
                    if quantity < out_quantity:
                        outgoing_moves.extend(Move.copy([out_move], default={
                                    'quantity': out_quantity - quantity,
                                    }))
                        Move.write([out_move], {
                                'quantity': quantity,
                                })
                    Move.write([out_move], {
                            'lot': move.lot.id,
                            })
                    quantity -= out_quantity
                assert quantity <= 0

        Move.assign([m for s in shipments for m in s.outgoing_moves])


class ShipmentOutReturn:
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def _get_inventory_moves(cls, incoming_move):
        move = super(ShipmentOutReturn,
            cls)._get_inventory_moves(incoming_move)
        if move and incoming_move.lot:
            move.lot = incoming_move.lot
        return move

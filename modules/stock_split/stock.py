# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._buttons.update({
                'split_wizard': {
                    'readonly': ~Eval('state').in_(['draft', 'assigned']),
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button_action('stock_split.wizard_split_move')
    def split_wizard(cls, moves):
        pass

    def split(self, quantity, uom, count=None):
        """
        Split the move into moves of quantity.
        If count is not defined, the move will be split until the remainder is
        less than quantity.
        Return the split moves
        """
        pool = Pool()
        Uom = pool.get('product.uom')

        moves = [self]
        remainder = Uom.compute_qty(self.uom, self.quantity, uom)
        if remainder <= quantity:
            return moves
        state = self.state
        self.write([self], {
                'state': 'draft',
                })
        self.write([self], {
                'quantity': quantity,
                'uom': uom.id,
                })
        remainder -= quantity
        if count:
            count -= 1
        while (remainder > quantity
                and (count or count is None)):
            with Transaction().set_context(_stock_move_split=True):
                moves.extend(self.copy([self], {
                            'quantity': quantity,
                            'uom': uom.id,
                            }))
            remainder -= quantity
            if count:
                count -= 1
        remainder = uom.round(remainder)
        assert remainder >= 0
        if remainder:
            with Transaction().set_context(_stock_move_split=True):
                moves.extend(self.copy([self], {
                            'quantity': remainder,
                            'uom': uom.id,
                        }))
        self.write(moves, {
                'state': state,
                })
        return moves


class SplitMoveStart(ModelView):
    'Split Move'
    __name__ = 'stock.move.split.start'
    count = fields.Integer('Counts', help='The limit number of moves.')
    quantity = fields.Float("Quantity", digits='uom', required=True)
    uom = fields.Many2One('product.uom', 'Uom', required=True,
        domain=[
            ('category', '=', Eval('uom_category')),
            ])
    uom_category = fields.Many2One('product.uom.category', 'Uom Category',
        readonly=True)


class SplitMove(Wizard):
    'Split Move'
    __name__ = 'stock.move.split'
    start = StateView('stock.move.split.start',
        'stock_split.split_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Split', 'split', 'tryton-ok', default=True),
            ])
    split = StateTransition()

    def default_start(self, fields):
        return {
            'uom': self.record.uom.id,
            'uom_category': self.record.uom.category.id,
            }

    def transition_split(self):
        self.record.split(
            self.start.quantity, self.start.uom, self.start.count)
        return 'end'


class _ShipmentSplit(ModelView):

    @classmethod
    def __setup__(cls):
        super(_ShipmentSplit, cls).__setup__()
        cls._buttons.update({
                'split_wizard': {
                    'readonly': Eval('state') != 'draft',
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button_action('stock_split.wizard_split_shipment')
    def split_wizard(cls, shipments):
        pass


class ShipmentInReturn(_ShipmentSplit, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class ShipmentOut(_ShipmentSplit, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentInternal(_ShipmentSplit, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'


class SplitShipment(Wizard):
    "Split Shipment"
    __name__ = 'stock.shipment.split'
    start = StateView('stock.shipment.split.start',
        'stock_split.shipment_split_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Split", 'split', 'tryton-ok', default=True),
            ])
    split = StateTransition()

    def get_moves(self, shipment):
        if shipment.__name__ == 'stock.shipment.out':
            return shipment.outgoing_moves
        elif shipment.__name__ in {
                'stock.shipment.in.return',
                'stock.shipment.internal',
                }:
            return shipment.moves

    def default_start(self, fields):
        moves = self.get_moves(self.record)
        move_ids = [m.id for m in moves if m.state == 'draft']
        return {
            'domain_moves': move_ids,
            }

    def transition_split(self):
        pool = Pool()
        Move = pool.get('stock.move')
        shipment = self.record
        Shipment = self.model
        if shipment.state != 'draft':
            raise ValueError("Wrong shipment state")
        if not set(self.start.moves).issubset(self.start.domain_moves):
            raise ValueError("Invalid moves, %s != %s" % (self.start.moves,
                    self.start.domain_moves))

        if Shipment.__name__ == 'stock.shipment.out':
            Move.draft(shipment.inventory_moves)
            Move.delete(
                [m for m in shipment.inventory_moves if m.state == 'draft'])

        shipment, = Shipment.copy([shipment], default={'moves': None})
        Move.write(list(self.start.moves), {'shipment': str(shipment)})
        return 'end'


class SplitShipmentStart(ModelView):
    "Split Shipment"
    __name__ = 'stock.shipment.split.start'
    moves = fields.Many2Many(
        'stock.move', None, None, "Moves",
        domain=[('id', 'in', Eval('domain_moves'))],
        help="The selected moves will be sent in the new shipment.")
    domain_moves = fields.Many2Many('stock.move', None, None, "Domain Moves")

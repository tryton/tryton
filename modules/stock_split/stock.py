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
        super().__setup__()
        cls._buttons.update({
                'split_wizard': {
                    'readonly': ~Eval('state').in_(['draft', 'assigned']),
                    'depends': ['state'],
                    },
                'unsplit': {
                    'readonly': ~Eval('state').in_(['draft', 'assigned']),
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button_action('stock_split.wizard_split_move')
    def split_wizard(cls, moves):
        pass

    def split(self, quantity, unit, count=None):
        """
        Split the move into moves of quantity.
        If count is not defined, the move will be split until the remainder is
        less than quantity.
        Return the split moves
        """
        pool = Pool()
        Uom = pool.get('product.uom')

        moves = [self]
        remainder = Uom.compute_qty(self.unit, self.quantity, unit)
        if remainder <= quantity:
            return moves
        state = self.state
        self.write([self], {
                'state': 'draft',
                })
        self.write([self], {
                'quantity': quantity,
                'unit': unit.id,
                })
        remainder -= quantity
        if count:
            count -= 1
        while (remainder > quantity
                and (count or count is None)):
            with Transaction().set_context(_stock_move_split=True):
                moves.extend(self.copy([self], {
                            'quantity': quantity,
                            'unit': unit.id,
                            }))
            remainder -= quantity
            if count:
                count -= 1
        remainder = unit.round(remainder)
        assert remainder >= 0
        if remainder:
            with Transaction().set_context(_stock_move_split=True):
                moves.extend(self.copy([self], {
                            'quantity': remainder,
                            'unit': unit.id,
                        }))
        self.write(moves, {
                'state': state,
                })
        return moves

    @classmethod
    @ModelView.button
    def unsplit(cls, moves, _exclude=None):
        pool = Pool()
        UoM = pool.get('product.uom')

        _exclude = _exclude.copy() if _exclude is not None else set()
        _exclude.update({
                'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
                'quantity', 'unit', 'internal_quantity'})

        fields_names = {
            name for name, field in cls._fields.items()
            if not isinstance(field, (fields.Function, fields.MultiValue))}
        fields_names -= _exclude
        values = cls.read([m.id for m in moves], fields_names=fields_names)
        id2values = {v.pop('id'): v for v in values}

        groups = []
        for move in moves:
            for group in groups:
                if id2values[move.id] == id2values[group[0].id]:
                    group.append(move)
                    break
            else:
                groups.append([move])

        def unit_precision(unit):
            return unit.factor * unit.rounding

        to_save, to_clear = [], []
        for group in groups:
            if len(group) <= 1:
                continue
            quantity = sum(m.internal_quantity for m in group)
            unit = min((m.unit for m in group), key=unit_precision)
            move, *others = group
            move.quantity = UoM.compute_qty(
                move.product.default_uom, quantity, unit)
            move.unit = unit
            to_save.append(move)
            to_clear.extend(others)
        cls.write(to_clear, {'quantity': 0})
        cls.save(to_save)


class SplitMoveStart(ModelView):
    __name__ = 'stock.move.split.start'
    count = fields.Integer('Counts', help='The limit number of moves.')
    quantity = fields.Float("Quantity", digits='unit', required=True)
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        domain=[
            ('category', '=', Eval('uom_category', -1)),
            ])
    uom_category = fields.Many2One(
        'product.uom.category', "UoM Category", readonly=True,
        help="The category of Unit of Measure.")


class SplitMove(Wizard):
    __name__ = 'stock.move.split'
    start = StateView('stock.move.split.start',
        'stock_split.split_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Split', 'split', 'tryton-ok', default=True),
            ])
    split = StateTransition()

    def default_start(self, fields):
        return {
            'unit': self.record.unit.id,
            'uom_category': self.record.unit.category.id,
            }

    def transition_split(self):
        self.record.split(
            self.start.quantity, self.start.unit, self.start.count)
        return 'end'


class _ShipmentSplit(ModelView):

    @classmethod
    def __setup__(cls):
        super().__setup__()
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
    __name__ = 'stock.shipment.split.start'
    moves = fields.Many2Many(
        'stock.move', None, None, "Moves",
        domain=[('id', 'in', Eval('domain_moves'))],
        help="The selected moves will be sent in the new shipment.")
    domain_moves = fields.Many2Many('stock.move', None, None, "Domain Moves")

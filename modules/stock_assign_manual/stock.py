# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json

from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import Model, ModelStorage, ModelView, dualmethod, fields
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


class ShipmentUnassignMixin:
    '''Mixin to unassign quantity from assigned shipment moves'''
    __slots__ = ()

    @dualmethod
    def unassign(cls, shipments, moves, quantities):
        '''
        Unassign the quantity from the corresponding move of the shipments.
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        to_unassign = []
        if not all(m.state == 'assigned' for m in moves):
            raise ValueError("Not assigned move")
        Move.draft(moves)
        for move, unassign_quantity in zip(moves, quantities):
            if not unassign_quantity:
                continue
            if unassign_quantity > move.quantity:
                raise ValueError(
                    "Unassigned quantity greater than move quantity")
            if unassign_quantity == move.quantity:
                to_unassign.append(move)
            else:
                with Transaction().set_context(_stock_move_split=True):
                    to_unassign.extend(Move.copy(
                            [move],
                            {'quantity': unassign_quantity}))
                move.quantity -= unassign_quantity
        Move.save(moves)
        Move.assign(moves)
        if to_unassign:
            cls.wait(shipments, to_unassign)


class ShipmentInReturn(ShipmentUnassignMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'assign_manual_wizard': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button_action(
        'stock_assign_manual.wizard_shipment_in_return_assign_manual')
    def assign_manual_wizard(cls, shipments):
        pass


class ShipmentOut(ShipmentUnassignMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'assign_manual_wizard': {
                    'invisible': ((Eval('state') != 'waiting')
                        | (Eval('warehouse_storage')
                            == Eval('warehouse_output'))),
                    'depends': [
                        'state', 'warehouse_storage', 'warehouse_output'],
                    },
                })

    @classmethod
    @ModelView.button_action(
        'stock_assign_manual.wizard_shipment_out_assign_manual')
    def assign_manual_wizard(cls, shipments):
        pass


class ShipmentInternal(ShipmentUnassignMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'assign_manual_wizard': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button_action(
        'stock_assign_manual.wizard_shipment_internal_assign_manual')
    def assign_manual_wizard(cls, shipments):
        pass


class ShipmentAssignManual(Wizard):
    "Manual Assign Shipment"
    __name__ = 'stock.shipment.assign.manual'
    start_state = 'next_'
    next_ = StateTransition()
    show = StateView('stock.shipment.assign.manual.show',
        'stock_assign_manual.shipment_assign_manual_show_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Skip", 'skip', 'tryton-forward', validate=False),
            Button("Assign", 'assign', 'tryton-ok', default=True),
            ])
    skip = StateTransition()
    assign = StateTransition()

    def transition_next_(self):

        def next_move():
            for move in self.record.assign_moves:
                if move.state == 'draft' and move not in self.show.skipped:
                    self.show.move = move
                    return move

        if getattr(self.show, 'skipped', None) is None:
            self.show.skipped = []

        if not next_move():
            if all(m.state == 'assigned' for m in self.record.assign_moves):
                self.model.assign([self.record])
            return 'end'
        return 'show'

    def default_show(self, fields):
        defaults = {}
        if 'skipped' in fields:
            defaults['skipped'] = [m.id for m in self.show.skipped]
        if 'move' in fields:
            defaults['move'] = self.show.move.id
        if 'unit' in fields:
            defaults['unit'] = self.show.move.uom.id
        if 'move_quantity' in fields:
            defaults['move_quantity'] = self.show.move.quantity
        return defaults

    def transition_skip(self):
        moves = list(self.show.skipped)
        moves.append(self.show.move)
        self.show.skipped = moves
        return 'next_'

    def transition_assign(self):
        self.show.assign()
        return 'next_'


class ShipmentAssignManualShow(ModelView):
    "Manual Assign Shipment"
    __name__ = 'stock.shipment.assign.manual.show'

    skipped = fields.Many2Many(
        'stock.move', None, None, "Skipped", readonly=True)
    move = fields.Many2One('stock.move', "Move", readonly=True)
    quantity = fields.Float(
        "Quantity", digits='unit',
        domain=['OR',
            ('quantity', '=', None),
            [
                ('quantity', '>', 0),
                ('quantity', '<=', Eval('move_quantity', 0)),
                ],
            ],
        help="The maximum quantity to assign from the place.\n"
        "Leave empty for the full quantity of the move.")
    unit = fields.Many2One('product.uom', "Unit", readonly=True)
    move_quantity = fields.Float("Move Quantity", readonly=True)
    place = fields.Selection('get_places', "Place", required=True, sort=False)
    place_string = place.translated('place')

    @fields.depends('move')
    def get_places(self, with_childs=True, grouping=('product',)):
        pool = Pool()
        Date = pool.get('ir.date')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Lang = pool.get('ir.lang')
        lang = Lang.get()

        if not self.move:
            return []

        if with_childs:
            locations = Location.search([
                    ('parent', 'child_of', [self.move.from_location.id]),
                    ])
        else:
            locations = [self.move.from_location]

        location_ids = [loc.id for loc in locations]
        product_ids = [self.move.product.id]
        with Transaction().set_context(company=self.move.company.id):
            stock_date_end = Date.today()
        with Transaction().set_context(
                stock_date_end=stock_date_end,
                stock_assign=True,
                forecast=False,
                company=self.move.company.id):
            pbl = Product.products_by_location(
                location_ids, with_childs=False,
                grouping=grouping, grouping_filter=(product_ids,))

        def get_key(move, location_id):
            key = (location_id,)
            for field in grouping:
                value = getattr(move, field)
                if isinstance(value, Model):
                    value = value.id
                key += (value,)
            return key

        def match(key, pattern):
            for k, p in zip(key, pattern):
                if p is None or k == p:
                    continue
                else:
                    return False
            else:
                return True

        def get_name(key):
            move = Move()
            parts = [Location(key[0]).rec_name]
            for field, value in zip(grouping, key[1:]):
                setattr(move, field, value)
                value = getattr(move, field)
                if isinstance(value, ModelStorage):
                    parts.append(value.rec_name)
                elif value:
                    parts.append(str(value))
            return ' - '.join(parts)

        # Prevent picking from the destination location
        try:
            locations.remove(self.move.to_location)
        except ValueError:
            pass
        # Try first to pick from source location
        locations.remove(self.move.from_location)
        locations.insert(0, self.move.from_location)
        places = [(None, '')]
        quantities = self.move.sort_quantities(
            pbl.items(), locations, grouping)
        for key, qty in quantities:
            move_key = get_key(self.move, key[0])
            if qty > 0 and match(key, move_key):
                uom = self.move.product.default_uom
                quantity = lang.format_number_symbol(
                    pbl[key], uom, digits=uom.digits)
                name = '%(name)s (%(quantity)s)' % {
                    'name': get_name(key),
                    'quantity': quantity
                    }
                places.append((json.dumps(key), name))
        return places

    def assign(self, grouping=('product',)):
        pool = Pool()
        Move = pool.get('stock.move')
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        if self.quantity is not None:
            if not (0 <= self.quantity <= self.move.quantity):
                uom = self.move.product.default_uom
                raise ValidationError(gettext(
                        'stock_assign_manual.msg_invalid_quantity',
                        quantity=lang.format_number(
                            self.move_quantity, uom.digits)))
            quantity = self.move.uom.round(self.quantity)
            remainder = self.move.uom.round(self.move.quantity - quantity)
            self.move.quantity = quantity
            self.move.save()
            if remainder:
                Move.copy([self.move], {'quantity': remainder})
        key = json.loads(self.place)
        values = self._apply(key, grouping)
        quantity = self.move.quantity
        Move.assign_try([self.move], with_childs=False, grouping=grouping)
        if self.move.state != 'assigned':
            # Restore initial values as assign_try may have saved the move
            for field, value in values.items():
                setattr(self.move, field, value)
            self.move.save()
            if self.move.quantity == quantity:
                raise UserError(gettext(
                        'stock_assign_manual.msg_assign_failed',
                        move=self.move.rec_name,
                        place=self.place_string))

    def _apply(self, key, grouping):
        """Update the move according to the key
        and return a dictionary with the initial values."""
        values = {'from_location': self.move.from_location.id}
        location_id = key[0]
        self.move.from_location = location_id
        for field, value in zip(grouping, key[1:]):
            if value is not None and '.' not in field:
                values[field] = getattr(self.move, field)
                setattr(self.move, field, value)
        return values


class ShipmentUnassignManual(Wizard):
    "Manual Unassign Shipment"
    __name__ = 'stock.shipment.unassign.manual'
    start = StateTransition()
    show = StateView('stock.shipment.unassign.manual.show',
        'stock_assign_manual.shipment_unassign_manual_show_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Unassign", 'unassign', 'tryton-ok', default=True),
            ])
    unassign = StateTransition()

    def transition_start(self):
        moves = self.record.assign_moves
        if any(m.state == 'assigned' for m in moves):
            return 'show'
        return 'end'

    def default_show(self, fields):
        moves = self.record.assign_moves
        move_ids = [m.id for m in moves if m.state == 'assigned']
        return {
            'assigned_moves': move_ids,
            }

    def transition_unassign(self):
        moves = []
        quantities = []
        for m in self.show.moves:
            moves.append(m.move)
            quantities.append(m.unassigned_quantity)
        self.record.unassign(moves, quantities)
        return 'end'


class ShipmentAssignedMove(ModelView):
    "Shipment Assigned Move"
    __name__ = 'stock.shipment.assigned.move'

    move = fields.Many2One('stock.move', "Move", required=True)
    unassigned_quantity = fields.Float(
        "Unassigned Quantity", digits='unit',
        domain=['OR',
            ('unassigned_quantity', '=', None),
            [
                ('unassigned_quantity', '>=', 0),
                ('unassigned_quantity', '<=', Eval('move_quantity', 0)),
                ],
            ],
        help="The quantity to unassign")
    assigned_quantity = fields.Float(
        "Assigned Quantity", digits='unit',
        domain=['OR',
            ('assigned_quantity', '=', None),
            [
                ('assigned_quantity', '>=', 0),
                ('assigned_quantity', '<=', Eval('move_quantity', 0)),
                ],
            ],
        help="The quantity left assigned")
    unit = fields.Function(
        fields.Many2One('product.uom', "Unit"), 'on_change_with_unit')
    move_quantity = fields.Function(
        fields.Float("Move Quantity"), 'on_change_with_move_quantity')

    @staticmethod
    def default_unassigned_quantity():
        return 0.0

    @fields.depends('move', 'unassigned_quantity', 'assigned_quantity')
    def on_change_move(self, name=None):
        if self.move:
            self.assigned_quantity = self.move.quantity
            self.unassigned_quantity = 0.0

    @fields.depends('assigned_quantity', 'move', 'unassigned_quantity', 'unit')
    def on_change_unassigned_quantity(self, name=None):
        if self.move and self.unassigned_quantity:
            self.assigned_quantity = self.unit.round(
                self.move.quantity - self.unassigned_quantity)

    @fields.depends('unassigned_quantity', 'move', 'assigned_quantity', 'unit')
    def on_change_assigned_quantity(self, name=None):
        if self.move and self.assigned_quantity:
            self.unassigned_quantity = self.unit.round(
                self.move.quantity - self.assigned_quantity)

    @fields.depends('move')
    def on_change_with_unit(self, name=None):
        if self.move:
            return self.move.uom.id

    @fields.depends('move')
    def on_change_with_move_quantity(self, name=None):
        if self.move:
            return self.move.quantity


class ShipmentUnassignManualShow(ModelView):
    "Manually Unassign Shipment"
    __name__ = 'stock.shipment.unassign.manual.show'

    moves = fields.One2Many(
        'stock.shipment.assigned.move', None, "Moves",
        domain=[('move.id', 'in', Eval('assigned_moves'))],
        help="The moves to unassign.")
    assigned_moves = fields.Many2Many(
        'stock.move', None, None, "Assigned Moves")

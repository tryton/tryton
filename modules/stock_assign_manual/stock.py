# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json

from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import Model, ModelStorage, ModelView, fields
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button


class ShipmentInReturn(metaclass=PoolMeta):
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


class ShipmentOut(metaclass=PoolMeta):
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


class ShipmentInternal(metaclass=PoolMeta):
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
        if 'unit_digits' in fields:
            defaults['unit_digits'] = self.show.move.unit_digits
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
        "Quantity", digits=(16, Eval('unit_digits', 2)),
        domain=['OR',
            ('quantity', '=', None),
            [
                ('quantity', '>', 0),
                ('quantity', '<=', Eval('move_quantity', 0)),
                ],
            ],
        depends=['unit_digits', 'move_quantity'],
        help="The maximum quantity to assign from the place.\n"
        "Leave empty for the full quantity of the move.")
    unit = fields.Many2One('product.uom', "Unit", readonly=True)
    unit_digits = fields.Integer("Unit Digits", readonly=True)
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
        index = {l.id: i for i, l in enumerate(locations)}
        places = [(None, '')]
        pbl_items = pbl.items()
        pbl_items = filter(lambda x: x[0][0] in index, pbl_items)
        pbl_items = sorted(pbl_items, key=lambda x: index[x[0][0]])
        for key, qty in pbl_items:
            move_key = get_key(self.move, key[0])
            if qty > 0 and match(key, move_key):
                uom = self.move.product.default_uom
                quantity = lang.format('%.*f', (uom.digits, pbl[key]))
                name = '%(name)s (%(quantity)s%(unit)s)' % {
                    'name': get_name(key),
                    'quantity': quantity,
                    'unit': uom.symbol,
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
                        quantity=lang.format(
                            '%.*f', (uom.digits, self.move.quantity))))
            quantity = self.move.uom.round(self.quantity)
            remainder = self.move.uom.round(self.move.quantity - quantity)
            self.move.quantity = quantity
            self.move.save()
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

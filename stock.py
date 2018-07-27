# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.model import ModelView, Workflow, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

__all__ = [
    'Lot', 'Move', 'Inventory', 'InventoryCount',
    'ShipmentIn', 'ShipmentInReturn',
    'ShipmentOut', 'ShipmentOutReturn',
    'Production',
    ]


class Lot(metaclass=PoolMeta):
    __name__ = 'stock.lot'

    unit = fields.Many2One(
        'product.uom', "Unit",
        domain=[
            ('category', '=', Eval('product_default_uom_category', -1)),
            ],
        depends=['product_default_uom_category'],
        help="The biggest unit for the lot.")
    unit_quantity = fields.Float(
        "Quantity", digits=(16, Eval('unit_digits', 2)),
        states={
            'required': Bool(Eval('unit')),
            'invisible': ~Eval('unit'),
            },
        depends=['unit', 'unit_digits'],
        help="The maximal quantity for the lot.")

    product_default_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Default Product UoM Category"),
        'on_change_with_product_default_uom_category')
    unit_digits = fields.Function(
        fields.Integer("Unit Digits"), 'on_change_with_unit_digits')

    @classmethod
    def __setup__(cls):
        super(Lot, cls).__setup__()
        cls._error_messages.update({
                'change_unit': ("You cannot change the unit of a lot "
                    "which is associated to done moves."),
                })
        cls._modify_no_move += [
            ('unit', 'done', 'change_unit'),
            ('unit_quantity', 'done', 'change_unit'),
            ]

    @fields.depends('product', methods=['on_change_unit'])
    def on_change_product(self):
        try:
            super(Lot, self).on_change_product()
        except AttributeError:
            pass
        if self.product and self.product.lot_unit:
            self.unit = self.product.lot_unit
            self.on_change_unit()

    @fields.depends('unit')
    def on_change_unit(self):
        if self.unit:
            self.unit_quantity = self.unit.rounding

    @fields.depends('product')
    def on_change_with_product_default_uom_category(self, name=None):
        if self.product:
            category = self.product.default_uom_category
            return category.id if category else None

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._error_messages.update({
                'lot_unit_quantity_greater': (
                    'The quantity in "%(name)s" of the lot "%(lot)s" '
                    'cannot be greater than %(quantity)s%(unit)s.'),
                })

    def check_lot(self):
        pool = Pool()
        UoM = pool.get('product.uom')
        super(Move, self).check_lot()
        if (self.state == 'done'
                and self.lot
                and self.lot.unit):
            quantity = UoM.compute_qty(
                self.uom, self.quantity,
                self.lot.unit, round=False)
            if quantity > self.lot.unit_quantity:
                self.raise_user_error('lot_unit_quantity_greater', {
                        'lot': self.lot.rec_name,
                        'name': self.rec_name,
                        'quantity': self.lot.unit_quantity,
                        'unit': self.lot.unit.symbol,
                        })


class Inventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def confirm(cls, inventories):
        pool = Pool()
        Move = pool.get('stock.move')
        for inventory in inventories:
            for line in inventory.lines:
                if (line.lot and line.lot.unit
                        and line.quantity > line.lot.unit_quantity):
                    Move.raise_user_error('lot_unit_quantity_greater', {
                            'lot': line.lot.rec_name,
                            'name': line.rec_name,
                            'quantity': line.lot.unit_quantity,
                            'unit': line.lot.unit.symbol,
                            })
        super(Inventory, cls).confirm(inventories)


class InventoryCount(metaclass=PoolMeta):
    __name__ = 'stock.inventory.count'

    def default_quantity(self, fields):
        pool = Pool()
        InventoryLine = pool.get('stock.inventory.line')
        UoM = pool.get('product.uom')
        values = super(InventoryCount, self).default_quantity(fields)
        line = InventoryLine(values['line'])
        if line.lot and line.lot.unit:
            values['quantity_added'] = UoM.compute_qty(
                line.lot.unit, line.lot.unit_quantity,
                line.uom)
        return values


class LotUnitMixin(object):
    _lot_unit_moves = None

    @classmethod
    def validate(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        UoM = pool.get('product.uom')

        super(LotUnitMixin, cls).validate(shipments)

        for shipment in shipments:
            for move_attribute in cls._lot_unit_moves:
                lot_quantities = defaultdict(lambda: 0)
                for move in getattr(shipment, move_attribute):
                    if move.state != 'done':
                        continue
                    if not move.lot or not move.lot.unit:
                        continue
                    lot_quantities[move.lot] += UoM.compute_qty(
                        move.uom, move.quantity,
                        move.lot.unit, round=False)
                for lot, quantity in lot_quantities.items():
                    if quantity > lot.unit_quantity:
                        Move.raise_user_error('lot_unit_quantity_greater', {
                                'lot': lot.rec_name,
                                'name': shipment.rec_name,
                                'quantity': lot.unit_quantity,
                                'unit': lot.unit.symbol,
                                })


class ShipmentIn(LotUnitMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'
    _lot_unit_moves = ['incoming_moves', 'inventory_moves']


class ShipmentInReturn(LotUnitMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'
    _lot_unit_moves = ['moves']


class ShipmentOut(LotUnitMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'
    _lot_unit_moves = ['outgoing_moves', 'inventory_moves']


class ShipmentOutReturn(LotUnitMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'
    _lot_unit_moves = ['incoming_moves', 'inventory_moves']


class ShipmentInternal(LotUnitMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'
    _lot_unit_moves = ['incoming_moves', 'outgoing_moves']


class Production(LotUnitMixin, metaclass=PoolMeta):
    __name__ = 'production'
    _lot_unit_moves = ['inputs', 'outputs']

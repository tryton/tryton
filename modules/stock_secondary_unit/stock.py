# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits, round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    secondary_quantity = fields.Function(fields.Float(
            "Secondary Quantity", digits='secondary_unit',
            states={
                'invisible': ~Eval('secondary_unit'),
                'readonly': Eval('state').in_(
                    ['cancelled', 'assigned', 'done']),
                }),
        'on_change_with_secondary_quantity', setter='set_secondary')
    secondary_unit = fields.Many2One(
        'product.uom', "Secondary Unit", ondelete='RESTRICT',
        domain=[
            ('category', '=', Eval('product_secondary_uom_category')),
            ],
        states={
            'invisible': ~Eval('product_secondary_uom_category'),
            'readonly': Eval('state').in_(['cancelled', 'assigned', 'done']),
            })
    secondary_unit_price = fields.Function(
        Monetary(
            "Secondary Unit Price", currency='currency', digits=price_digits,
            states={
                'invisible': (~Eval('unit_price_required')
                    | ~Eval('secondary_unit')),
                'readonly': Eval('state') != 'draft',
                }),
        'on_change_with_secondary_unit_price', setter='set_secondary')

    product_secondary_uom_category = fields.Function(
        fields.Many2One(
            'product.uom.category', "Product Secondary UOM Category"),
        'get_product_secondary_uom_category')

    @fields.depends('quantity', 'uom', 'secondary_unit', 'origin')
    def on_change_with_secondary_quantity(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.quantity and self.uom and self.secondary_unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            return Uom.compute_qty(
                self.uom, self.quantity,
                self.secondary_unit, round=True,
                factor=self.secondary_uom_factor, rate=self.secondary_uom_rate)
        else:
            return None

    @fields.depends('secondary_quantity', 'secondary_unit', 'uom', 'origin')
    def on_change_secondary_quantity(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.secondary_quantity and self.secondary_unit and self.uom
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            self.quantity = Uom.compute_qty(
                self.secondary_unit, self.secondary_quantity,
                self.uom, round=True,
                factor=self.secondary_uom_rate, rate=self.secondary_uom_factor)

    @fields.depends('unit_price', 'uom', 'secondary_unit', 'origin')
    def on_change_with_secondary_unit_price(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.unit_price and self.uom and self.secondary_unit
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            unit_price = Uom.compute_price(
                self.uom, self.unit_price, self.secondary_unit,
                factor=self.secondary_uom_factor, rate=self.secondary_uom_rate
                )
            return round_price(unit_price)
        else:
            return None

    @fields.depends('secondary_unit_price', 'secondary_unit', 'uom', 'origin')
    def on_change_secondary_unit_price(self, name=None):
        pool = Pool()
        Uom = pool.get('product.uom')
        if (self.secondary_unit_price and self.secondary_unit and self.uom
                and (self.secondary_uom_factor or self.secondary_uom_rate)):
            self.unit_price = Uom.compute_price(
                self.secondary_unit, self.secondary_unit_price, self.uom,
                factor=self.secondary_uom_rate, rate=self.secondary_uom_factor)
            self.unit_price = round_price(self.unit_price)

    @fields.depends(methods=[
            'on_change_secondary_quantity', 'on_change_secondary_unit_price'])
    def on_change_secondary_unit(self):
        self.on_change_secondary_quantity()
        self.on_change_secondary_unit_price()

    def get_product_secondary_uom_category(self, name):
        category = None
        if self.secondary_unit:
            # Stay valid even if origin has been deleted
            category = self.secondary_unit.category.id
        if isinstance(self.origin, self.__class__) and self.origin != self:
            if self.origin.product_secondary_uom_category:
                category = self.origin.product_secondary_uom_category.id
        return category

    @classmethod
    def set_secondary(cls, lines, name, value):
        pass

    @property
    def secondary_uom_factor(self):
        if isinstance(self.origin, self.__class__) and self.origin != self:
            return self.origin.secondary_uom_factor

    @property
    def secondary_uom_rate(self):
        if isinstance(self.origin, self.__class__) and self.origin != self:
            return self.origin.secondary_uom_rate


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move:
            move.secondary_unit = incoming_move.secondary_unit
        return move


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def _get_inventory_move(self, move):
        inventory_move = super()._get_inventory_move(move)
        if inventory_move:
            inventory_move.secondary_unit = move.secondary_unit
        return inventory_move


class ShipmentOutReturn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    def _get_inventory_move(self, incoming_move):
        move = super()._get_inventory_move(incoming_move)
        if move:
            move.secondary_unit = incoming_move.secondary_unit
        return move

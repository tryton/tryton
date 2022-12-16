# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = ['SaleLine']


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls._error_messages.update({
                'over_shipment': (
                    'The Sale Line "%s" exceed the over shipment tolerance.'),
                })

    def _test_under_shipment_tolerance(self, quantity):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        if quantity:
            config = Configuration(1)
            tolerance = config.sale_under_shipment_tolerance
            if tolerance is not None:
                minimal_quantity = abs(self.quantity * (1 - tolerance))
                minimal_quantity = self.unit.round(minimal_quantity)
                return quantity <= minimal_quantity
        return False

    @property
    def _move_remaining_quantity(self):
        quantity = super(SaleLine, self)._move_remaining_quantity
        if self._test_under_shipment_tolerance(quantity):
            return 0
        return quantity

    def get_move(self, shipment_type):
        pool = Pool()
        Uom = pool.get('product.uom')
        move = super(SaleLine, self).get_move(shipment_type)
        # Compute tolerance only if there is already at least one move.
        if move and set(self.moves) - set(self.moves_recreated):
            quantity = Uom.compute_qty(
                move.uom, move.quantity, self.unit, round=False)
            if self._test_under_shipment_tolerance(quantity):
                move = None
        return move

    def check_over_shipment(self):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        config = Configuration(1)

        if self.quantity >= 0:
            shipment_type = 'out'
        else:
            shipment_type = 'in'
        shipped_quantity = self._get_shipped_quantity(shipment_type)
        tolerance = config.sale_over_shipment_tolerance
        if tolerance is not None:
            maximal_quantity = abs(self.quantity * tolerance)
            if shipped_quantity > maximal_quantity:
                self.raise_user_warning(
                    'over_shipment_sale_line_%d' % self.id,
                    'over_shipment', self.rec_name)

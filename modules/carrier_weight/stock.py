#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import izip, groupby
from functools import partial

from trytond.model import Model
from trytond.pool import Pool


class ShipmentIn(Model):
    _name = 'stock.shipment.in'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return None

    def _get_carrier_context(self, values):
        pool = Pool()
        carrier_obj = pool.get('carrier')
        product_obj = pool.get('product.product')
        uom_obj = pool.get('product.uom')

        context = super(ShipmentIn, self)._get_carrier_context(values)
        if not values.get('carrier'):
            return context
        carrier = carrier_obj.browse(values['carrier'])
        if carrier.carrier_cost_method != 'weight':
            return context
        context = context.copy()
        weights = []
        context['weights'] = weights
        product_ids = [line['product']
            for line in values.get('incoming_moves') or []
            if line.get('product')]
        id2product = dict((p.id, p) for p in product_obj.browse(product_ids))
        uom_ids = [line['uom'] for line in values.get('incoming_moves') or []
            if line.get('uom')]
        id2uom = dict((u.id, u) for u in uom_obj.browse(uom_ids))

        lines = values.get('incoming_moves') or []
        keyfunc = partial(self._group_parcel_key, lines)
        lines = sorted(lines, key=keyfunc)

        for key, parcel in groupby(lines, key=keyfunc):
            weight = 0
            for line in parcel:
                if (line.get('product')
                        and line.get('quantity')
                        and line.get('uom')):
                    product = id2product[line['product']]
                    quantity = uom_obj.compute_qty(id2uom[line['uom']],
                        line['quantity'], product.default_uom, round=False)
                    weight += uom_obj.compute_qty(product.weight_uom,
                        product.weight * quantity, carrier.weight_uom,
                        round=False)
            weights.append(weight)
        return context

ShipmentIn()


class ShipmentOut(Model):
    _name = 'stock.shipment.out'

    def _group_parcel_key(self, lines, line):
        """
        The key to group lines by parcel
        """
        return None

    def _get_carrier_context(self, values):
        pool = Pool()
        carrier_obj = pool.get('carrier')
        product_obj = pool.get('product.product')
        uom_obj = pool.get('product.uom')

        context = super(ShipmentOut, self)._get_carrier_context(values)
        if not values.get('carrier'):
            return context
        carrier = carrier_obj.browse(values['carrier'])
        if carrier.carrier_cost_method != 'weight':
            return context
        context = context.copy()
        weights = []
        context['weights'] = weights
        product_ids = [line['product']
            for line in values.get('inventory_moves') or []
            if line.get('product')]
        id2product = dict((p.id, p) for p in product_obj.browse(product_ids))
        uom_ids = [line['uom'] for line in values.get('inventory_moves') or []
            if line.get('uom')]
        id2uom = dict((u.id, u) for u in uom_obj.browse(uom_ids))

        lines = values.get('inventory_moves') or []
        keyfunc = partial(self._group_parcel_key, lines)
        lines = sorted(lines, key=keyfunc)

        for key, parcel in groupby(lines, key=keyfunc):
            weight = 0
            for line in parcel:
                if (line.get('product')
                        and line.get('quantity')
                        and line.get('uom')):
                    product = id2product[line['product']]
                    quantity = uom_obj.compute_qty(id2uom[line['uom']],
                        line['quantity'], product.default_uom, round=False)
                    weight += uom_obj.compute_qty(product.weight_uom,
                        product.weight * quantity, carrier.weight_uom,
                        round=False)
            weights.append(weight)
        return context

    def get_carrier_context(self, shipment, values=None):
        if values is None:
            values = {}
        values = values.copy()
        inventory_moves = [{
                'product': m.product.id,
                'quantity': m.quantity,
                'uom': m.uom.id,
                } for m in shipment.inventory_moves]
        values.setdefault('inventory_moves', inventory_moves)
        for new, old in izip(inventory_moves, values['inventory_moves']):
            old.update(new)
        return super(ShipmentOut, self).get_carrier_context(shipment,
            values=values)

ShipmentOut()

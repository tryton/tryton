#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from functools import partial
from itertools import groupby

from trytond.model import Model
from trytond.pool import Pool


class Sale(Model):
    _name = 'sale.sale'

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

        context = super(Sale, self)._get_carrier_context(values)

        carrier = carrier_obj.browse(values['carrier'])
        if carrier.carrier_cost_method != 'weight':
            return context
        context = context.copy()
        weights = []
        context['weights'] = weights
        product_ids = [line['product'] for line in values.get('lines') or []
            if line.get('product')]
        id2product = dict((p.id, p) for p in product_obj.browse(product_ids))
        unit_ids = [line['unit'] for line in values.get('lines') or []
            if line.get('unit')]
        id2unit = dict((u.id, u) for u in uom_obj.browse(unit_ids))

        lines = values.get('lines') or []
        keyfunc = partial(self._group_parcel_key, lines)
        lines = sorted(lines, key=keyfunc)

        for key, parcel in groupby(lines, key=keyfunc):
            weight = 0
            for line in parcel:
                if (line.get('product')
                        and line.get('quantity')
                        and line.get('unit')):
                    product = id2product[line['product']]
                    quantity = uom_obj.compute_qty(id2unit[line['unit']],
                        line['quantity'], product.default_uom, round=False)
                    if product.weight:
                        weight += uom_obj.compute_qty(product.weight_uom,
                            product.weight * quantity, carrier.weight_uom,
                            round=False)
            weights.append(weight)
        return context

Sale()

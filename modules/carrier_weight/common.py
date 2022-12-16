# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool


def parcel_weight(parcel, carrier_uom, uom_field='uom'):
    pool = Pool()
    Uom = pool.get('product.uom')

    weight = 0
    for line in parcel:
        product = getattr(line, 'product', None)
        quantity = getattr(line, 'quantity', None)
        uom = getattr(line, uom_field, None)

        if not all([product, quantity, uom]):
            continue

        if product.weight is not None:
            internal_quantity = Uom.compute_qty(
                uom, quantity, product.default_uom, round=False)
            weight += Uom.compute_qty(
                product.weight_uom, internal_quantity * product.weight,
                carrier_uom, round=False)
        elif uom.category == carrier_uom.category:
            weight += Uom.compute_qty(uom, quantity, carrier_uom, round=False)
    return weight

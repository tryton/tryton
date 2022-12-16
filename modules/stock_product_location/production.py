# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    def _explode_move_values(
            self, from_location, to_location, company, bom_io, quantity):
        pool = Pool()
        ProductionBomOutput = pool.get('production.bom.output')
        move = super(Production, self)._explode_move_values(
            from_location, to_location, company, bom_io, quantity)
        if move and isinstance(bom_io, ProductionBomOutput):
            for product_location in bom_io.product.locations:
                if product_location.warehouse != to_location.warehouse:
                    continue
                move.to_location = product_location.location
        return move

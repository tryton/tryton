# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import random

from proteus import Model


def setup(config, activated, company, suppliers):
    ShipmentIn = Model.get('stock.shipment.in')
    ShipmentOut = Model.get('stock.shipment.out')

    for supplier in suppliers:
        shipment = ShipmentIn()
        shipment.supplier = supplier
        all_moves = shipment.incoming_moves.find()
        moves = random.sample(all_moves, len(all_moves) * 2 // 3)
        while moves:
            shipment = ShipmentIn()
            shipment.supplier = supplier
            for _ in range(random.randint(1, len(moves))):
                move = moves.pop()
                shipment.incoming_moves.append(move)
            shipment.click('receive')
            shipment.click('do')

    shipments = ShipmentOut.find([('state', '=', 'waiting')])
    for shipment in shipments:
        if shipment.click('assign_try'):
            shipment.click('pick')
            shipment.click('pack')
            shipment.click('do')

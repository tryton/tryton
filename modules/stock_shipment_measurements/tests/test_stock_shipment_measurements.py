# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
from decimal import Decimal

from trytond.pool import Pool
from trytond.tests.test_tryton import (ModuleTestCase, activate_module,
    with_transaction)
from trytond.tests.test_tryton import suite as test_suite

from trytond.modules.company.tests import create_company, set_company


class StockShipmentMeasurementsTestCase(ModuleTestCase):
    'Test Stock Shipment Measurements module'
    module = 'stock_shipment_measurements'
    extras = ['stock_package']
    longMessage = True

    @classmethod
    def setUpClass(cls):
        super(StockShipmentMeasurementsTestCase, cls).setUpClass()
        activate_module('stock_package')

    @with_transaction()
    def test_move_internal_measurements(self):
        "Test move internal measurements"
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        kg, = Uom.search([('name', '=', 'Kilogram')])
        g, = Uom.search([('name', '=', 'Gram')])
        liter, = Uom.search([('name', '=', 'Liter')])
        supplier, = Location.search([('code', '=', 'SUP')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        currency = company.currency

        template, = Template.create([{
                    'name': "Test internal measurements",
                    'type': 'goods',
                    'list_price': Decimal(1),
                    'default_uom': kg,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])

        # without any measurements
        with set_company(company):
            move, = Move.create([{
                        'product': product,
                        'uom': g,
                        'quantity': 200,
                        'from_location': supplier,
                        'to_location': storage,
                        'company': company,
                        'unit_price': Decimal(1),
                        'currency': currency,
                        }])
            self.assertEqual(move.internal_weight, 0.2)
            self.assertEqual(move.internal_volume, None)

            Move.write([move], {'quantity': 100})
            self.assertEqual(move.internal_weight, 0.1)
            self.assertEqual(move.internal_volume, None)

        template.weight = 1.1
        template.weight_uom = kg
        template.save()

        # with weight measurements
        with set_company(company):
            move, = Move.create([{
                        'product': product,
                        'uom': g,
                        'quantity': 300,
                        'from_location': supplier,
                        'to_location': storage,
                        'company': company,
                        'unit_price': Decimal(1),
                        'currency': currency,
                        }])
            self.assertEqual(move.internal_weight, 0.33)
            self.assertEqual(move.internal_volume, None)

            Move.write([move], {'quantity': 500})
            self.assertEqual(move.internal_weight, 0.55)
            self.assertEqual(move.internal_volume, None)

        template.volume = 2
        template.volume_uom = liter
        template.save()

        # with weight and volume measurements
        with set_company(company):
            move, = Move.create([{
                        'product': product,
                        'uom': g,
                        'quantity': 500,
                        'from_location': supplier,
                        'to_location': storage,
                        'company': company,
                        'unit_price': Decimal(1),
                        'currency': currency,
                        }])
            self.assertEqual(move.internal_weight, 0.55)
            self.assertEqual(move.internal_volume, 1)

            Move.write([move], {'quantity': 600})
            self.assertEqual(move.internal_weight, 0.66)
            self.assertEqual(move.internal_volume, 1.2)

    @with_transaction()
    def test_shipment_out_measurements(self):
        "Test shipment out measurements"
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Shipment = pool.get('stock.shipment.out')
        Package = pool.get('stock.package')
        PackageType = pool.get('stock.package.type')
        Party = pool.get('party.party')

        kg, = Uom.search([('name', '=', 'Kilogram')])
        liter, = Uom.search([('name', '=', 'Liter')])
        customer, = Location.search([('code', '=', 'CUS')])
        storage, = Location.search([('code', '=', 'STO')])
        party = Party(name='Customer')
        party.addresses = [{}]
        party.save()
        company = create_company()
        currency = company.currency
        package_type = PackageType(name="Type")
        package_type.save()

        template, = Template.create([{
                    'name': "Test measurements",
                    'type': 'goods',
                    'list_price': Decimal(1),
                    'default_uom': kg,
                    'volume': 0.2,
                    'volume_uom': liter,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])

        with set_company(company):
            shipment = Shipment()
            shipment.customer = party
            shipment.delivery_address, = party.addresses
            shipment.save()

            # without moves
            self.assertEqual(shipment.weight, None)
            self.assertEqual(shipment.volume, None)

            shipment.moves = [Move(
                    product=product,
                    uom=kg,
                    quantity=10,
                    from_location=storage,
                    to_location=customer,
                    company=company,
                    unit_price=Decimal(1),
                    currency=currency,
                    )]
            shipment.save()

            # without inventory moves
            self.assertEqual(shipment.weight, 10)
            self.assertEqual(shipment.volume, 2)

            Shipment.wait([shipment])

            # with inventory moves
            self.assertEqual(shipment.weight, 10)
            self.assertEqual(shipment.volume, 2)

            for clause, result in [
                    ([('weight', '=', 10)], [shipment]),
                    ([('weight', '=', 5)], []),
                    ([('volume', '=', 2)], [shipment]),
                    ([('volume', '=', 3)], []),
                    ]:
                msg = 'clause: %s' % clause
                self.assertEqual(Shipment.search(clause), result, msg=msg)

            # Add packages
            package_root = Package()
            package_root.type = package_type
            package_root.shipment = shipment
            package_root.additional_weight = 1
            package_root.save()

            package = Package()
            package.type = package_type
            package.shipment = shipment
            package.moves = shipment.moves
            package.parent = package_root
            package.save()

            self.assertEqual(package_root.weight, None)
            self.assertEqual(package_root.volume, None)

            self.assertEqual(package.weight, 10)
            self.assertEqual(package.volume, 2)

            self.assertEqual(package_root.total_weight, 11)
            self.assertEqual(package_root.total_volume, 2)


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockShipmentMeasurementsTestCase))
    return suite

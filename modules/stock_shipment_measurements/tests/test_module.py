# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.modules.company.tests import (
    CompanyTestMixin, create_company, set_company)
from trytond.pool import Pool
from trytond.tests.test_tryton import (
    ModuleTestCase, activate_module, with_transaction)


class StockShipmentMeasurementsTestCase(CompanyTestMixin, ModuleTestCase):
    'Test Stock Shipment Measurements module'
    module = 'stock_shipment_measurements'
    extras = ['stock_package']
    longMessage = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
                    'default_uom': kg,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])

        # without any measurements
        with set_company(company):
            move, = Move.create([{
                        'product': product,
                        'unit': g,
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
                        'unit': g,
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
                        'unit': g,
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
            shipment.warehouse = Shipment.default_warehouse()
            shipment.on_change_warehouse()
            shipment.save()

            # without moves
            self.assertEqual(shipment.weight, None)
            self.assertEqual(shipment.volume, None)

            shipment.moves = [Move(
                    product=product,
                    unit=kg,
                    quantity=10,
                    from_location=shipment.warehouse.output_location,
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
            Shipment.pick([shipment])

            # with inventory moves
            self.assertEqual(shipment.weight, 10)
            self.assertEqual(shipment.volume, 2)

            for clause, result in [
                    ([('weight', '=', 10)], [shipment]),
                    ([('weight', '=', 5)], []),
                    ([('weight', 'in', [10, 5])], [shipment]),
                    ([('volume', '=', 2)], [shipment]),
                    ([('volume', '=', 3)], []),
                    ([('volume', 'in', [2, 3])], [shipment]),
                    ]:
                msg = 'clause: %s' % clause
                self.assertEqual(Shipment.search(clause), result, msg=msg)

            # Add packages
            package_root = Package()
            package_root.type = package_type
            package_root.shipment = shipment
            package_root.additional_weight = 1
            package_root.packaging_volume = 3
            package_root.packaging_volume_uom = liter
            package_root.save()

            package = Package()
            package.type = package_type
            package.shipment = shipment
            package.moves = shipment.outgoing_moves
            package.parent = package_root
            package.save()

            self.assertEqual(package_root.weight, None)
            self.assertEqual(package_root.volume, None)

            self.assertEqual(package.weight, 10)
            self.assertEqual(package.volume, 2)

            self.assertEqual(package_root.total_weight, 11)
            self.assertEqual(package_root.total_volume, 3)

            self.assertEqual(package.total_weight, 10)
            self.assertEqual(package.total_volume, 2)

            Shipment.pack([shipment])
            Shipment.do([shipment])

            self.assertEqual(shipment.internal_weight, 10)
            self.assertEqual(shipment.internal_volume, 2)
            self.assertEqual(shipment.weight, 10)
            self.assertEqual(shipment.volume, 2)

            for clause, result in [
                    ([('weight', '=', 10)], [shipment]),
                    ([('weight', '=', 5)], []),
                    ([('weight', 'in', [10, 5])], [shipment]),
                    ([('volume', '=', 2)], [shipment]),
                    ([('volume', '=', 3)], []),
                    ([('volume', 'in', [2, 3])], [shipment]),
                    ]:
                msg = 'clause: %s' % clause
                self.assertEqual(Shipment.search(clause), result, msg=msg)

    @with_transaction()
    def test_shipment_internal_measurements(self):
        "Test shipment internal measurements"
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Shipment = pool.get('stock.shipment.internal')

        kg, = Uom.search([('name', '=', 'Kilogram')])
        liter, = Uom.search([('name', '=', 'Liter')])
        warehouse1, = Location.search([('type', '=', 'warehouse')])
        warehouse2, = Location.copy([warehouse1])
        company = create_company()

        template, = Template.create([{
                    'name': "Test measurements",
                    'type': 'goods',
                    'default_uom': kg,
                    'volume': 0.2,
                    'volume_uom': liter,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])

        with set_company(company):
            shipment = Shipment()
            shipment.from_location = warehouse1.storage_location
            shipment.to_location = warehouse2.storage_location
            shipment.save()

            # without moves
            self.assertEqual(shipment.weight, 0)
            self.assertEqual(shipment.volume, 0)

            shipment.moves = [Move(
                    product=product,
                    unit=kg,
                    quantity=10,
                    from_location=shipment.from_location,
                    to_location=shipment.to_location,
                    company=company,
                    )]
            shipment.save()

            # without transit
            self.assertEqual(shipment.weight, 10)
            self.assertEqual(shipment.volume, 2)

            Shipment.wait([shipment])
            self.assertEqual(len(shipment.moves), 2)

            # with transit
            self.assertEqual(shipment.weight, 10)
            self.assertEqual(shipment.volume, 2)


del ModuleTestCase

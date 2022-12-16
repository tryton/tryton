# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class StockForecastTestCase(ModuleTestCase):
    'Test StockForecast module'
    module = 'stock_forecast'

    @with_transaction()
    def test_distribute(self):
        'Test distribute'
        pool = Pool()
        Line = pool.get('stock.forecast.line')
        line = Line()
        for values, result in (
                ((1, 5), {0: 5}),
                ((4, 8), {0: 2, 1: 2, 2: 2, 3: 2}),
                ((2, 5), {0: 2, 1: 3}),
                ((10, 4), {0: 0, 1: 1, 2: 0, 3: 1, 4: 0,
                        5: 0, 6: 1, 7: 0, 8: 1, 9: 0}),
                ):
            self.assertEqual(line.distribute(*values), result)

    @with_transaction()
    def test_create_moves_before(self):
        "Test create moves before start date"
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Forecast = pool.get('stock.forecast')
        Move = pool.get('stock.move')

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test create_moves',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'list_price': Decimal('1'),
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        customer, = Location.search([('code', '=', 'CUS')])
        warehouse, = Location.search([('code', '=', 'WH')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        with set_company(company):
            today = datetime.date.today()

            forecast, = Forecast.create([{
                        'warehouse': warehouse.id,
                        'destination': customer.id,
                        'from_date': today + relativedelta(months=1, day=1),
                        'to_date': today + relativedelta(months=1, day=20),
                        'company': company.id,
                        'lines': [
                            ('create', [{
                                        'product': product.id,
                                        'quantity': 10,
                                        'uom': unit.id,
                                        'minimal_quantity': 2,
                                        }],
                                ),
                            ],
                        }])
            Forecast.confirm([forecast])

            Forecast.create_moves([forecast])
            line, = forecast.lines
            self.assertEqual(line.quantity_executed, 0)
            self.assertEqual(len(line.moves), 5)
            self.assertEqual(sum(move.quantity for move in line.moves), 10)
            self.assertGreaterEqual(
                min(m.planned_date for m in line.moves), forecast.from_date)

            Forecast.delete_moves([forecast])
            line, = forecast.lines
            self.assertEqual(len(line.moves), 0)

            Move.create([{
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 2,
                        'planned_date': today + relativedelta(months=1, day=5),
                        'company': company.id,
                        'currency': company.currency.id,
                        'unit_price': Decimal('1'),
                        }])
            line, = forecast.lines
            self.assertEqual(line.quantity_executed, 2)

            Forecast.create_moves([forecast])
            line, = forecast.lines
            self.assertEqual(line.quantity_executed, 2)
            self.assertEqual(len(line.moves), 4)
            self.assertEqual(sum(move.quantity for move in line.moves), 8)
            self.assertGreaterEqual(
                min(m.planned_date for m in line.moves), forecast.from_date)

    @with_transaction()
    def test_create_moves_during(self):
        "Test create moves during the period"
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Forecast = pool.get('stock.forecast')
        Move = pool.get('stock.move')

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test create_moves',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'list_price': Decimal('1'),
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        customer, = Location.search([('code', '=', 'CUS')])
        warehouse, = Location.search([('code', '=', 'WH')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        with set_company(company):
            today = datetime.date.today()

            forecast, = Forecast.create([{
                        'warehouse': warehouse.id,
                        'destination': customer.id,
                        'from_date': today - relativedelta(days=20),
                        'to_date': today + relativedelta(days=10),
                        'company': company.id,
                        'lines': [
                            ('create', [{
                                        'product': product.id,
                                        'quantity': 20,
                                        'uom': unit.id,
                                        'minimal_quantity': 2,
                                        }],
                                ),
                            ],
                        }])
            Forecast.confirm([forecast])

            Forecast.create_moves([forecast])
            line, = forecast.lines
            self.assertEqual(line.quantity_executed, 0)
            self.assertEqual(len(line.moves), 10)
            self.assertEqual(sum(move.quantity for move in line.moves), 20)
            self.assertGreaterEqual(
                min(m.planned_date for m in line.moves), today)

            Forecast.delete_moves([forecast])
            line, = forecast.lines
            self.assertEqual(len(line.moves), 0)

            Move.create([{
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 10,
                        'planned_date': today - relativedelta(days=5),
                        'company': company.id,
                        'currency': company.currency.id,
                        'unit_price': Decimal('1'),
                        }])
            line, = forecast.lines
            self.assertEqual(line.quantity_executed, 10)

            Forecast.create_moves([forecast])
            line, = forecast.lines
            self.assertEqual(line.quantity_executed, 10)
            self.assertEqual(len(line.moves), 5)
            self.assertEqual(sum(move.quantity for move in line.moves), 10)
            self.assertGreaterEqual(
                min(m.planned_date for m in line.moves), today)

    @with_transaction()
    def test_create_moves_after(self):
        "Test create not moves after end date"
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Forecast = pool.get('stock.forecast')

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test create_moves',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'list_price': Decimal('1'),
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        customer, = Location.search([('code', '=', 'CUS')])
        warehouse, = Location.search([('code', '=', 'WH')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        with set_company(company):
            today = datetime.date.today()

            forecast, = Forecast.create([{
                        'warehouse': warehouse.id,
                        'destination': customer.id,
                        'from_date': today - relativedelta(days=20),
                        'to_date': today - relativedelta(days=10),
                        'company': company.id,
                        'lines': [
                            ('create', [{
                                        'product': product.id,
                                        'quantity': 20,
                                        'uom': unit.id,
                                        'minimal_quantity': 2,
                                        }],
                                ),
                            ],
                        }])
            Forecast.confirm([forecast])

            Forecast.create_moves([forecast])
            line, = forecast.lines
            self.assertEqual(len(line.moves), 0)

    @with_transaction()
    def test_complete(self):
        'Test complete'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        Forecast = pool.get('stock.forecast')
        Move = pool.get('stock.move')
        ForecastComplete = pool.get('stock.forecast.complete', type='wizard')

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Test complete',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'list_price': Decimal('1'),
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        customer, = Location.search([('code', '=', 'CUS')])
        supplier, = Location.search([('code', '=', 'SUP')])
        warehouse, = Location.search([('code', '=', 'WH')])
        storage, = Location.search([('code', '=', 'STO')])
        company = create_company()
        with set_company(company):
            today = datetime.date.today()

            moves = Move.create([{
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 10,
                        'effective_date': (today
                            + relativedelta(months=-1, day=1)),
                        'company': company.id,
                        'currency': company.currency.id,
                        'unit_price': Decimal('1'),
                        }, {
                        'from_location': storage.id,
                        'to_location': customer.id,
                        'product': product.id,
                        'uom': unit.id,
                        'quantity': 5,
                        'effective_date': (today
                            + relativedelta(months=-1, day=15)),
                        'company': company.id,
                        'currency': company.currency.id,
                        'unit_price': Decimal('1'),
                        }])
            Move.do(moves)

            forecast, = Forecast.create([{
                        'warehouse': warehouse.id,
                        'destination': customer.id,
                        'from_date': today + relativedelta(months=1, day=1),
                        'to_date': today + relativedelta(months=1, day=20),
                        'company': company.id,
                        }])

            with Transaction().set_context(
                    active_model=Forecast.__name__, active_id=forecast.id):
                session_id, _, _ = ForecastComplete.create()
                forecast_complete = ForecastComplete(session_id)
                forecast_complete.ask.from_date = (
                    today + relativedelta(months=-1, day=1))
                forecast_complete.ask.to_date = (
                    today + relativedelta(months=-1, day=20))
                forecast_complete.transition_complete()

            self.assertEqual(len(forecast.lines), 1)
            forecast_line, = forecast.lines
            self.assertEqual(forecast_line.product, product)
            self.assertEqual(forecast_line.uom, unit)
            self.assertEqual(forecast_line.quantity, 5)
            self.assertEqual(forecast_line.minimal_quantity, 1)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            StockForecastTestCase))
    return suite

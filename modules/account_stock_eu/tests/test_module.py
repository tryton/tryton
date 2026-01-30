# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from unittest.mock import Mock, patch

from trytond.modules.account.exceptions import FiscalYearNotFoundError
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class AccountStockEuTestCase(ModuleTestCase):
    "Test Account Stock Eu module"
    module = 'account_stock_eu'
    extras = ['carrier', 'incoterm', 'production', 'stock_consignment']

    @with_transaction()
    def test_sale_incoterm_required(self):
        "Test incoterm required on sale"
        pool = Pool()
        Sale = pool.get('sale.sale')
        FiscalYear = pool.get('account.fiscalyear')
        Country = pool.get('country.country')

        from_country = Mock(spec=Country)
        to_country = Mock(spec=Country)
        sale = Mock(spec=Sale)
        sale.warehouse.address.country = from_country
        sale.shipment_address.country = to_country
        type(sale)._incoterm_required = Sale._incoterm_required
        fiscalyear = Mock(spec=FiscalYear)

        with patch.object(FiscalYear, 'find') as fiscalyear_find:
            fiscalyear_find.return_value = fiscalyear
            for extended, from_europe, to_europe, result in [
                    (False, False, False, True),
                    (False, False, True, True),
                    (False, True, False, True),
                    (False, True, True, False),
                    (True, False, False, True),
                    (True, False, True, True),
                    (True, True, False, True),
                    (True, True, True, True),
                    (None, False, False, True),
                    (None, False, True, True),
                    (None, True, False, True),
                    (None, True, True, False),
                    ]:
                if extended is not None:
                    fiscalyear_find.side_effect = None
                    fiscalyear.intrastat_extended = extended
                else:
                    fiscalyear_find.side_effect = FiscalYearNotFoundError('')
                from_country.is_member.return_value = from_europe
                to_country.is_member.return_value = to_europe
                with self.subTest(
                        extended=extended,
                        from_europe=from_europe,
                        to_europe=to_europe):
                    self.assertEqual(sale._incoterm_required, result)

    @with_transaction()
    def test_sale_incoterm_required_same_country(self):
        "Test incoterm required on sale with same country"
        pool = Pool()
        Sale = pool.get('sale.sale')
        FiscalYear = pool.get('account.fiscalyear')
        Country = pool.get('country.country')

        country = Mock(spec=Country)
        sale = Mock(spec=Sale)
        sale.warehouse.address.country = country
        sale.shipment_address.country = country
        type(sale)._incoterm_required = Sale._incoterm_required
        fiscalyear = Mock(spec=FiscalYear)

        with patch.object(FiscalYear, 'find') as fiscalyear_find:
            fiscalyear_find.return_value = fiscalyear
            for extended, europe, result in [
                    (False, False, False),
                    (False, True, False),
                    (True, False, False),
                    (True, True, False),
                    (None, False, False),
                    (None, True, False),
                    ]:
                if extended is not None:
                    fiscalyear_find.side_effect = None
                    fiscalyear.intrastat_extended = extended
                else:
                    fiscalyear_find.side_effect = FiscalYearNotFoundError('')
                country.is_member.return_value = europe
                with self.subTest(
                        extended=extended,
                        europe=europe):
                    self.assertEqual(sale._incoterm_required, result)

    @with_transaction()
    def test_sale_incoterm_required_no_country(self):
        "Test incoterm required on sale without country"
        pool = Pool()
        Sale = pool.get('sale.sale')
        FiscalYear = pool.get('account.fiscalyear')

        sale = Mock(spec=Sale)
        sale.warehouse.address.country = None
        sale.shipment_address.country = None
        type(sale)._incoterm_required = Sale._incoterm_required
        fiscalyear = Mock(spec=FiscalYear)

        with patch.object(FiscalYear, 'find') as fiscalyear_find:
            fiscalyear_find.return_value = fiscalyear

            for extended, result in [
                    (False, False),
                    (True, False),
                    (None, False),
                    ]:
                if extended is not None:
                    fiscalyear_find.side_effect = None
                    fiscalyear.intrastat_extended = extended
                else:
                    fiscalyear_find.side_effect = FiscalYearNotFoundError('')
                with self.subTest(extended=extended):
                    self.assertEqual(sale._incoterm_required, result)


del ModuleTestCase

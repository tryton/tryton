# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker

from trytond.modules.account_asset.asset import normalized_delta


class AccountAssetTestCase(ModuleTestCase):
    'Test AccountAsset module'
    module = 'account_asset'
    extras = ['purchase']

    def test_normalized_delta(self):
        "Test normalized detal"
        for start, end, delta in [
                (dt.date(2019, 1, 1), dt.date(2019, 12, 31),
                    dt.timedelta(days=364)),
                (dt.date(2019, 1, 1), dt.date(2020, 1, 1),
                    dt.timedelta(days=365)),
                (dt.date(2019, 1, 1), dt.date(2019, 3, 1),
                    dt.timedelta(days=31 + 28)),
                (dt.date(2024, 1, 1), dt.date(2024, 2, 1),
                    dt.timedelta(days=31)),
                (dt.date(2024, 1, 1), dt.date(2024, 3, 1),
                    dt.timedelta(days=31 + 28)),
                (dt.date(2024, 3, 1), dt.date(2024, 4, 1),
                    dt.timedelta(days=31)),
                (dt.date(2024, 1, 1), dt.date(2025, 1, 1),
                    dt.timedelta(days=365)),
                (dt.date(2023, 1, 1), dt.date(2025, 1, 1),
                    dt.timedelta(days=365 * 2)),
                (dt.date(2000, 1, 1), dt.date(2020, 1, 1),
                    dt.timedelta(days=365 * 20)),
                ]:
            self.assertEqual(
                normalized_delta(start, end), delta,
                msg='%s - %s' % (start, end))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AccountAssetTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_account_asset.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_account_asset_depreciated.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite('scenario_purchase_asset.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

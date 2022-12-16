# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from trytond.modules.account_asset.asset import normalized_delta
from trytond.tests.test_tryton import ModuleTestCase


class AccountAssetTestCase(ModuleTestCase):
    'Test AccountAsset module'
    module = 'account_asset'
    extras = ['purchase']

    def test_normalized_delta(self):
        "Test normalized delta"
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


del ModuleTestCase

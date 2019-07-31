# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.report.report import Report


class ReportTestCase(unittest.TestCase):
    'Test Report'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_format_timedelta(self):
        "format_timedelta returns a string with the input time"

        timedelta = Report.format_timedelta(
            datetime.timedelta(days=400, hours=5))
        self.assertEqual(timedelta, '1Y 1M 5d 05:00')

        timedelta = Report.format_timedelta(
            datetime.timedelta(days=400))
        self.assertEqual(timedelta, '1Y 1M 5d 00:00')

        timedelta = Report.format_timedelta(
            datetime.timedelta(days=400, hours=5, minutes=30, seconds=40),
            skip_zeros=True)
        self.assertEqual(timedelta, '1Y 1M 5d')


def suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(ReportTestCase))
    return suite

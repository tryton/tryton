# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.report.report import Report
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)


class ReportTestCase(TestCase):
    'Test Report'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        activate_module('tests')

    @with_transaction()
    def test_format_datetime(self):
        "Test format datetime"
        self.assertEqual(Report.format_datetime(
                datetime.datetime(2020, 7, 8, 13, 30, 00)),
            '07/08/2020 13:30:00')

    @with_transaction()
    def test_format_datetime_custom_format(self):
        "Test format datetime custom format"
        self.assertEqual(Report.format_datetime(
                datetime.datetime(2020, 7, 8, 13, 30, 00),
                format='%d %b %Y %I:%M %p'),
            "08 Jul 2020 01:30 PM"),

    @with_transaction()
    def test_execute(self):
        "Execute report"
        pool = Pool()
        Report = pool.get('test.test_report', type='report')

        self.assertEqual(
            Report.execute([], {}),
            ('txt', 'Administrator\n', False, 'Test Report'))

    @with_transaction()
    def test_execute_without_access(self):
        "Execute report without model access"
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        Group = pool.get('res.group')
        Report = pool.get('test.test_report', type='report')

        group = Group(name="Test")
        group.save()
        action_report, = ActionReport.search([
                ('report_name', '=', 'test.test_report'),
                ])
        action_report.groups = [group]
        action_report.save()

        with self.assertRaises(AccessError):
            Report.execute([], {'model': 'test.access'})

    @with_transaction()
    def test_execute_without_model_access(self):
        "Execute report without model access"
        pool = Pool()
        Report = pool.get('test.test_report', type='report')
        ModelAccess = pool.get('ir.model.access')
        ModelAccess.create([{
                    'model': 'test.access',
                    'perm_write': False,
                    }])

        with self.assertRaises(AccessError):
            Report.execute([], {'model': 'test.access'})

    @with_transaction()
    def test_execute_without_read_access(self):
        "Execute report without read access"
        pool = Pool()
        Report = pool.get('test.test_report', type='report')

        with self.assertRaises(AccessError):
            Report.execute([1], {'model': 'test.access'})


def create_test_format_timedelta(i, in_, out):
    @with_transaction()
    def test(self):
        self.assertEqual(Report.format_timedelta(in_), out)
    test.__name__ = 'test_format_timedelta_%d' % i
    test.__doc__ = "test format_timedelta of %s" % in_
    return test


for i, (in_, out) in enumerate([
            (None, ''),
            (datetime.timedelta(), '00:00'),
            (datetime.timedelta(days=3, hours=5, minutes=30), '3d 05:30'),
            (datetime.timedelta(weeks=48), '11M 6d'),
            (datetime.timedelta(weeks=50), '11M 2w 6d'),
            (datetime.timedelta(weeks=52), '12M 4d'),
            (datetime.timedelta(days=360), '12M'),
            (datetime.timedelta(days=364), '12M 4d'),
            (datetime.timedelta(days=365), '1Y'),
            (datetime.timedelta(days=366), '1Y 1d'),
            (datetime.timedelta(hours=2, minutes=5, seconds=10), '02:05:10'),
            (datetime.timedelta(minutes=15, microseconds=42),
                '00:15:00.000042'),
            (datetime.timedelta(days=1, microseconds=42), '1d .000042'),
            (datetime.timedelta(seconds=-1), '-00:00:01'),
            (datetime.timedelta(days=-1, hours=-5, minutes=-30), '-1d 05:30'),
            ]):
    test_method = create_test_format_timedelta(i, in_, out)
    setattr(ReportTestCase, test_method.__name__, test_method)

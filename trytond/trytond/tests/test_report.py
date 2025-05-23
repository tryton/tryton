# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from email.message import EmailMessage
from unittest.mock import Mock, patch

from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.report.report import Report, get_email
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)
from trytond.transaction import Transaction


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

    @with_transaction()
    def test_get_email_html(self):
        "Test get email"
        class FakeReport(Report):
            @classmethod
            def execute(cls, *args, **kwargs):
                return (
                    'html', '<!doctype html><title>Test</title>', False,
                    "Title")

        record = Mock()
        language = Mock()
        language.code = 'en'
        msg, title = get_email(FakeReport, record, [language])

        self.assertEqual(title, "Title")
        self.assertIsInstance(msg, EmailMessage)
        self.assertEqual(msg['Content-Language'], 'en')
        self.assertTrue(msg.is_multipart())

        plain = msg.get_body(preferencelist=('plain',))
        self.assertEqual(plain['Content-Language'], 'en')
        self.assertEqual(plain.get_content().strip(), "Test")

        html = msg.get_body(preferencelist=('html',))
        self.assertEqual(html['Content-Language'], 'en')
        self.assertEqual(
            html.get_content().strip(),
            '<!doctype html><title>Test</title>')

    @with_transaction()
    @patch('trytond.report.report.html2text')
    def test_get_email_html_without_html2text(self, html2text):
        html2text.__bool__.side_effect = lambda: False

        class FakeReport(Report):
            @classmethod
            def execute(cls, *args, **kwargs):
                return (
                    'html', '<!doctype html><title>Test</title>', False,
                    "Title")

        record = Mock()
        language = Mock()
        language.code = 'en'
        msg, title = get_email(FakeReport, record, [language])

        self.assertEqual(title, "Title")
        self.assertIsInstance(msg, EmailMessage)
        self.assertEqual(msg['Content-Language'], 'en')
        self.assertFalse(msg.is_multipart())
        self.assertEqual(
            msg.get_content().strip(),
            '<!doctype html><title>Test</title>')

    @with_transaction()
    def test_get_email_html_multilanguage(self):
        "Test get email multi-language"
        class FakeReport(Report):
            @classmethod
            def execute(cls, *args, **kwargs):
                language = Transaction().language
                return (
                    'html', f'<!doctype html><title>{language}</title>',
                    False, language.upper())

        record = Mock()
        french = Mock()
        french.code = 'fr'
        english = Mock()
        english.code = 'en'
        msg, title = get_email(FakeReport, record, [french, english])

        self.assertEqual(title, "EN")
        self.assertIsInstance(msg, EmailMessage)
        self.assertEqual(msg['Content-Language'], 'fr, en')
        self.assertTrue(msg.is_multipart())
        self.assertEqual(len(list(msg.walk())), 5)

        plain = msg.get_body(preferencelist=('plain',))
        self.assertEqual(plain['Content-Language'], 'fr')
        self.assertEqual(plain.get_content().strip(), "fr")

        html = msg.get_body(preferencelist=('html',))
        self.assertEqual(html['Content-Language'], 'fr')
        self.assertEqual(
            html.get_content().strip(),
            '<!doctype html><title>fr</title>')

    @with_transaction()
    def test_get_email_binary(self):
        "Test get email binary"
        class FakeReport(Report):
            @classmethod
            def execute(cls, *args, **kwargs):
                return 'pdf', b'PDF', False, "Title"

        record = Mock()
        language = Mock()
        language.code = 'en'
        msg, title = get_email(FakeReport, record, [language])

        self.assertEqual(title, "Title")
        self.assertIsInstance(msg, EmailMessage)
        self.assertEqual(msg['Content-Language'], 'en')
        self.assertFalse(msg.is_multipart())
        self.assertEqual(msg.get_content_maintype(), 'application')
        self.assertEqual(msg.get_content_subtype(), 'pdf')


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

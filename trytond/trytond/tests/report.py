# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.report import Report


class TestReport(Report):
    __name__ = 'test.test_report'


class TestReportMJML(Report):
    __name__ = 'test.test_report_mjml'


def register(module):
    Pool.register(
        TestReport,
        TestReportMJML,
        module=module, type_='report')

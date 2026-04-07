# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import patch

from .common import NaiadTestCase


class ActionTestCase(NaiadTestCase):

    def setUp(self):
        super().setUp()
        patcher = patch('trytond.res.user._send_email')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_report(self):
        "Test report"
        c = self.client()

        c.action('res.user', 'reset_password', 1)
        filename, content = c.report(
            'res.user.email_reset_password', 1)

        self.assertRegex(filename, r'.*\.html')
        self.assertIsInstance(content, bytes)

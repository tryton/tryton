# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from urllib.parse import urljoin

import respx

from naiad import Client
from trytond.pool import Pool
from trytond.tests.test_tryton import RouteTestCase, app

__all__ = ['NaiadTestCase', 'app']


class NaiadTestCase(RouteTestCase):
    module = 'res'
    base_url = 'http://localhost:8000'

    @classmethod
    def setUpDatabase(cls):
        pool = Pool()
        User = pool.get('res.user')
        UserApplication = pool.get('res.user.application')
        admin, = User.search([('login', '=', 'admin')])
        admin.email = 'admin@tryton.org'
        admin.save()
        application = UserApplication(user=admin, application='rest')
        application.save()
        cls.key = application.key

    @property
    def url(self):
        return urljoin(self.base_url, self.db_name)

    def setUp(self):
        super().setUp()
        self.respx_mock = respx.mock(base_url=self.base_url)
        self.respx_mock.start()
        self.respx_mock.route().mock(side_effect=respx.WSGIHandler(app))
        self.addCleanup(self.respx_mock.stop)

    def client(self, usages=None, context=None, languages=None):
        return Client(
            self.url, self.key,
            usages=usages, context=context, languages=languages)

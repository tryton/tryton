# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import base64
import json
import urllib.parse

from trytond.pool import Pool
from trytond.protocols.wrappers import HTTPStatus, Response
from trytond.routing import BuildURLError
from trytond.tests.test_tryton import (
    DB_NAME, Client, RouteTestCase, TestCase, activate_module, drop_db,
    with_transaction)
from trytond.transaction import Transaction
from trytond.wsgi import app


class RoutesTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        drop_db()
        activate_module(['ir', 'res'], 'fr')
        pool = Pool(DB_NAME)
        with Transaction().start(DB_NAME, 0):
            User = pool.get('res.user')
            admin, = User.search([('login', '=', 'admin')])
            admin.password = 'password'
            admin.save()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        drop_db()

    @property
    def auth_headers(self):
        return {
            'Authorization': (
                'Basic ' + base64.b64encode(b'admin:password').decode()),
            }

    def data_url(self, model):
        return '/%(database)s/r/base/data/%(model)s' % {
            'database': DB_NAME,
            'model': model,
            }

    def test_data_no_field(self):
        "Test GET data without field"
        c = Client(app, Response)

        response = c.get(self.data_url('res.user'), headers=self.auth_headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.data, b'\r\n\r\n')

    def test_data_one_field(self):
        "Test GET data with one field"
        c = Client(app, Response)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'name')])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.data, b'Nom\r\nAdministrator\r\n')

    def test_data_multiple_fields(self):
        "Test GET data with multiple fields"
        c = Client(app, Response)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'name'), ('f', 'login')])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.data, b'Nom,Identifiant\r\nAdministrator,admin\r\n')

    def test_data_language(self):
        "Test GET data with language"
        c = Client(app, Response)

        response = c.get(
            self.data_url('ir.lang'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'),
                ('l', 'fr'),
                ('d', json.dumps([('code', '=', 'fr')])),
                ])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.data, 'Nom\r\nFrançais\r\n'.encode('utf-8'))

    def test_data_size(self):
        "Test GET data with size limit"
        c = Client(app, Response)

        response = c.get(
            self.data_url('ir.lang'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'),
                ('s', 5),
                ])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.data.splitlines()), 5 + 1)

    def test_data_page(self):
        "Test GET data with page"
        c = Client(app, Response)

        response0 = c.get(
            self.data_url('ir.lang'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'),
                ('s', 5),
                ('p', 0)
                ])
        response1 = c.get(
            self.data_url('ir.lang'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'),
                ('s', 5),
                ('p', 1)
                ])

        self.assertEqual(response0.status_code, HTTPStatus.OK)
        self.assertEqual(response1.status_code, HTTPStatus.OK)
        self.assertNotEqual(response0.data, response1.data)

    def test_data_encoding(self):
        "Test GET data with encoding"
        c = Client(app, Response)

        response = c.get(
            self.data_url('ir.lang'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'),
                ('l', 'fr'),
                ('d', json.dumps([('code', '=', 'fr')])),
                ('enc', 'latin1'),
                ])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.data, 'Nom\r\nFrançais\r\n'.encode('latin1'))

    def test_data_delimiter(self):
        "Test GET data with delimiter"
        c = Client(app, Response)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'name'), ('f', 'login'), ('dl', '|')])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.data, b'Nom|Identifiant\r\nAdministrator|admin\r\n')

    def test_data_quotechar(self):
        "Test GET data with quotechar"
        c = Client(app, Response)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'), ('f', 'login'), ('dl', 'n'), ('qc', '*')])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.data,
            b'Nomn*Identifiant*\r\n*Administrator*n*admin*\r\n')

    def test_data_no_header(self):
        "Test GET data without header"
        c = Client(app, Response)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'name'), ('h', 0)])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.data, b'Administrator\r\n')

    def test_data_locale_format(self):
        "Test GET data in locale format"
        c = Client(app, Response)

        response_std = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'create_date')])
        response_locale = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'create_date'), ('loc', 1)])

        self.assertEqual(response_std.status_code, HTTPStatus.OK)
        self.assertEqual(response_locale.status_code, HTTPStatus.OK)
        self.assertNotEqual(response_std.data, response_locale.data)


class RoutingTestCase(RouteTestCase):
    module = 'tests'

    def test_route(self):
        "Test route"
        c = self.client()

        response = c.get(f'/{self.db_name}/r/test/hello')
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.text, "Hello, World!")

    def test_route_with_parameters(self):
        "Test route with parameters"
        c = self.client()

        response = c.get(f'/{self.db_name}/r/test/hello/Foo')
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.text, "Hello, Foo!")

    def test_router_redirection(self):
        "Test route with redirection"
        c = self.client()

        response = c.get('/test/redirection/redirect/Foo')
        self.assertEqual(response.status_code, HTTPStatus.PERMANENT_REDIRECT)
        location = urllib.parse.urlsplit(response.location)
        self.assertEqual(
            location.path, f'/{self.db_name}/r/test/redirection/Foo')

        response = c.get(response.location)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.text, "Foo succeeded!")

    @with_transaction()
    def test_url_for(self):
        "Test url_for"
        pool = Pool()
        Router = pool.get('test', type='router')

        for values, expected_url in [
                ({'model': 'foo', 'id': 1},
                    f'/{self.db_name}/r/test/url/foo/1'),
                ({'model': 'bar', 'id': 2, 'field': 'baz'},
                    f'/{self.db_name}/r/test/url/bar/2/baz'),
                ]:
            with self.subTest(values=values):
                url = Router.url_for('url_rel', **values)
                parsed_url = urllib.parse.urlsplit(url)
                self.assertEqual(parsed_url.path, expected_url)

    @with_transaction()
    def test_url_for_absolute_url(self):
        "Test url_for with an absolute URL"
        pool = Pool()
        Router = pool.get('test', type='router')

        for values, expected_url in [
                ({'model': 'foo', 'id': 1}, '/test/url/foo/1'),
                ({'model': 'bar', 'id': 2, 'field': 'baz'},
                    '/test/url/bar/2/baz'),
                ]:
            with self.subTest(values=values):
                url = Router.url_for('url_abs', **values)
                parsed_url = urllib.parse.urlsplit(url)
                self.assertEqual(parsed_url.path, expected_url)

    @with_transaction()
    def test_url_for_with_arguments(self):
        "Test url_for with arguments"
        pool = Pool()
        Router = pool.get('test', type='router')
        find_me_url = Router.url_for('url_rel', model='foo', id=1, a1=1, a2=2)
        parsed_url = urllib.parse.urlsplit(find_me_url)
        self.assertEqual(
            parsed_url.path, f'/{self.db_name}/r/test/url/foo/1')
        self.assertEqual(
            urllib.parse.parse_qs(parsed_url.query),
            {'a1': ['1'], 'a2': ['2']})

    @with_transaction()
    def test_url_for_no_match(self):
        "Test url_for when the arguments does not match"
        pool = Pool()
        Router = pool.get('test', type='router')

        for values in (
                {},
                {'model': 'foo'},
                {'id': 1},
                {'field': 'baz'},
                {'model': 'foo', 'field': 'baz'},
                {'field': 'baz', 'id': 2},
                {'model': 'foo', 'field': 'baz', 'extra': 'yes'},
                ):
            with self.subTest(values=values):
                with self.assertRaises(BuildURLError):
                    Router.url_for('url_rel', **values)

    @with_transaction()
    def test_url_for_no_match_method(self):
        "Test url_for when the method does not match"
        pool = Pool()
        Router = pool.get('test', type='router')

        with self.assertRaises(BuildURLError):
            Router.url_for('url_rel', model='foo', id=1, _method='POST')

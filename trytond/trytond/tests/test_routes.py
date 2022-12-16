# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import base64
import json
import unittest

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, DB_NAME, drop_db
from trytond.transaction import Transaction
from trytond.wsgi import app


class RoutesTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
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
            'Authorization': b'Basic ' + base64.b64encode(b'admin:password'),
            }

    def data_url(self, model):
        return '/%(database)s/data/%(model)s' % {
            'database': DB_NAME,
            'model': model,
            }

    def test_data_no_field(self):
        "Test GET data without field"
        c = Client(app, BaseResponse)

        response = c.get(self.data_url('res.user'), headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'\r\n\r\n')

    def test_data_one_field(self):
        "Test GET data with one field"
        c = Client(app, BaseResponse)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'name')])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'name\r\nAdministrator\r\n')

    def test_data_multiple_fields(self):
        "Test GET data with multiple fields"
        c = Client(app, BaseResponse)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'name'), ('f', 'login')])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data, b'name,login\r\nAdministrator,admin\r\n')

    def test_data_language(self):
        "Test GET data with language"
        c = Client(app, BaseResponse)

        response = c.get(
            self.data_url('ir.lang'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'),
                ('l', 'fr'),
                ('d', json.dumps([('code', '=', 'fr')])),
                ])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, 'name\r\nFrançais\r\n'.encode('utf-8'))

    def test_data_size(self):
        "Test GET data with size limit"
        c = Client(app, BaseResponse)

        response = c.get(
            self.data_url('ir.lang'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'),
                ('s', 5),
                ])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.splitlines()), 5 + 1)

    def test_data_page(self):
        "Test GET data with page"
        c = Client(app, BaseResponse)

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

        self.assertEqual(response0.status_code, 200)
        self.assertEqual(response1.status_code, 200)
        self.assertNotEqual(response0.data, response1.data)

    def test_data_encoding(self):
        "Test GET data with encoding"
        c = Client(app, BaseResponse)

        response = c.get(
            self.data_url('ir.lang'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'),
                ('l', 'fr'),
                ('d', json.dumps([('code', '=', 'fr')])),
                ('enc', 'latin1'),
                ])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data, 'name\r\nFrançais\r\n'.encode('latin1'))

    def test_data_delimiter(self):
        "Test GET data with delimiter"
        c = Client(app, BaseResponse)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'name'), ('f', 'login'), ('dl', '|')])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data, b'name|login\r\nAdministrator|admin\r\n')

    def test_data_quotechar(self):
        "Test GET data with quotechar"
        c = Client(app, BaseResponse)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[
                ('f', 'name'), ('f', 'login'), ('dl', 'n'), ('qc', '*')])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data, b'*name*n*login*\r\n*Administrator*n*admin*\r\n')

    def test_data_no_header(self):
        "Test GET data without header"
        c = Client(app, BaseResponse)

        response = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'name'), ('h', 0)])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'Administrator\r\n')

    def test_data_locale_format(self):
        "Test GET data in locale format"
        c = Client(app, BaseResponse)

        response_std = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'create_date')])
        response_locale = c.get(
            self.data_url('res.user'), headers=self.auth_headers,
            query_string=[('f', 'create_date'), ('loc', 1)])

        self.assertEqual(response_std.status_code, 200)
        self.assertEqual(response_locale.status_code, 200)
        self.assertNotEqual(response_std.data, response_locale.data)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RoutesTestCase)

# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import json
from base64 import urlsafe_b64encode
from unittest.mock import patch

try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from trytond.pool import Pool
from trytond.tests.test_tryton import RouteTestCase


class RESTTestCase(RouteTestCase):
    key = None
    module = 'res'
    language = 'fr'

    def setUp(self):
        super().setUp()
        patcher = patch('trytond.res.user._send_email')
        patcher.start()
        self.addCleanup(patcher.stop)

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
    def headers(self):
        return {
            'Authorization': f'bearer {self.key}',
            }

    def test_search(self):
        "Test search"
        response = self.client().get(
            f'{self.db_name}/rest/model/res.user', headers=self.headers,
            query_string=[
                ('d', urlsafe_b64encode(json.dumps(
                            [('login', '=', 'admin')]).encode())),
                ])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.json,
            [{'id': 1, '__name__': 'res.user', 'rec_name': 'Administrator'}])
        self.assertEqual(response.headers.get('Content-Language'), 'fr')

    def test_search_range(self):
        "Test search range"
        c = self.client()

        headers = self.headers.copy()

        size = len(
            c.get(f'{self.db_name}/rest/model/ir.lang', headers=headers).json)

        for range_, content_range, length in [
                ('records=2-', f'records 2-{size}/{size}', size - 2),
                ('records=2-4', f'records 2-4/{size}', 2),
                ('records=2-4, 6-7', None, size),
                ('records=-2', None, size),
                ]:
            with self.subTest(range_=range_):
                headers['Range'] = range_
                response = c.get(
                    f'{self.db_name}/rest/model/ir.lang', headers=headers)

                self.assertEqual(response.status_code, HTTPStatus.OK)
                self.assertEqual(
                    response.headers.get('Content-Range'), content_range)
                self.assertEqual(len(response.json), length)

        headers['Range'] = f'records={size + 1}-'
        response = c.get(f'{self.db_name}/rest/model/ir.lang', headers=headers)
        self.assertEqual(
            response.status_code,
            HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)

    def test_search_limit(self):
        "Test search limit"
        response = self.client().get(
            f'{self.db_name}/rest/model/ir.lang', headers=self.headers,
            query_string=[('s', 2)])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.json), 2)

    def test_search_offset(self):
        "Test search offset"
        c = self.client()

        size = len(
            c.get(
                f'{self.db_name}/rest/model/ir.lang',
                headers=self.headers).json)

        response = c.get(
            f'{self.db_name}/rest/model/ir.lang', headers=self.headers,
            query_string=[('p', 2)])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.json), size - 2)

    def test_search_order(self):
        "Test search order"
        response = self.client().get(
            f'{self.db_name}/rest/model/ir.lang', headers=self.headers,
            query_string=[
                ('o', urlsafe_b64encode(json.dumps(
                            [('id', 'ASC')]).encode()))])

        self.assertEqual(response.status_code, HTTPStatus.OK)
        result = response.json
        self.assertEqual(result, sorted(result, key=lambda x: x['id']))

    def test_get(self):
        "Test get"
        response = self.client().get(
            f'{self.db_name}/rest/model/res.user/1', headers=self.headers)

        self.assertEqual(
            response.json,
            {'id': 1, '__name__': 'res.user', 'rec_name': 'Administrator'})

    def test_get_fields(self):
        "Test get fields"
        response = self.client().get(
            f'{self.db_name}/rest/model/res.user/1', headers=self.headers,
            query_string=[
                ('f', 'name'),
                ('f', 'login'),
                ('f', 'groups.name'),
                ])

        self.assertEqual(
            response.json,
            {'id': 1, '__name__': 'res.user',
                'name': "Administrator", 'login': 'admin',
                'groups': [
                    {'id': 1, '__name__': 'res.group',
                        'name': 'Administration'}],
                })

    def test_get_fields_2many(self):
        "Test get only xxx2many fields"
        response = self.client().get(
            f'{self.db_name}/rest/model/res.user/1', headers=self.headers,
            query_string=[
                ('f', 'groups'),
                ])

        self.assertEqual(
            response.json,
            {'id': 1, '__name__': 'res.user',
                'groups': [1],
                })

    def test_get_not_found(self):
        "Test get not found"
        response = self.client().get(
                f'{self.db_name}/rest/model/res.user/42', headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_create(self):
        "Test create"
        response = self.client().post(
            f'{self.db_name}/rest/model/res.user', headers=self.headers,
            json={'login': "test create"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.json,
            {**response.json,
                '__name__': 'res.user',
                'rec_name': "test create",
                })
        id = response.json['id']
        self.assertGreaterEqual(id, 0)

    def test_update(self):
        "Test update"
        c = self.client()

        response = c.post(
            f'{self.db_name}/rest/model/res.user', headers=self.headers,
            json={'login': "test update"})
        id = response.json['id']

        response = c.put(
            f'{self.db_name}/rest/model/res.user/{id}', headers=self.headers,
            json={'login': "test updated"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.json,
            {'id': id, '__name__': 'res.user', 'rec_name': 'test updated'})

    def test_update_not_found(self):
        "Test update not found"
        response = self.client().put(
            f'{self.db_name}/rest/model/res.user/42', headers=self.headers,
            json={'name': "Administrator"})

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_delete(self):
        "Test delete"
        c = self.client()

        response = c.post(
            f'{self.db_name}/rest/model/res.group', headers=self.headers,
            json={'name': 'test delete'})
        id = response.json['id']

        response = c.delete(
            f'{self.db_name}/rest/model/res.group/{id}', headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

    def test_delete_not_found(self):
        "Test delete not found"
        response = self.client().delete(
            f'{self.db_name}/rest/model/res.group/42', headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_button(self):
        "Test button"
        response = self.client().post(
            f'{self.db_name}/rest/model/res.user/1/reset_password',
            headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.json,
            {'id': 1, '__name__': 'res.user', 'rec_name': 'Administrator'})

    def test_button_no_record(self):
        "Test button without record"
        response = self.client().post(
            f'{self.db_name}/rest/model/res.user/get_preferences',
            headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsInstance(response.json, dict)

    def test_button_data(self):
        "Test button with data"
        response = self.client().post(
            f'{self.db_name}/rest/model/res.user/1/reset_password',
            json={
                'length': 12,
                },
            headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_button_not_found(self):
        "Test button not found"
        response = self.client().post(
            f'{self.db_name}/rest/model/res.user/42/reset_password',
            headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_button_no_button(self):
        "Test no button"
        response = self.client().post(
            f'{self.db_name}/rest/model/res.user/1/validate',
            headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_report(self):
        "Test report"
        c = self.client()

        response = c.post(
            f'{self.db_name}/rest/model/res.user/1/reset_password',
            headers=self.headers)
        response = c.get(
            f'{self.db_name}/rest/report/res.user.email_reset_password/1',
            headers=self.headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.mimetype, 'text/html')

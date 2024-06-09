# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import uuid
from unittest.mock import patch

from trytond.modules.company.tests import CompanyTestMixin
from trytond.modules.document_incoming.document import iter_pages
from trytond.pool import Pool
from trytond.protocols.wrappers import HTTPStatus
from trytond.tests.test_tryton import (
    ModuleTestCase, RouteTestCase, with_transaction)
from trytond.transaction import Transaction


class DocumentIncomingTestCase(CompanyTestMixin, ModuleTestCase):
    "Test Document Incoming module"
    module = 'document_incoming'
    extras = ['inbound_email']

    def test_iter_pages(self):
        "Test iter_pages"

        for expression, size, result in [
                ('1', 1, [[0]]),
                ('1,2', 2, [[0], [1]]),
                ('1-2', 2, [[0, 1]]),
                ('1-3', 2, [[0, 1]]),
                ('1-2', 4, [[0, 1], [2, 3]]),
                ('1-', 3, [[0, 1, 2]]),
                ('-2', 2, [[0, 1]]),
                ('1-2,3-4', 4, [[0, 1], [2, 3]]),
                ('2', 3, [[0], [1], [2]]),
                ('-2,3-', 4, [[0, 1], [2, 3]]),
                ('1--2', 2, [[0, 1]]),
                ('1,,4', 4, [[0], [1, 2], [3]]),
                ]:
            with self.subTest(expression=expression, size=size):
                self.assertEqual(
                    [list(i) for i in iter_pages(expression, size)],
                    result)

    def test_iter_pages_value_error(self):
        "Test iter_pages value error"

        for expression in ['a', 'a,b', '1-a']:
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    iter_pages(expression, 0)

    @with_transaction()
    def test_document_from_inbound_email(self):
        "Test document from inbound email"
        pool = Pool()
        Document = pool.get('document.incoming')
        Email = pool.get('inbound.email')
        Rule = pool.get('inbound.email.rule')

        with patch.object(Email, 'as_dict') as as_dict:
            as_dict.return_value = {
                'subject': "Subject",
                'text': "Text",
                'attachments': [{
                        'filename': "document",
                        'data': b'data',
                        }],
                }

            email = Email()
            rule = Rule(
                document_incoming_type='document_incoming',
                document_incoming_company=None,
                )

            document = Document.from_inbound_email(email, rule)

        self.assertFalse(document.active)
        self.assertEqual(document.name, "Subject")
        self.assertEqual(document.data, b'Text')
        self.assertEqual(document.source, 'inbound_email')
        child, = document.children
        self.assertTrue(child.active)
        self.assertEqual(child.name, 'document')
        self.assertEqual(child.data, b'data')
        self.assertEqual(child.source, 'inbound_email')


class DocumentIncomingRouteTestCase(RouteTestCase):
    "Test Document Incoming route"
    module = 'document_incoming'

    key = uuid.uuid4().hex

    @classmethod
    def setUpDatabase(cls):
        pool = Pool()
        Application = pool.get('res.user.application')
        Application(
            key=cls.key, user=1, application='document_incoming',
            state='validated').save()
        cls.Document = pool.get('document.incoming')

    def test_document_incoming_route_data(self):
        "Test document incoming route with data"

        client = self.client()

        response = client.post(
            f'/{self.db_name}/document_incoming'
            '?name=test&type=document_incoming',
            data=b'data',
            headers={
                'Authorization': f'bearer {self.key}',
                })
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        @with_transaction()
        def check():
            pool = Pool()
            Document = pool.get('document.incoming')
            document, = Document.search([])

            try:
                self.assertEqual(document.name, 'test')
                self.assertEqual(document.type, 'document_incoming')
                self.assertEqual(document.data, b'data')
            finally:
                Document.delete([document])
            Transaction().commit()
        check()

    def test_document_incoming_route_json(self):
        "Test document incoming route with JSON"

        client = self.client()

        response = client.post(
            f'/{self.db_name}/document_incoming',
            json={
                'name': 'test',
                'type': 'document_incoming',
                'data': 'ZGF0YQ==',
                },
            headers={
                'Authorization': f'bearer {self.key}',
                })
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        @with_transaction()
        def check():
            pool = Pool()
            Document = pool.get('document.incoming')
            document, = Document.search([])

            try:
                self.assertEqual(document.name, 'test')
                self.assertEqual(document.type, 'document_incoming')
                self.assertEqual(document.data, b'data')
            finally:
                Document.delete([document])
            Transaction().commit()
        check()

    def test_document_incoming_route_unknown_arguments(self):
        "Test document incoming route with JSON"

        client = self.client()

        response = client.post(
            f'/{self.db_name}/document_incoming?foo=bar',
            data=b'data',
            headers={
                'Authorization': f'bearer {self.key}',
                })
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        @with_transaction()
        def check():
            pool = Pool()
            Document = pool.get('document.incoming')
            document, = Document.search([])

            try:
                self.assertEqual(document.data, b'data')
            finally:
                Document.delete([document])
            Transaction().commit()
        check()

    def test_document_incoming_route_process(self):
        "Test document incoming route with JSON"

        client = self.client()

        with patch.object(self.Document, 'process') as process:
            response = client.post(
                f'/{self.db_name}/document_incoming'
                '?process=1&type=document_incoming',
                data=b'data',
                headers={
                    'Authorization': f'bearer {self.key}',
                    })
            process.assert_called_once()
            self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        @with_transaction()
        def clean():
            pool = Pool()
            Document = pool.get('document.incoming')
            document, = Document.search([])
            Document.delete([document])
            Transaction().commit()
        clean()


del ModuleTestCase, RouteTestCase

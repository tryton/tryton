# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
import json
from base64 import b64encode
from decimal import Decimal

from trytond.pool import Pool
from trytond.protocols.jsonrpc import JSONDecoder, JSONEncoder, JSONRequest
from trytond.protocols.wrappers import (
    HTTPStatus, Response, user_application, with_pool, with_transaction)
from trytond.protocols.xmlrpc import XMLRequest, client
from trytond.tests.test_tryton import Client, RouteTestCase, TestCase
from trytond.tools.immutabledict import ImmutableDict
from trytond.wsgi import TrytondWSGI


def _identity(x):
    return x


class DumpsLoadsMixin:

    def dumps_loads(self, value, test=_identity):
        raise NotImplementedError

    def test_datetime(self):
        'Test datetime'
        self.dumps_loads(datetime.datetime.now())

    def test_date(self):
        'Test date'
        self.dumps_loads(datetime.date.today())

    def test_time(self):
        'Test time'
        self.dumps_loads(datetime.datetime.now().time())

    def test_timedelta(self):
        "Test timedelta"
        self.dumps_loads(datetime.timedelta(days=1, seconds=10))

    def test_bytes(self):
        'Test bytes'
        self.dumps_loads(bytes(b'foo'))
        self.dumps_loads(bytearray(b'foo'))

    def test_decimal(self):
        'Test Decimal'
        self.dumps_loads(Decimal('3.141592653589793'))

    def test_biginteger(self):
        "Test BigInteger"
        self.dumps_loads(client.MAXINT + 1)

    def test_immutable_dict(self):
        "Test ImmutableDict"
        self.dumps_loads(ImmutableDict(foo='bar'))

    def test_set(self):
        "Test set"
        self.dumps_loads(set(range(10)), list)

    def test_frozenset(self):
        "Test set"
        self.dumps_loads(frozenset(range(10)), list)

    def test_none(self):
        'Test None'
        self.dumps_loads(None)


class JSONTestCase(DumpsLoadsMixin, TestCase):
    'Test JSON'

    def test_json_request(self):
        req = JSONRequest.from_values(
            data=b'{"method": "method", "params": ["foo", "bar"]}',
            content_type='text/json',
            )
        self.assertEqual(req.parsed_data,
            {'method': 'method', 'params': ['foo', 'bar']})
        self.assertEqual(req.rpc_method, 'method')
        self.assertEqual(req.rpc_params, ['foo', 'bar'])

    def dumps_loads(self, value, type=_identity):
        self.assertEqual(json.loads(
                json.dumps(value, cls=JSONEncoder),
                object_hook=JSONDecoder()),
            type(value))


class XMLTestCase(DumpsLoadsMixin, TestCase):
    'Test XML'

    def test_xml_request(self):
        req = XMLRequest.from_values(
            data=b"""<?xml version='1.0'?>
            <methodCall>
                <methodName>method</methodName>
                <params>
                    <param>
                        <value><string>foo</string></value>
                    </param>
                    <param>
                        <value><string>bar</string></value>
                    </param>
                </params>
            </methodCall>""",
            content_type='text/xml')
        self.assertEqual(req.parsed_data, (('foo', 'bar'), 'method'))
        self.assertEqual(req.rpc_method, 'method')
        self.assertEqual(req.rpc_params, ('foo', 'bar'))

    def dumps_loads(self, value, type=_identity):
        s = client.dumps((value,), allow_none=True)
        (result,), _ = client.loads(s)
        self.assertEqual(result, type(value))

    def test_decimal_class_load(self):
        "Test load Decimal as __class__"
        s = """<params><param><value>
            <struct>
                <member>
                    <name>__class__</name>
                    <value><string>Decimal</string></value>
                </member>
                <member>
                    <name>decimal</name>
                    <value><string>3.141592653589793</string></value>
                </member>
            </struct>
            </value></param></params>"""
        result, _ = client.loads(s)
        result, = result
        self.assertEqual(result, Decimal('3.141592653589793'))


class UserApplication(RouteTestCase):
    module = 'res'

    @classmethod
    def setUpDatabase(cls):
        pool = Pool()
        User = pool.get('res.user')
        UserApplication = pool.get('res.user.application')

        UserApplication.application.selection.append(('test', "Test"))

        User.create([{
                    'login': 'user',
                    'applications': [('create', [{
                                    'key': 'secret_key',
                                    'application': 'test',
                                    'state': 'validated',
                                    }])],
                    }])

    def test_authorization_bearer(self):
        app = TrytondWSGI()
        test_application = user_application('test')

        @app.route('/<database_name>/test/user_application')
        @with_pool
        @with_transaction()
        @test_application
        def _route(request, pool):
            return ''

        client = Client(app, Response)
        response = client.get(
            f'/{self.db_name}/test/user_application',
            headers=[
                ('Authorization', 'bearer secret_key'),
                ])
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_authorization_basic(self):
        app = TrytondWSGI()
        test_application = user_application('test')

        @app.route('/<database_name>/test/user_application')
        @with_pool
        @with_transaction()
        @test_application
        def _route(request, pool):
            return ''

        client = Client(app, Response)
        auth = b64encode(b':secret_key').decode('ascii')
        response = client.get(
            f'/{self.db_name}/test/user_application',
            headers=[
                ('Authorization', f'basic {auth}'),
                ])
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_authorization_bad_auth(self):
        app = TrytondWSGI()
        test_application = user_application('test')

        @app.route('/<database_name>/test/user_application')
        @with_pool
        @with_transaction()
        @test_application
        def _route(request, pool):
            return ''

        client = Client(app, Response)
        response = client.get(
            f'/{self.db_name}/test/user_application',
            headers=[
                ('Authorization', 'bearer foo'),
                ])
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
import json
import unittest
from decimal import Decimal

from trytond.protocols.jsonrpc import JSONDecoder, JSONEncoder, JSONRequest
from trytond.protocols.xmlrpc import XMLRequest, client
from trytond.tools.immutabledict import ImmutableDict


class DumpsLoadsMixin:

    def dumps_loads(self, value):
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

    def test_none(self):
        'Test None'
        self.dumps_loads(None)


class JSONTestCase(DumpsLoadsMixin, unittest.TestCase):
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

    def dumps_loads(self, value):
        self.assertEqual(json.loads(
                json.dumps(value, cls=JSONEncoder),
                object_hook=JSONDecoder()), value)


class XMLTestCase(DumpsLoadsMixin, unittest.TestCase):
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

    def dumps_loads(self, value):
        s = client.dumps((value,), allow_none=True)
        result, _ = client.loads(s)
        result, = result
        self.assertEqual(value, result)

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

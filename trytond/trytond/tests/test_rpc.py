# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from unittest.mock import Mock, DEFAULT, call

from trytond.tests.test_tryton import with_transaction, activate_module
from trytond.rpc import RPC
from trytond.transaction import Transaction


class RPCTestCase(unittest.TestCase):
    "Test RPC"

    @classmethod
    def setUpClass(cls):
        activate_module('ir')

    @with_transaction()
    def test_simple(self):
        "Test simple"
        rpc = RPC(check_access=False)
        self.assertEqual(
            rpc.convert(None, 'foo', {}),
            (['foo'], {}, {}, None))

    @with_transaction()
    def test_keyword_argument(self):
        "Test keyword argument"
        rpc = RPC(check_access=False)
        self.assertEqual(
            rpc.convert(None, 'foo', bar=True, context={}),
            (['foo'], {'bar': True}, {}, None))

    @with_transaction()
    def test_clean_context(self):
        "Test clean context"
        rpc = RPC(check_access=False)
        self.assertEqual(
            rpc.convert(None, {'_foo': True, '_datetime': None}),
            ([], {}, {'_datetime': None}, None))

    @with_transaction()
    def test_timestamp(self):
        "Test context timestamp"
        rpc = RPC(check_access=False)
        self.assertEqual(
            rpc.convert(None, {'_timestamp': 'test'}),
            ([], {}, {}, 'test'))

    @with_transaction()
    def test_instantiate(self):
        "Test instantiate"

        def side_effect(*args, **kwargs):
            self.assertEqual(Transaction().context, {'test': True})
            return DEFAULT

        rpc = RPC(instantiate=0, check_access=True)
        obj = Mock()
        obj.return_value = instance = Mock()
        obj.side_effect = side_effect

        # Integer
        self.assertEqual(
            rpc.convert(obj, 1, {'test': True}),
            ([instance], {}, {'test': True, '_check_access': True}, None))
        obj.assert_called_once_with(1)

        obj.reset_mock()

        # Dictionary
        self.assertEqual(
            rpc.convert(obj, {'foo': 'bar'}, {'test': True}),
            ([instance], {}, {'test': True, '_check_access': True}, None))
        obj.assert_called_once_with(foo='bar')

        obj.reset_mock()
        obj.browse.return_value = instances = Mock()

        # List
        self.assertEqual(
            rpc.convert(obj, [1, 2, 3], {'test': True}),
            ([instances], {}, {'test': True, '_check_access': True}, None))
        obj.browse.assert_called_once_with([1, 2, 3])

    @with_transaction()
    def test_instantiate_unique(self):
        "Test instantiate unique"
        rpc = RPC(instantiate=0, unique=True)
        obj = Mock()

        rpc.convert(obj, [1, 2], {})
        obj.browse.assert_called_once_with([1, 2])

        obj.reset_mock()

        with self.assertRaises(ValueError):
            rpc.convert(obj, [1, 1], {})

    @with_transaction()
    def test_instantiate_slice(self):
        "Test instantiate with slice"
        rpc = RPC(instantiate=slice(0, 2), check_access=False)
        obj = Mock()
        obj.return_value = instance = Mock()

        self.assertEqual(
            rpc.convert(obj, 1, 2, {}),
            ([instance, instance], {}, {}, None))
        obj.assert_has_calls([call(1), call(2)])

    @with_transaction()
    def test_check_access(self):
        "Test check_access"
        rpc_no_access = RPC(check_access=False)
        self.assertEqual(
            rpc_no_access.convert(None, {}),
            ([], {}, {}, None))

        rpc_with_access = RPC(check_access=True)
        self.assertEqual(
            rpc_with_access.convert(None, {}),
            ([], {}, {'_check_access': True}, None))


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(RPCTestCase)

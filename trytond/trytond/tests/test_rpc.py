# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from unittest.mock import DEFAULT, Mock, call

from trytond.protocols.wrappers import exceptions
from trytond.rpc import RPC
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)
from trytond.transaction import Transaction


class RPCTestCase(TestCase):
    "Test RPC"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
    def test_wrong_context_type(self):
        "Test wrong context type"
        rpc = RPC()
        with self.assertRaisesRegex(
                exceptions.UnprocessableEntity,
                "context must be a dictionary"):
            rpc.convert(None, context=None)

    @with_transaction()
    def test_missing_context(self):
        "Test missing context"
        rpc = RPC()
        with self.assertRaisesRegex(
                exceptions.UnprocessableEntity,
                "Missing context argument"):
            rpc.convert(None)

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

        with self.assertRaises(exceptions.UnprocessableEntity):
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

    @with_transaction()
    def test_size_limits_integer(self):
        "Test size_limits integer"
        obj = Mock()
        rpc = RPC(size_limits={0: 42})

        rpc.convert(obj, list(range(10)), {})

        with self.assertRaises(exceptions.RequestEntityTooLarge):
            rpc.convert(obj, list(range(43)), {})

    @with_transaction()
    def test_size_limits_slice(self):
        "Test size_limits slice"
        obj = Mock()
        rpc = RPC(size_limits={(0, None, 2): 42})

        rpc.convert(obj, list(range(10)), None, list(range(10)), {})

        with self.assertRaises(exceptions.RequestEntityTooLarge):
            rpc.convert(obj, list(range(30)), None, list(range(30)), {})

    @with_transaction()
    def test_size_limits_integer_number(self):
        "Test size_limits integer number"
        obj = Mock()
        rpc = RPC(size_limits={0: 42})

        rpc.convert(obj, 10, {})

        with self.assertRaises(exceptions.RequestEntityTooLarge):
            rpc.convert(obj, 43, {})

    @with_transaction()
    def test_size_limits_slice_number(self):
        "Test size_limits slice"
        obj = Mock()
        rpc = RPC(size_limits={(0, None, 2): 42})

        rpc.convert(obj, 10, None, 10, {})

        with self.assertRaises(exceptions.RequestEntityTooLarge):
            rpc.convert(obj, 30, None, 30, {})

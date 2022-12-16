# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import shutil
import tempfile
import unittest

from sql import Literal

from trytond.config import config
from trytond.model.exceptions import RequiredValidationError
from trytond.model import fields
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction

cast = fields.Binary.cast


class FieldBinaryTestCase(unittest.TestCase):
    "Test Field Binary"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def setUp(self):
        path = config.get('database', 'path')
        dtemp = tempfile.mkdtemp()
        config.set('database', 'path', dtemp)
        self.addCleanup(config.set, 'database', 'path', path)
        self.addCleanup(shutil.rmtree, dtemp)

    @with_transaction()
    def test_create(self):
        "Test create binary"
        Binary = Pool().get('test.binary')

        binary, = Binary.create([{
                    'binary': cast(b'foo'),
                    }])

        self.assertEqual(binary.binary, cast(b'foo'))

    @with_transaction()
    def test_create_without_default(self):
        "Test create binary without default"
        Binary = Pool().get('test.binary')

        binary, = Binary.create([{}])

        self.assertEqual(binary.binary, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create binary with default"
        Binary = Pool().get('test.binary_default')

        binary, = Binary.create([{}])

        self.assertEqual(binary.binary, cast(b'default'))

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create binary without value"
        Binary = Pool().get('test.binary_required')

        with self.assertRaises(RequiredValidationError):
            binary, = Binary.create([{}])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create binary with default"
        Binary = Pool().get('test.binary_default')

        binary, = Binary.create([{
                    'binary': cast(b'baz'),
                    }])

        self.assertEqual(binary.binary, cast(b'baz'))

    @with_transaction()
    def test_create_required_with_empty(self):
        "Test create binary with empty"
        Binary = Pool().get('test.binary_required')

        with self.assertRaises(RequiredValidationError):
            binary, = Binary.create([{
                        'binary': cast(b''),
                        }])

    @with_transaction()
    def test_create_filestorage(self):
        "Test create binary with filestorage"
        Binary = Pool().get('test.binary_filestorage')

        binary, = Binary.create([{
                    'binary': cast(b'foo'),
                    }])

        self.assertEqual(binary.binary, cast(b'foo'))
        self.assertTrue(binary.binary_id)

    @with_transaction()
    def test_create_empty_filestorage(self):
        "Test create binary empty with filestorage"
        Binary = Pool().get('test.binary_filestorage')

        binary, = Binary.create([{
                    'binary': None,
                    }])

        self.assertEqual(binary.binary, None)
        self.assertEqual(binary.binary_id, None)

    @with_transaction()
    def test_create_with_sql_value(self):
        "Test create binary with SQL value"
        Binary = Pool().get('test.binary')

        binary, = Binary.create([{
                    'binary': Literal('foo'),
                    }])

        self.assertEqual(binary.binary, cast(b'foo'))

    @with_transaction()
    def test_read_size(self):
        "Test read binary size"
        Binary = Pool().get('test.binary')
        binary, = Binary.create([{
                    'binary': cast(b'foo'),
                    }])

        with Transaction().set_context({'test.binary.binary': 'size'}):
            binary = Binary(binary.id)

        self.assertEqual(binary.binary, len(b'bar'))

    @with_transaction()
    def test_read_size_filestorage(self):
        "Test read binary size with filestorage"
        Binary = Pool().get('test.binary_filestorage')
        binary, = Binary.create([{
                    'binary': cast(b'foo'),
                    }])

        with Transaction().set_context(
                {'test.binary_filestorage.binary': 'size'}):
            binary = Binary(binary.id)

        self.assertEqual(binary.binary, len(b'bar'))

    @with_transaction()
    def test_write(self):
        "Test write binary"
        Binary = Pool().get('test.binary')
        binary, = Binary.create([{
                    'binary': cast(b'foo'),
                    }])

        Binary.write([binary], {
                'binary': cast(b'bar'),
                })

        self.assertEqual(binary.binary, cast(b'bar'))

    @with_transaction()
    def test_write_filestorage(self):
        "Test write binary with filestorage"
        Binary = Pool().get('test.binary_filestorage')
        binary, = Binary.create([{
                    'binary': cast(b'foo'),
                    }])

        Binary.write([binary], {
                'binary': cast(b'bar'),
                })

        self.assertEqual(binary.binary, cast(b'bar'))

    @with_transaction()
    def test_write_empty_filestorage(self):
        "Test write binary empty with filestorage"
        Binary = Pool().get('test.binary_filestorage')
        binary, = Binary.create([{
                    'binary': cast(b'foo'),
                    }])

        Binary.write([binary], {
                'binary': None,
                })

        self.assertEqual(binary.binary, None)
        self.assertEqual(binary.binary_id, None)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldBinaryTestCase)

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond import backend
from trytond.exceptions import UserError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction


class FieldDictTestCase(unittest.TestCase):
    "Test Field Dict"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def create_schema(self):
        DictSchema = Pool().get('test.dict.schema')

        DictSchema.create([{
                    'name': 'a',
                    'string': 'A',
                    'type_': 'integer',
                    }, {
                    'name': 'b',
                    'string': 'B',
                    'type_': 'integer',
                    }, {
                    'name': 'type',
                    'string': 'Type',
                    'type_': 'selection',
                    'selection': ('arabic: Arabic\n'
                        'hexa: Hexadecimal'),
                    }])

    def set_jsonb(self, table):
        cursor = Transaction().connection.cursor()
        cursor.execute('ALTER TABLE "%s" '
            'ALTER COLUMN dico TYPE json USING dico::json' % table)

    @with_transaction()
    def test_create(self):
        "Test create dict"
        Dict = Pool().get('test.dict')
        self.create_schema()

        dict_, = Dict.create([{
                    'dico': {'a': 1, 'b': 2},
                    }])

        self.assertDictEqual(dict_.dico, {'a': 1, 'b': 2})

    @with_transaction()
    def test_create_without_schema(self):
        "Test create dict without schema"
        Dict = Pool().get('test.dict')

        dict_, = Dict.create([{
                    'dico': {'z': 26},
                    }])

        self.assertDictEqual(dict_.dico, {'z': 26})

    @with_transaction()
    def test_create_without_default(self):
        "Test create dict without default"
        Dict = Pool().get('test.dict')
        self.create_schema()

        dict_, = Dict.create([{}])

        self.assertEqual(dict_.dico, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create dict without default"
        Dict = Pool().get('test.dict_default')
        self.create_schema()

        dict_, = Dict.create([{}])

        self.assertDictEqual(dict_.dico, {'a': 1})

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create dict required with value"
        Dict = Pool().get('test.dict_required')
        self.create_schema()

        dict_, = Dict.create([{
                    'dico': {'a': 1},
                    }])

        self.assertDictEqual(dict_.dico, {'a': 1})

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create dict required without value"
        Dict = Pool().get('test.dict_required')
        self.create_schema()

        with self.assertRaises(UserError):
            Dict.create([{}])

    @with_transaction()
    def test_create_required_with_empty(self):
        "Test create dict required without value"
        Dict = Pool().get('test.dict_required')
        self.create_schema()

        with self.assertRaises(UserError):
            Dict.create([{
                        'dico': {},
                        }])

    @with_transaction()
    def test_create_selection(self):
        "Test create dict with selection"
        Dict = Pool().get('test.dict')
        self.create_schema()

        dict_, = Dict.create([{
                    'dico': {'type': 'arabic'},
                    }])

        self.assertDictEqual(dict_.dico, {'type': 'arabic'})

    @with_transaction()
    @unittest.skipIf(
        backend.name() != 'postgresql', 'jsonb only suported by postgresql')
    def test_create_jsonb(self):
        "Test create dict as jsonb"
        connection = Transaction().connection
        Database = backend.get('Database')
        if Database().get_version(connection) < (9, 2):
            return

        Dict = Pool().get('test.dict_jsonb')
        self.set_jsonb(Dict._table)

        dict_, = Dict.create([{
                    'dico': {'a': 1, 'b': 2},
                    }])

        self.assertDictEqual(dict_.dico, {'a': 1, 'b': 2})

    @with_transaction()
    def test_write(self):
        "Test write dict"
        Dict = Pool().get('test.dict')
        self.create_schema()
        dict_, = Dict.create([{
                    'dico': {'a': 1, 'b': 2},
                    }])

        Dict.write([dict_], {
                'dico': {'a': 2},
                })

        self.assertDictEqual(dict_.dico, {'a': 2})

    @with_transaction()
    def test_write_wthout_schema(self):
        "Test write dict without schema"
        Dict = Pool().get('test.dict')
        dict_, = Dict.create([{
                    'dico': {'z': 26},
                    }])

        Dict.write([dict_], {
                'dico': {'y': 1},
                })

        self.assertDictEqual(dict_.dico, {'y': 1})

    @with_transaction()
    @unittest.skipIf(
        backend.name() != 'postgresql', 'jsonb only suported by postgresql')
    def test_write_jsonb(self):
        "Test write dict as jsonb"
        connection = Transaction().connection
        Database = backend.get('Database')
        if Database().get_version(connection) < (9, 2):
            return

        Dict = Pool().get('test.dict_jsonb')
        self.set_jsonb(Dict._table)
        dict_, = Dict.create([{
                    'dico': {'a': 1, 'b': 2},
                    }])

        Dict.write([dict_], {'dico': {'z': 26}})

        self.assertDictEqual(dict_.dico, {'z': 26})

    @with_transaction()
    def test_string(self):
        "Test string dict"
        Dict = Pool().get('test.dict')
        self.create_schema()

        dict_, = Dict.create([{
                    'dico': {'a': 1, 'type': 'arabic'},
                    }])

        self.assertDictEqual(dict_.dico_string, {'a': 1, 'type': "Arabic"})

    @with_transaction()
    def test_string_keys(self):
        "Test string keys dict"
        Dict = Pool().get('test.dict')
        self.create_schema()

        dict_, = Dict.create([{
                    'dico': {'a': 1, 'type': 'arabic'},
                    }])

        self.assertDictEqual(
            dict_.dico_string_keys, {'a': 'A', 'type': "Type"})


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldDictTestCase)

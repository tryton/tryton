# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond import backend
from trytond.model.dictschema import SelectionError
from trytond.model.exceptions import RequiredValidationError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction

from .test_field_char import UnaccentedTestCase


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

        with self.assertRaises(RequiredValidationError):
            Dict.create([{}])

    @with_transaction()
    def test_create_required_with_empty(self):
        "Test create dict required without value"
        Dict = Pool().get('test.dict_required')
        self.create_schema()

        with self.assertRaises(RequiredValidationError):
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
    def test_invalid_selection_schema(self):
        "Test invalid selection schema"
        pool = Pool()
        DictSchema = pool.get('test.dict.schema')

        with self.assertRaises(SelectionError):
            DictSchema.create([{
                        'name': 'selection',
                        'string': "Selection",
                        'type_': 'selection',
                        'selection': 'foo',
                        }])

    @with_transaction()
    @unittest.skipIf(
        backend.name() != 'postgresql', 'jsonb only supported by postgresql')
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
        backend.name() != 'postgresql', 'jsonb only supported by postgresql')
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
    def test_search_element_equals(self):
        "Test search dict element equals"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': 'Foo'},
                    }])

        dicts_foo = Dict.search([
                ('dico.a', '=', "Foo"),
                ])
        dicts_bar = Dict.search([
                ('dico.a', '=', "Bar"),
                ])
        dicts_foo_b = Dict.search([
                ('dico.b', '=', "Foo"),
                ])

        self.assertListEqual(dicts_foo, [dict_])
        self.assertListEqual(dicts_bar, [])
        self.assertListEqual(dicts_foo_b, [])

    @with_transaction()
    def test_search_element_equals_none(self):
        "Test search dict element equals None"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': None},
                    }])

        dicts = Dict.search([
                ('dico.a', '=', None),
                ])

        self.assertListEqual(dicts, [dict_])

    @with_transaction()
    def test_search_non_element_equals_none(self):
        "Test search dict non element equals None"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Foo"},
                    }])

        dicts = Dict.search([
                ('dico.b', '=', None),
                ])

        self.assertListEqual(dicts, [dict_])

    @with_transaction()
    def test_search_element_non_equals(self):
        "Test search dict element non equals"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Foo"},
                    }])

        dicts_foo = Dict.search([
                ('dico.a', '!=', "Foo"),
                ])
        dicts_bar = Dict.search([
                ('dico.a', '!=', "Bar"),
                ])
        dicts_foo_b = Dict.search([
                ('dico.b', '!=', "Foo"),
                ])

        self.assertListEqual(dicts_foo, [])
        self.assertListEqual(dicts_bar, [dict_])
        self.assertListEqual(dicts_foo_b, [])

    @with_transaction()
    def test_search_element_non_equals_none(self):
        "Test search dict element non equals None"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': None},
                    }])

        dicts = Dict.search([
                ('dico.a', '!=', None),
                ])

        self.assertListEqual(dicts, [])

    @with_transaction()
    def test_search_non_element_non_equals_none(self):
        "Test search dict non element non equals None"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Foo"},
                    }])

        dicts = Dict.search([
                ('dico.b', '!=', None),
                ])

        self.assertListEqual(dicts, [])

    @with_transaction()
    def test_search_element_equals_true(self):
        "Test search dict element equals True"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict1, dict2 = Dict.create([{
                    'dico': {'a': True},
                    }, {
                    'dico': {'a': False},
                    }])

        dicts = Dict.search([
                ('dico.a', '=', True),
                ])

        self.assertListEqual(dicts, [dict1])

    @with_transaction()
    def test_search_element_equals_false(self):
        "Test search dict element equals False"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict1, dict2 = Dict.create([{
                    'dico': {'a': True},
                    }, {
                    'dico': {'a': False},
                    }])

        dicts = Dict.search([
                ('dico.a', '=', False),
                ])

        self.assertListEqual(dicts, [dict2])

    @with_transaction()
    def test_search_element_non_equals_true(self):
        "Test search dict element non equals True"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': True},
                    }])

        dicts = Dict.search([
                ('dico.a', '!=', True),
                ])

        self.assertListEqual(dicts, [])

    @with_transaction()
    def test_search_element_in(self):
        "Test search dict element in"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Foo"},
                    }])

        dicts_foo = Dict.search([
                ('dico.a', 'in', ["Foo"]),
                ])
        dicts_bar = Dict.search([
                ('dico.a', 'in', ["Bar"]),
                ])
        dicts_empty = Dict.search([
                ('dico.a', 'in', []),
                ])
        dicts_foo_b = Dict.search([
                ('dico.b', 'in', ["Foo"]),
                ])

        self.assertListEqual(dicts_foo, [dict_])
        self.assertListEqual(dicts_bar, [])
        self.assertListEqual(dicts_empty, [])
        self.assertListEqual(dicts_foo_b, [])

    @with_transaction()
    def test_search_element_in_none(self):
        "Test search dict element in [None]"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': None},
                    }])

        dicts = Dict.search([
                ('dico.a', 'in', [None]),
                ])

        self.assertListEqual(dicts, [dict_])

    @with_transaction()
    def test_search_element_not_in(self):
        "Test search dict element not in"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Foo"},
                    }])

        dicts_foo = Dict.search([
                ('dico.a', 'not in', ["Foo"]),
                ])
        dicts_bar = Dict.search([
                ('dico.a', 'not in', ["Bar"]),
                ])
        dicts_empty = Dict.search([
                ('dico.a', 'not in', []),
                ])
        dicts_foo_b = Dict.search([
                ('dico.b', 'not in', ["Foo"]),
                ])

        self.assertListEqual(dicts_foo, [])
        self.assertListEqual(dicts_bar, [dict_])
        self.assertListEqual(dicts_empty, [dict_])
        self.assertListEqual(dicts_foo_b, [])

    @with_transaction()
    def test_search_element_not_in_none(self):
        "Test search dict element not in [None]"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': None},
                    }])

        dicts = Dict.search([
                ('dico.a', 'not in', [None]),
                ])

        self.assertListEqual(dicts, [])

    @with_transaction()
    def test_search_element_less(self):
        "Test search dict element less than"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': 1.1},
                    }])

        dicts_5 = Dict.search([
                ('dico.a', '<', 5),
                ])
        dicts__5 = Dict.search([
                ('dico.a', '<', -5),
                ])
        dicts_1_1 = Dict.search([
                ('dico.a', '<', 1.1),
                ])

        self.assertListEqual(dicts_5, [dict_])
        self.assertListEqual(dicts__5, [])
        self.assertListEqual(dicts_1_1, [])

    @with_transaction()
    def test_search_element_less_equals(self):
        "Test search dict element less than or equals"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': 1.1},
                    }])

        dicts_5 = Dict.search([
                ('dico.a', '<=', 5),
                ])
        dicts__5 = Dict.search([
                ('dico.a', '<=', -5),
                ])
        dicts_1_1 = Dict.search([
                ('dico.a', '<=', 1.1),
                ])

        self.assertListEqual(dicts_5, [dict_])
        self.assertListEqual(dicts__5, [])
        self.assertListEqual(dicts_1_1, [dict_])

    @with_transaction()
    def test_search_element_greater(self):
        "Test search dict element greater than"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': 1.1},
                    }])

        dicts_5 = Dict.search([
                ('dico.a', '>', 5),
                ])
        dicts__5 = Dict.search([
                ('dico.a', '>', -5),
                ])
        dicts_1_1 = Dict.search([
                ('dico.a', '>', 1.1),
                ])

        self.assertListEqual(dicts_5, [])
        self.assertListEqual(dicts__5, [dict_])
        self.assertListEqual(dicts_1_1, [])

    @with_transaction()
    def test_search_element_greater_equals(self):
        "Test search dict element greater than or equals"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': 1.1},
                    }])

        dicts_5 = Dict.search([
                ('dico.a', '>=', 5),
                ])
        dicts__5 = Dict.search([
                ('dico.a', '>=', -5),
                ])
        dicts_1_1 = Dict.search([
                ('dico.a', '>=', 1.1),
                ])

        self.assertListEqual(dicts_5, [])
        self.assertListEqual(dicts__5, [dict_])
        self.assertListEqual(dicts_1_1, [dict_])

    @with_transaction()
    def test_search_element_like(self):
        "Test search dict element like"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Bar"},
                    }])

        dicts_bar = Dict.search([
                ('dico.a', 'like', "Bar"),
                ])
        dicts_b = Dict.search([
                ('dico.a', 'like', "B%"),
                ])
        dicts_foo = Dict.search([
                ('dico.a', 'like', "Foo"),
                ])
        dicts_f = Dict.search([
                ('dico.a', 'like', "F%"),
                ])
        dicts_b_b = Dict.search([
                ('dico.b', 'like', "B%"),
                ])

        self.assertListEqual(dicts_bar, [dict_])
        self.assertListEqual(dicts_b, [dict_])
        self.assertListEqual(dicts_foo, [])
        self.assertListEqual(dicts_f, [])
        self.assertListEqual(dicts_b_b, [])

    @with_transaction()
    def test_search_element_ilike(self):
        "Test search dict element ilike"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Bar"},
                    }])

        dicts_bar = Dict.search([
                ('dico.a', 'ilike', "bar"),
                ])
        dicts_b = Dict.search([
                ('dico.a', 'ilike', "b%"),
                ])
        dicts_foo = Dict.search([
                ('dico.a', 'ilike', "foo"),
                ])
        dicts_f = Dict.search([
                ('dico.a', 'ilike', "f%"),
                ])
        dicts_b_b = Dict.search([
                ('dico.b', 'ilike', "b%"),
                ])

        self.assertListEqual(dicts_bar, [dict_])
        self.assertListEqual(dicts_b, [dict_])
        self.assertListEqual(dicts_foo, [])
        self.assertListEqual(dicts_f, [])
        self.assertListEqual(dicts_b_b, [])

    @with_transaction()
    def test_search_element_not_like(self):
        "Test search dict element not like"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Bar"},
                    }])

        dicts_bar = Dict.search([
                ('dico.a', 'not like', "Bar"),
                ])
        dicts_b = Dict.search([
                ('dico.a', 'not like', "B%"),
                ])
        dicts_foo = Dict.search([
                ('dico.a', 'not like', "Foo"),
                ])
        dicts_f = Dict.search([
                ('dico.a', 'not like', "F%"),
                ])
        dicts_b_b = Dict.search([
                ('dico.b', 'not like', "B%"),
                ])

        self.assertListEqual(dicts_bar, [])
        self.assertListEqual(dicts_b, [])
        self.assertListEqual(dicts_foo, [dict_])
        self.assertListEqual(dicts_f, [dict_])
        self.assertListEqual(dicts_b_b, [])

    @with_transaction()
    def test_search_element_not_ilike(self):
        "Test search dict element not ilike"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')

        dict_, = Dict.create([{
                    'dico': {'a': "Bar"},
                    }])

        dicts_bar = Dict.search([
                ('dico.a', 'not ilike', "bar"),
                ])
        dicts_b = Dict.search([
                ('dico.a', 'not ilike', "b%"),
                ])
        dicts_foo = Dict.search([
                ('dico.a', 'not ilike', "foo"),
                ])
        dicts_f = Dict.search([
                ('dico.a', 'not ilike', "f%"),
                ])
        dicts_b_b = Dict.search([
                ('dico.b', 'not ilike', "b%"),
                ])

        self.assertListEqual(dicts_bar, [])
        self.assertListEqual(dicts_b, [])
        self.assertListEqual(dicts_foo, [dict_])
        self.assertListEqual(dicts_f, [dict_])
        self.assertListEqual(dicts_b_b, [])

    @with_transaction()
    @unittest.skipIf(
        backend.name() != 'postgresql', 'jsonb only supported by postgresql')
    def test_search_element_jsonb(self):
        "Test search dict element on jsonb"
        connection = Transaction().connection
        Database = backend.get('Database')
        if Database().get_version(connection) < (9, 2):
            return

        pool = Pool()
        Dict = pool.get('test.dict_noschema')
        self.set_jsonb(Dict._table)
        dict_, = Dict.create([{
                    'dico': {'a': 'Foo'},
                    }])

        dicts = Dict.search([
                ('dico.a', '=', "Foo"),
                ])

        self.assertListEqual(dicts, [dict_])

    @with_transaction()
    def test_search_order_element(self):
        "Test search order by dict element"
        pool = Pool()
        Dict = pool.get('test.dict_noschema')
        for value in [5, 3, 2]:
            Dict.create([{'dico': {'a': 5 - value, 'b': value}}])

        records = Dict.search([], order=[('dico.b', 'ASC')])
        values = [r.dico['b'] for r in records]

        self.assertListEqual(values, [2, 3, 5])

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


@unittest.skipUnless(backend.name() == 'postgresql',
    "unaccent works only on postgresql")
class FieldDictUnaccentedTestCase(UnaccentedTestCase):
    "Test Field Dict with unaccented searched"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')
        super().setUpClass()

    @with_transaction()
    def test_search_unaccented_off(self):
        "Test searches without the unaccented feature"
        pool = Pool()
        Dict = pool.get('test.dict_unaccented_off')
        dict_, = Dict.create([{
                    'dico': {'a': 'Stéphanie'},
                    }])

        dicts = Dict.search([
                ('dico.a', 'ilike', 'Stephanie'),
                ])

        self.assertListEqual(dicts, [])

    @with_transaction()
    def test_search_accented(self):
        "Test searches of accented value"
        pool = Pool()
        Dict = pool.get('test.dict_unaccented_on')
        dict_, = Dict.create([{
                    'dico': {'a': 'Stéphanie'},
                    }])

        dicts = Dict.search([
                ('dico.a', 'ilike', 'Stephanie'),
                ])

        self.assertListEqual(dicts, [dict_])

    @with_transaction()
    def test_search_unaccented(self):
        "Test searches of unaccented value"
        pool = Pool()
        Dict = pool.get('test.dict_unaccented_on')
        dict_, = Dict.create([{
                    'dico': {'a': 'Stephanie'},
                    }])

        dicts = Dict.search([
                ('dico.a', 'ilike', 'Stéphanie'),
                ])

        self.assertListEqual(dicts, [dict_])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldDictTestCase)

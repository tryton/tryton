# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from sql import Literal

from trytond import backend
from trytond.model.exceptions import (
    ForbiddenCharValidationError, RequiredValidationError, SizeValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import (
    ExtensionTestCase, activate_module, with_transaction)
from trytond.transaction import Transaction


class CommonTestCaseMixin:

    @with_transaction()
    def test_create(self):
        "Test create char"
        Char = self.Char()

        char, char_none = Char.create([{
                    'char': "Test",
                    }, {
                    'char': None,
                    }])

        self.assertEqual(char.char, "Test")
        self.assertEqual(char_none.char, None)

    @with_transaction()
    def test_create_unicode(self):
        "Test create unicode"
        Char = self.Char()

        char, = Char.create([{
                    'char': "é",
                    }])

        self.assertEqual(char.char, "é")

    @with_transaction()
    def test_search_equals(self):
        "Test search char equals"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Foo",
                    }])

        chars_foo = Char.search([
                ('char', '=', "Foo"),
                ])
        chars_bar = Char.search([
                ('char', '=', "Bar"),
                ])

        self.assertListEqual(chars_foo, [char])
        self.assertListEqual(chars_bar, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search char equals None"
        Char = self.Char()
        char, = Char.create([{
                    'char': None,
                    }])

        chars = Char.search([
                ('char', '=', None),
                ])

        self.assertListEqual(chars, [char])

    @with_transaction()
    def test_search_equals_unicode(self):
        "Test search char equals unicode"
        Char = self.Char()
        char, = Char.create([{
                    'char': "é",
                    }])

        chars = Char.search([
                ('char', '=', "é"),
                ])

        self.assertListEqual(chars, [char])

    @with_transaction()
    def test_search_equals_non_unicode(self):
        "Test search char equals non unicode"
        Char = self.Char()
        char, = Char.create([{
                    'char': "é",
                    }])

        chars = Char.search([
                ('char', '=', "é"),
                ])

        self.assertListEqual(chars, [char])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search char non equals"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Foo",
                    }])

        chars_foo = Char.search([
                ('char', '!=', "Foo"),
                ])
        chars_bar = Char.search([
                ('char', '!=', "Bar"),
                ])

        self.assertListEqual(chars_foo, [])
        self.assertListEqual(chars_bar, [char])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search char non equals None"
        Char = self.Char()
        char, = Char.create([{
                    'char': None,
                    }])

        chars = Char.search([
                ('char', '!=', None),
                ])

        self.assertListEqual(chars, [])

    @with_transaction()
    def test_search_in(self):
        "Test search char in"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Foo",
                    }])

        chars_foo = Char.search([
                ('char', 'in', ["Foo"]),
                ])
        chars_bar = Char.search([
                ('char', 'in', ["Bar"]),
                ])
        chars_empty = Char.search([
                ('char', 'in', []),
                ])

        self.assertListEqual(chars_foo, [char])
        self.assertListEqual(chars_bar, [])
        self.assertListEqual(chars_empty, [])

    @with_transaction()
    def test_search_in_none(self):
        "Test search char in [None]"
        Char = self.Char()
        char, = Char.create([{
                    'char': None,
                    }])

        chars = Char.search([
                ('char', 'in', [None]),
                ])

        self.assertListEqual(chars, [char])

    @with_transaction()
    def test_search_not_in(self):
        "Test search char not in"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Foo",
                    }])

        chars_foo = Char.search([
                ('char', 'not in', ["Foo"]),
                ])
        chars_bar = Char.search([
                ('char', 'not in', ["Bar"]),
                ])
        chars_empty = Char.search([
                ('char', 'not in', []),
                ])

        self.assertListEqual(chars_foo, [])
        self.assertListEqual(chars_bar, [char])
        self.assertListEqual(chars_empty, [char])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search char not in [None]"
        Char = self.Char()
        char, = Char.create([{
                    'char': None,
                    }])

        chars = Char.search([
                ('char', 'not in', [None]),
                ])

        self.assertListEqual(chars, [])

    @with_transaction()
    def test_search_like(self):
        "Test search char like"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Bar",
                    }])

        chars_bar = Char.search([
                ('char', 'like', "Bar"),
                ])
        chars_b = Char.search([
                ('char', 'like', "B%"),
                ])
        chars_foo = Char.search([
                ('char', 'like', "Foo"),
                ])
        chars_f = Char.search([
                ('char', 'like', "F%"),
                ])

        self.assertListEqual(chars_bar, [char])
        self.assertListEqual(chars_b, [char])
        self.assertListEqual(chars_foo, [])
        self.assertListEqual(chars_f, [])

    @with_transaction()
    def test_search_ilike(self):
        "Test search char ilike"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Bar",
                    }])

        chars_bar = Char.search([
                ('char', 'ilike', "bar"),
                ])
        chars_b = Char.search([
                ('char', 'ilike', "b%"),
                ])
        chars_foo = Char.search([
                ('char', 'ilike', "foo"),
                ])
        chars_f = Char.search([
                ('char', 'ilike', "f%"),
                ])

        self.assertListEqual(chars_bar, [char])
        self.assertListEqual(chars_b, [char])
        self.assertListEqual(chars_foo, [])
        self.assertListEqual(chars_f, [])

    @with_transaction()
    def test_search_not_like(self):
        "Test search char not like"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Bar",
                    }])

        chars_bar = Char.search([
                ('char', 'not like', "Bar"),
                ])
        chars_b = Char.search([
                ('char', 'not like', "B%"),
                ])
        chars_foo = Char.search([
                ('char', 'not like', "Foo"),
                ])
        chars_f = Char.search([
                ('char', 'not like', "F%"),
                ])

        self.assertListEqual(chars_bar, [])
        self.assertListEqual(chars_b, [])
        self.assertListEqual(chars_foo, [char])
        self.assertListEqual(chars_f, [char])

    @with_transaction()
    def test_search_not_ilike(self):
        "Test search char not like"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Bar",
                    }])

        chars_bar = Char.search([
                ('char', 'not ilike', "bar"),
                ])
        chars_b = Char.search([
                ('char', 'not ilike', "b%"),
                ])
        chars_foo = Char.search([
                ('char', 'not ilike', "foo"),
                ])
        chars_f = Char.search([
                ('char', 'not ilike', "f%"),
                ])

        self.assertListEqual(chars_bar, [])
        self.assertListEqual(chars_b, [])
        self.assertListEqual(chars_foo, [char])
        self.assertListEqual(chars_f, [char])

    @with_transaction()
    def test_write_unicode(self):
        "Test write char unicode"
        Char = self.Char()
        char, = Char.create([{
                    'char': "Foo",
                    }])

        Char.write([char], {
                'char': "é",
                })

        self.assertEqual(char.char, "é")

    @with_transaction()
    def test_create_strip(self):
        "Test create with stripping"
        Char = self.Char()

        char, = Char.create([{
                    'char': " Foo ",
                    'char_lstripped': " Foo ",
                    'char_rstripped': " Foo ",
                    'char_unstripped': " Foo ",
                    }])

        read_record = Char(char.id)
        self.assertEqual(read_record.char, "Foo")
        self.assertEqual(read_record.char_lstripped, "Foo ")
        self.assertEqual(read_record.char_rstripped, " Foo")
        self.assertEqual(read_record.char_unstripped, " Foo ")

    @with_transaction()
    def test_write_strip(self):
        "Test write with stripping"
        Char = self.Char()

        char, = Char.create([{
                    'char': "Foo",
                    'char_lstripped': "Foo",
                    'char_rstripped': "Foo",
                    'char_unstripped': "Foo",
                    }])

        Char.write([char], {
                'char': " Bar ",
                'char_lstripped': " Bar ",
                'char_rstripped': " Bar ",
                'char_unstripped': " Bar ",
                })
        read_record = Char(char.id)
        self.assertEqual(read_record.char, "Bar")
        self.assertEqual(read_record.char_lstripped, "Bar ")
        self.assertEqual(read_record.char_rstripped, " Bar")
        self.assertEqual(read_record.char_unstripped, " Bar ")

    @with_transaction()
    def test_set_strip(self):
        "Test set with stripping"
        Char = self.Char()

        char = Char()

        char.char = " Foo "
        char.char_lstripped = " Foo "
        char.char_rstripped = " Foo "
        char.char_unstripped = " Foo "
        self.assertEqual(char.char, "Foo")
        self.assertEqual(char.char_lstripped, "Foo ")
        self.assertEqual(char.char_rstripped, " Foo")
        self.assertEqual(char.char_unstripped, " Foo ")


class FieldCharTestCase(unittest.TestCase, CommonTestCaseMixin):
    "Test Field Char"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def Char(self):
        return Pool().get('test.char')

    @with_transaction()
    def test_create_with_sql_value(self):
        "Test create with SQL value"
        Char = self.Char()

        char, = Char.create([{'char': Literal('Foo')}])

        self.assertEqual(char.char, "Foo")

    @with_transaction()
    def test_set_sql_value(self):
        "Test cannot set SQL value"
        Char = self.Char()

        char = Char()

        with self.assertRaises(ValueError):
            char.char = Literal('Foo')

    @with_transaction()
    def test_create_without_default(self):
        "Test create char without default"
        Char = Pool().get('test.char')

        char, = Char.create([{}])

        self.assertEqual(char.char, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create char without default"
        Char = Pool().get('test.char_default')

        char, = Char.create([{}])

        self.assertEqual(char.char, "Test")

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create char required with value"
        Char = Pool().get('test.char_required')

        char, = Char.create([{
                    'char': "Test",
                    }])

        self.assertEqual(char.char, "Test")

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create char required without value"
        Char = Pool().get('test.char_required')

        with self.assertRaises(RequiredValidationError):
            Char.create([{}])

    @with_transaction()
    def test_create_required_with_empty(self):
        "Test create char required with empty"
        Char = Pool().get('test.char_required')

        with self.assertRaises(RequiredValidationError):
            Char.create([{
                        'char': '',
                        }])

    @with_transaction()
    def test_create_size_valid(self):
        "Test create char with size"
        Char = Pool().get('test.char_size')

        char, = Char.create([{
                    'char': "Test",
                    }])

        self.assertEqual(char.char, "Test")

    @with_transaction()
    def test_create_size_invalid(self):
        "Test create char with invalid size"
        Char = Pool().get('test.char_size')

        with self.assertRaises(SizeValidationError):
            Char.create([{
                        'char': "foobar",
                        }])

    @with_transaction()
    def test_create_size_pyson_valid(self):
        "Test create char with PYSON size"
        Char = Pool().get('test.char_size_pyson')

        char, = Char.create([{
                    'char': "Test",
                    'size': 5,
                    }])

        self.assertEqual(char.char, "Test")

    @with_transaction()
    def test_create_size_pyson_invalid(self):
        "Test create char with invalid PYSON size"
        Char = Pool().get('test.char_size_pyson')

        with self.assertRaises(SizeValidationError):
            Char.create([{
                        'char': "foobar",
                        'size': 5,
                        }])

    @with_transaction()
    def test_create_size_pyson_none(self):
        "Test create char with PYSON size as None"
        pool = Pool()
        Char = pool.get('test.char_size_pyson')

        char, = Char.create([{
                    'char': "foo",
                    'size': None,
                    }])

    @with_transaction()
    def test_create_invalid_char(self):
        "Test create char with invalid char"
        Char = Pool().get('test.char')

        with self.assertRaises(ForbiddenCharValidationError):
            Char.create([{
                        'char': "foo\nbar",
                        }])

    @with_transaction()
    def test_write(self):
        "Test write char"
        Char = Pool().get('test.char')
        char, = Char.create([{
                    'char': "Foo",
                    }])

        Char.write([char], {
                'char': "Bar",
                })

        self.assertEqual(char.char, "Bar")

    @with_transaction()
    def test_write_none(self):
        "Test write char None"
        Char = Pool().get('test.char')
        char, = Char.create([{
                    'char': "Foo",
                    }])

        Char.write([char], {
                'char': None,
                })

        self.assertEqual(char.char, None)

    @with_transaction()
    def test_write_size_invalid(self):
        "Test write char with invalid size"
        Char = Pool().get('test.char_size')

        char, = Char.create([{
                    'char': "Test",
                    }])

        with self.assertRaises(SizeValidationError):
            Char.write([char], {
                    'char': 'foobar',
                    })

    @with_transaction()
    def test_create_strip_with_sql_value(self):
        "Test create with stripping with SQL value"
        Char = self.Char()

        char, = Char.create([{
                    'char': Literal(" Foo "),
                    'char_lstripped': Literal(" Foo "),
                    'char_rstripped': Literal(" Foo "),
                    'char_unstripped': Literal(" Foo "),
                    }])

        read_record = Char(char.id)
        self.assertEqual(read_record.char, "Foo")
        self.assertEqual(read_record.char_lstripped, "Foo ")
        self.assertEqual(read_record.char_rstripped, " Foo")
        self.assertEqual(read_record.char_unstripped, " Foo ")

    @with_transaction()
    def test_write_strip_with_sql_value(self):
        "Test write with stripping with SQL value"
        Char = self.Char()

        char, = Char.create([{
                    'char': "Foo",
                    'char_lstripped': "Foo",
                    'char_rstripped': "Foo",
                    'char_unstripped': "Foo",
                    }])

        Char.write([char], {
                'char': Literal(" Bar "),
                'char_lstripped': Literal(" Bar "),
                'char_rstripped': Literal(" Bar "),
                'char_unstripped': Literal(" Bar "),
                })
        read_record = Char(char.id)
        self.assertEqual(read_record.char, "Bar")
        self.assertEqual(read_record.char_lstripped, "Bar ")
        self.assertEqual(read_record.char_rstripped, " Bar")
        self.assertEqual(read_record.char_unstripped, " Bar ")


class FieldCharTranslatedTestCase(unittest.TestCase, CommonTestCaseMixin):
    "Test Field Char Translated"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def Char(self):
        return Pool().get('test.char_translate')

    @with_transaction()
    def test_create_with_sql_value(self):
        "Test cannot create with SQL value"
        Char = self.Char()

        with self.assertRaises(ValueError):
            Char.create([{'char': Literal('Foo')}])

    @with_transaction()
    def test_translation_default_language_cache(self):
        """Test set translation for default language does not fill
        transactional cache with former value"""
        pool = Pool()
        Config = pool.get('ir.configuration')
        Char = self.Char()

        with Transaction().set_context(language=Config.get_language()):
            char, = Char.create([{
                        'char': "foo",
                        }])

            char.char = "bar"
            char.save()

            self.assertEqual(char.char, "bar")


@unittest.skipUnless(backend.name == 'postgresql',
    "unaccent works only on postgresql")
class FieldCharUnaccentedTestCase(ExtensionTestCase):
    "Test Field Char with unaccented searches"
    extension = 'unaccent'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')
        super().setUpClass()

    @with_transaction()
    def test_normal_search(self):
        "Test searches without the unaccented feature"
        Char = Pool().get('test.char_unaccented_off')
        char, = Char.create([{
                    'char': 'Stéphanie',
                    }])

        chars_stephanie = Char.search([
                ('char', 'ilike', 'Stephanie'),
                ])

        self.assertListEqual(chars_stephanie, [])

    @with_transaction()
    def test_accented_search(self):
        "Test searches of accented value"
        Char = Pool().get('test.char_unaccented_on')
        char, = Char.create([{
                    'char': 'Stéphanie',
                    }])

        chars_stephanie = Char.search([
                ('char', 'ilike', 'Stephanie'),
                ])

        self.assertListEqual(chars_stephanie, [char])

    @with_transaction()
    def test_unaccented_search(self):
        "Test searches of unaccented value"
        Char = Pool().get('test.char_unaccented_on')
        char, = Char.create([{
                    'char': 'Stephanie',
                    }])

        chars_stephanie = Char.search([
                ('char', 'ilike', 'Stéphanie'),
                ])
        self.assertListEqual(chars_stephanie, [char])

    @with_transaction()
    def test_unaccented_translated_search(self):
        "Test unaccented translated search"
        pool = Pool()
        Char = pool.get('test.char_unaccented_translate')
        Lang = pool.get('ir.lang')

        lang, = Lang.search([
                ('translatable', '=', False),
                ('code', '!=', 'en'),
                ], limit=1)
        lang.translatable = True
        lang.save()
        char, = Char.create([{
                    'char': 'School',
                    }])

        with Transaction().set_context(lang=lang.code):
            trans_char = Char(char.id)
            trans_char.char = 'École'
            trans_char.save()

            chars_ecole = Char.search([
                    ('char', 'ilike', 'Ecole'),
                    ])
            self.assertListEqual(chars_ecole, [char])


@unittest.skipUnless(backend.name == 'postgresql',
    "similarity works only on postgresql")
class FieldCharSimilarityTestCase(ExtensionTestCase):
    "Test Field Char with similarity searches"
    extension = 'pg_trgm'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')
        super().setUpClass()

    def _test_search(self, Model):
        record1, record2 = Model.create([{
                    'char': "word",
                    }, {
                    'char': "Foo",
                    }])

        with Transaction().set_context(search_similarity=0.3):
            self.assertListEqual(Model.search([
                        ('char', 'ilike', 'two words'),
                        ]), [record1])

    @with_transaction()
    def test_search(self):
        "Test search"
        pool = Pool()
        self._test_search(pool.get('test.char'))

    @with_transaction()
    def test_search_translated(self):
        "Test search translated"
        pool = Pool()
        self._test_search(pool.get('test.char_translate'))

    def _test_order(self, Model):
        record1, record2 = Model.create([{
                    'char': "word",
                    }, {
                    'char': "Foo",
                    }])
        with Transaction().set_context({
                    '%s.char.order' % Model.__name__: 'foo bar',
                    }):
            self.assertListEqual(Model.search([
                        ], order=[('char', 'DESC')]),
                [record2, record1])

    @with_transaction()
    def test_order(self):
        "Test order"
        pool = Pool()
        self._test_order(pool.get('test.char'))

    @with_transaction()
    def test_order_translated(self):
        "Test order translated"
        pool = Pool()
        self._test_order(pool.get('test.char_translate'))

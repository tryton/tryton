# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.model.exceptions import (
    RequiredValidationError, SizeValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class CommonTestCaseMixin:

    @with_transaction()
    def test_create(self):
        "Test create text"
        Text = self.Text()

        text, text_none = Text.create([{
                    'text': "Test",
                    }, {
                    'text': None,
                    }])

        self.assertEqual(text.text, "Test")
        self.assertEqual(text_none.text, None)

    @with_transaction()
    def test_create_unicode(self):
        "Test create unicode"
        Text = self.Text()

        text, = Text.create([{
                    'text': "é",
                    }])

        self.assertEqual(text.text, "é")

    @with_transaction()
    def test_create_multiline(self):
        "Test create multilibe"
        Text = self.Text()

        text, = Text.create([{
                    'text': "Foo\nBar",
                    }])

        self.assertEqual(text.text, "Foo\nBar")

    @with_transaction()
    def test_search_equals(self):
        "Test search text equals"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Foo",
                    }])

        texts_foo = Text.search([
                ('text', '=', "Foo"),
                ])
        texts_bar = Text.search([
                ('text', '=', "Bar"),
                ])

        self.assertListEqual(texts_foo, [text])
        self.assertListEqual(texts_bar, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search text equals None"
        Text = self.Text()
        text, = Text.create([{
                    'text': None,
                    }])

        texts = Text.search([
                ('text', '=', None),
                ])

        self.assertListEqual(texts, [text])

    @with_transaction()
    def test_search_equals_unicode(self):
        "Test search text equals unicode"
        Text = self.Text()
        text, = Text.create([{
                    'text': "é",
                    }])

        texts = Text.search([
                ('text', '=', "é"),
                ])

        self.assertListEqual(texts, [text])

    @with_transaction()
    def test_search_equals_non_unicode(self):
        "Test search text equals non unicode"
        Text = self.Text()
        text, = Text.create([{
                    'text': "é",
                    }])

        texts = Text.search([
                ('text', '=', "é"),
                ])

        self.assertListEqual(texts, [text])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search text non equals"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Foo",
                    }])

        texts_foo = Text.search([
                ('text', '!=', "Foo"),
                ])
        texts_bar = Text.search([
                ('text', '!=', "Bar"),
                ])

        self.assertListEqual(texts_foo, [])
        self.assertListEqual(texts_bar, [text])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search text non equals None"
        Text = self.Text()
        text, = Text.create([{
                    'text': None,
                    }])

        texts = Text.search([
                ('text', '!=', None),
                ])

        self.assertListEqual(texts, [])

    @with_transaction()
    def test_search_in(self):
        "Test search text in"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Foo",
                    }])

        texts_foo = Text.search([
                ('text', 'in', ["Foo"]),
                ])
        texts_bar = Text.search([
                ('text', 'in', ["Bar"]),
                ])
        texts_empty = Text.search([
                ('text', 'in', []),
                ])

        self.assertListEqual(texts_foo, [text])
        self.assertListEqual(texts_bar, [])
        self.assertListEqual(texts_empty, [])

    @with_transaction()
    def test_search_in_none(self):
        "Test search text in [None]"
        Text = self.Text()
        text, = Text.create([{
                    'text': None,
                    }])

        texts = Text.search([
                ('text', 'in', [None]),
                ])

        self.assertListEqual(texts, [text])

    @with_transaction()
    def test_search_not_in(self):
        "Test search text not in"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Foo",
                    }])

        texts_foo = Text.search([
                ('text', 'not in', ["Foo"]),
                ])
        texts_bar = Text.search([
                ('text', 'not in', ["Bar"]),
                ])
        texts_empty = Text.search([
                ('text', 'not in', []),
                ])

        self.assertListEqual(texts_foo, [])
        self.assertListEqual(texts_bar, [text])
        self.assertListEqual(texts_empty, [text])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search text not in [None]"
        Text = self.Text()
        text, = Text.create([{
                    'text': None,
                    }])

        texts = Text.search([
                ('text', 'not in', [None]),
                ])

        self.assertListEqual(texts, [])

    @with_transaction()
    def test_search_like(self):
        "Test search text like"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Bar",
                    }])

        texts_bar = Text.search([
                ('text', 'like', "Bar"),
                ])
        texts_b = Text.search([
                ('text', 'like', "B%"),
                ])
        texts_foo = Text.search([
                ('text', 'like', "Foo"),
                ])
        texts_f = Text.search([
                ('text', 'like', "F%"),
                ])

        self.assertListEqual(texts_bar, [text])
        self.assertListEqual(texts_b, [text])
        self.assertListEqual(texts_foo, [])
        self.assertListEqual(texts_f, [])

    @with_transaction()
    def test_search_ilike(self):
        "Test search text ilike"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Bar",
                    }])

        texts_bar = Text.search([
                ('text', 'ilike', "bar"),
                ])
        texts_b = Text.search([
                ('text', 'ilike', "b%"),
                ])
        texts_foo = Text.search([
                ('text', 'ilike', "foo"),
                ])
        texts_f = Text.search([
                ('text', 'ilike', "f%"),
                ])

        self.assertListEqual(texts_bar, [text])
        self.assertListEqual(texts_b, [text])
        self.assertListEqual(texts_foo, [])
        self.assertListEqual(texts_f, [])

    @with_transaction()
    def test_search_not_like(self):
        "Test search text not like"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Bar",
                    }])

        texts_bar = Text.search([
                ('text', 'not like', "Bar"),
                ])
        texts_b = Text.search([
                ('text', 'not like', "B%"),
                ])
        texts_foo = Text.search([
                ('text', 'not like', "Foo"),
                ])
        texts_f = Text.search([
                ('text', 'not like', "F%"),
                ])

        self.assertListEqual(texts_bar, [])
        self.assertListEqual(texts_b, [])
        self.assertListEqual(texts_foo, [text])
        self.assertListEqual(texts_f, [text])

    @with_transaction()
    def test_search_not_ilike(self):
        "Test search text not like"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Bar",
                    }])

        texts_bar = Text.search([
                ('text', 'not ilike', "bar"),
                ])
        texts_b = Text.search([
                ('text', 'not ilike', "b%"),
                ])
        texts_foo = Text.search([
                ('text', 'not ilike', "foo"),
                ])
        texts_f = Text.search([
                ('text', 'not ilike', "f%"),
                ])

        self.assertListEqual(texts_bar, [])
        self.assertListEqual(texts_b, [])
        self.assertListEqual(texts_foo, [text])
        self.assertListEqual(texts_f, [text])

    @with_transaction()
    def test_write_unicode(self):
        "Test write text unicode"
        Text = self.Text()
        text, = Text.create([{
                    'text': "Foo",
                    }])

        Text.write([text], {
                'text': "é",
                })

        self.assertEqual(text.text, "é")


class FieldTextTestCase(unittest.TestCase, CommonTestCaseMixin):
    "Test Field Text"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def Text(self):
        return Pool().get('test.text')

    @with_transaction()
    def test_create_without_default(self):
        "Test create text without default"
        Text = Pool().get('test.text')

        text, = Text.create([{}])

        self.assertEqual(text.text, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create text without default"
        Text = Pool().get('test.text_default')

        text, = Text.create([{}])

        self.assertEqual(text.text, "Test")

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create text required with value"
        Text = Pool().get('test.text_required')

        text, = Text.create([{
                    'text': "Test",
                    }])

        self.assertEqual(text.text, "Test")

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create text required without value"
        Text = Pool().get('test.text_required')

        with self.assertRaises(RequiredValidationError):
            Text.create([{}])

    @with_transaction()
    def test_create_required_with_empty(self):
        "Test create text required with empty"
        Text = Pool().get('test.text_required')

        with self.assertRaises(RequiredValidationError):
            Text.create([{
                        'text': '',
                        }])

    @with_transaction()
    def test_create_size_valid(self):
        "Test create text with size"
        Text = Pool().get('test.text_size')

        text, = Text.create([{
                    'text': "Test",
                    }])

        self.assertEqual(text.text, "Test")

    @with_transaction()
    def test_create_size_invalid(self):
        "Test create text with invalid size"
        Text = Pool().get('test.text_size')

        with self.assertRaises(SizeValidationError):
            Text.create([{
                        'text': "foobar",
                        }])

    @with_transaction()
    def test_write(self):
        "Test write text"
        Text = Pool().get('test.text')
        text, = Text.create([{
                    'text': "Foo",
                    }])

        Text.write([text], {
                'text': "Bar",
                })

        self.assertEqual(text.text, "Bar")

    @with_transaction()
    def test_write_none(self):
        "Test write text None"
        Text = Pool().get('test.text')
        text, = Text.create([{
                    'text': "Foo",
                    }])

        Text.write([text], {
                'text': None,
                })

        self.assertEqual(text.text, None)

    @with_transaction()
    def test_write_size_invalid(self):
        "Test write text with invalid size"
        Text = Pool().get('test.text_size')

        text, = Text.create([{
                    'text': "Test",
                    }])

        with self.assertRaises(SizeValidationError):
            Text.write([text], {
                    'text': 'foobar',
                    })


class FieldTextTranslatedTestCase(unittest.TestCase, CommonTestCaseMixin):
    "Test Field Text Translated"

    def Text(self):
        return Pool().get('test.text_translate')


def suite():
    suite_ = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite_.addTests(loader.loadTestsFromTestCase(FieldTextTestCase))
    suite_.addTests(loader.loadTestsFromTestCase(FieldTextTranslatedTestCase))
    return suite_

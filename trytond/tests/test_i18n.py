# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.i18n import gettext, lazy_gettext
from trytond.pool import Pool
from trytond.tools.string_ import LazyString


class I18nTestCase(unittest.TestCase):
    'Test Model Access'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_gettext_with_translation(self):
        "gettext returns the translated text"
        pool = Pool()
        Lang = pool.get('ir.lang')
        Translation = pool.get('ir.translation')
        ModelData = pool.get('ir.model.data')

        lang, = Lang.search([('code', '!=', 'en')], limit=1)
        Translation.create([{
                    'name': 'ir.message,text',
                    'lang': lang.code,
                    'type': 'model',
                    'res_id': ModelData.get_id('tests', 'msg_test'),
                    'src': 'Message',
                    'value': 'Translated Message',
                    'module': 'tests',
                    'fuzzy': False,
                    }])

        message = gettext('tests.msg_test', lang.code)

        self.assertEqual(message, 'Translated Message')

    @with_transaction()
    def test_gettext_with_translation_format(self):
        "gettext returns the translated and formatted text"
        pool = Pool()
        Lang = pool.get('ir.lang')
        Translation = pool.get('ir.translation')
        ModelData = pool.get('ir.model.data')

        lang, = Lang.search([('code', '!=', 'en')], limit=1)
        Translation.create([{
                    'name': 'ir.message,text',
                    'lang': lang.code,
                    'type': 'model',
                    'res_id': ModelData.get_id('tests', 'msg_test'),
                    'src': 'Message',
                    'value': 'Translated Message %(variable)s',
                    'module': 'tests',
                    'fuzzy': False,
                    }])

        message1 = gettext(
            'tests.msg_test', lang.code, variable='foo')
        message2 = gettext(
            'tests.msg_test', lang.code, variable='bar')

        self.assertEqual(message1, 'Translated Message foo')
        self.assertEqual(message2, 'Translated Message bar')

    @with_transaction()
    def test_gettext_no_translation(self):
        "gettext returns original string when no translation"
        pool = Pool()
        Lang = pool.get('ir.lang')

        lang, = Lang.search([('code', '!=', 'en')], limit=1)

        message = gettext('tests.msg_test', lang.code)

        self.assertEqual(message, 'Message')

    @with_transaction()
    def test_gettest_wrong_id_format(self):
        "gettext returns the id if it has wrong format"
        message = gettext("Wrong Format")

        self.assertEqual(message, "Wrong Format")

    @with_transaction()
    def test_gettext_wrong_id(self):
        "gettext returns the id if it does not exist"
        message = gettext('tests.not_exist')

        self.assertEqual(message, 'tests.not_exist')

    def test_gettext_without_transaction(self):
        "gettext return the id if there is no transaction"
        message = gettext('test.msg_test')

        self.assertEqual(message, 'test.msg_test')

    @with_transaction()
    def test_lazy_gettext(self):
        "lazy_gettext returns a LazyString"
        lazy = lazy_gettext('tests.msg_test')

        self.assertIsInstance(lazy, LazyString)
        self.assertEqual(str(lazy), "Message")


def suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(I18nTestCase))
    return suite

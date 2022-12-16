#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from unittest import TestCase
from proteus import config, Wizard, Model


class TestWizard(TestCase):

    def setUp(self):
        config.set_trytond(':memory:', database_type='sqlite')

    def test_translation_clean(self):
        translation_clean = Wizard('ir.translation.clean')
        self.assertEqual(translation_clean.form.__class__.__name__,
                'ir.translation.clean.init')
        translation_clean.execute('start')

    def test_translation_export(self):
        translation_export = Wizard('ir.translation.export')
        translation_export.form.lang = 'en_US'
        translation_export.form.module = 'ir'
        translation_export.execute('start')
        self.assert_(translation_export.form.file)
        translation_export.execute('end')

    def test_user_config(self):
        User = Model.get('res.user')

        user_config = Wizard('res.user.config')
        user_config.execute('user')
        user_config.form.name = 'Foo'
        user_config.form.login = 'foo'
        user_config.execute('add')
        self.assertEqual(user_config.form.name, None)
        self.assertEqual(user_config.form.login, None)
        user_config.form.name = 'Bar'
        user_config.form.login = 'bar'
        user_config.execute('end')

        self.assert_(User.find([('name', '=', 'Foo')]))
        self.assertFalse(User.find([('name', '=', 'Bar')]))

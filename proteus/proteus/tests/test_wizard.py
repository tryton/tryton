# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Wizard, Model
from .common import ProteusTestCase


class TestWizard(ProteusTestCase):

    def test_translation_clean(self):
        translation_clean = Wizard('ir.translation.clean')
        self.assertEqual(translation_clean.form.__class__.__name__,
                'ir.translation.clean.start')
        translation_clean.execute('clean')
        self.assertEqual(translation_clean.form.__class__.__name__,
            'ir.translation.clean.succeed')

    def test_translation_export(self):
        Lang = Model.get('ir.lang')
        Module = Model.get('ir.module')
        translation_export = Wizard('ir.translation.export')
        translation_export.form.language, = Lang.find([('code', '=', 'en')])
        translation_export.form.module, = Module.find([('name', '=', 'ir')])
        translation_export.execute('export')
        self.assertTrue(translation_export.form.file)
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

        self.assertTrue(User.find([('name', '=', 'Foo')]))
        self.assertFalse(User.find([('name', '=', 'Bar')]))

    def test_translation_update(self):
        print_model_graph = Wizard('ir.translation.update')
        self.assertEqual(len(print_model_graph.actions), 0)
        print_model_graph.execute('update')
        self.assertEqual(len(print_model_graph.actions), 1)

    def test_configuration_wizard(self):
        config_wizard = Wizard('ir.module.config_wizard')
        config_wizard.execute('action')
        self.assertTrue(config_wizard.actions)

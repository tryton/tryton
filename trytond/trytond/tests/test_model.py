# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction


class ModelTestCase(unittest.TestCase):
    'Test Model'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_repr(self):
        'Test repr'
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(name='foo')
        self.assertEqual(
            repr(record), "Pool().get('test.model')(**{'name': 'foo'})")

        record.save()
        self.assertEqual(
            repr(record), "Pool().get('test.model')(%s)" % record.id)

    @with_transaction()
    def test_init_parent(self):
        "Test __init__ with _parent_"
        pool = Pool()
        Model = pool.get('test.model_child')

        values = {
            '_parent_parent.name': "Test",
            }
        record = Model(**values)

        self.assertEqual(record.parent.name, "Test")

    @with_transaction()
    def test_init_parent_parent(self):
        "Test __init__ with _parent_._parent_"
        pool = Pool()
        Model = pool.get('test.model_child_child')

        values = {
            '_parent_parent.name': "Test 1",
            '_parent_parent._parent_parent.name': "Test 2",
            }
        record = Model(**values)

        self.assertEqual(record.parent.name, "Test 1")
        self.assertEqual(record.parent.parent.name, "Test 2")

    @with_transaction()
    def test_init_context(self):
        "Test __init__ for field with context"
        pool = Pool()
        Model = pool.get('test.model')
        ModelContext = pool.get('test.model_context')

        target, = Model.create([{'name': "Test Context"}])
        # The dictionary order is important
        values = {
            'target': target.id,
            'name': "foo",
            }
        record = ModelContext(**values)

        self.assertEqual(record.target._context, {'name': "foo"})

    @with_transaction()
    def test_init_parent_context(self):
        "Test __init__ with _parent for field with context"
        pool = Pool()
        ModelContext = pool.get('test.model_context')

        # The dictionary order is important
        values = {
            '_parent_target.name': "Test Context",
            'name': "foo",
            }
        record = ModelContext(**values)

        self.assertEqual(record.target._context, {'name': "foo"})

    @with_transaction()
    def test_init_context_parent(self):
        "Test __init__ for field with context from _parent"
        pool = Pool()
        Model = pool.get('test.model')
        ModelContext = pool.get('test.model_context_parent')

        target, = Model.create([{'name': "Test Context"}])
        # The dictionary order is important
        values = {
            'target': target.id,
            '_parent_parent.name': "bar",
            }
        record = ModelContext(**values)

        self.assertEqual(record.target._context, {'name': "bar"})

    @with_transaction()
    def test_init_parent_context_parent(self):
        "Test __init__ with _parent for field with context from _parent"
        pool = Pool()
        ModelContext = pool.get('test.model_context_parent')

        # The dictionary order is important
        values = {
            '_parent_target.name': "Test Context",
            '_parent_parent.name': "bar",
            }
        record = ModelContext(**values)

        self.assertEqual(record.parent.name, "bar")
        self.assertEqual(record.target._context, {'name': "bar"})

    @with_transaction()
    def test_names_model(self):
        "Test __names__ for model only"
        pool = Pool()
        Model = pool.get('test.model')

        names = Model.__names__()

        self.assertEqual(names, {'model': "Model"})

    @with_transaction()
    def test_names_field(self):
        "Test __names__ with field"
        pool = Pool()
        Model = pool.get('test.model')

        names = Model.__names__('name')

        self.assertEqual(names, {'model': "Model", 'field': "Name"})

    @with_transaction()
    def test_fields_get_no_write_access(self):
        "Test field is readonly when no write access on it"
        pool = Pool()
        Model = pool.get('test.model')
        Field = pool.get('ir.model.field')
        FieldAccess = pool.get('ir.model.field.access')

        field, = Field.search([
                ('name', '=', 'name'),
                ('model.model', '=', Model.__name__),
                ])
        FieldAccess.create([{
                    'field': field.id,
                    'perm_write': False,
                    }])

        definition = Model.fields_get(['name'])

        self.assertTrue(definition['name']['readonly'])


class ModelTranslationTestCase(unittest.TestCase):
    "Test Model translation"
    default_language = 'en'
    other_language = 'fr'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')
        cls.setup_language()

    @classmethod
    @with_transaction()
    def setup_language(cls):
        pool = Pool()
        Language = pool.get('ir.lang')
        Configuration = pool.get('ir.configuration')

        default, = Language.search([('code', '=', cls.default_language)])
        default.translatable = True
        default.save()

        other, = Language.search([('code', '=', cls.other_language)])
        other.translatable = True
        other.save()

        config = Configuration(1)
        config.language = cls.default_language
        config.save()

        Transaction().commit()

    @with_transaction()
    def test_fields_get(self):
        "Test fields_get translated"
        pool = Pool()
        Model = pool.get('test.model')
        Translation = pool.get('ir.translation')

        Translation.create([{
                    'lang': self.other_language,
                    'src': "Name",
                    'name': 'test.model,name',
                    'res_id': -1,
                    'value': "Nom",
                    'type': 'field',
                    }])
        with Transaction().set_context(language=self.default_language):
            field = Model.fields_get(['name'])['name']
        with Transaction().set_context(language=self.other_language):
            other = Model.fields_get(['name'])['name']

        self.assertEqual(field['string'], "Name")
        self.assertEqual(other['string'], "Nom")


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader().loadTestsFromTestCase(ModelTestCase))
    suite_.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModelTranslationTestCase))
    return suite_

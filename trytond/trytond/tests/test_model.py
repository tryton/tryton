# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import unittest
from copy import copy

from trytond.model.model import record
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
    def test_hash_with_id(self):
        "Test hash with id"
        pool = Pool()
        Model = pool.get('test.model')

        record1 = Model(id=1)
        record1bis = Model(id=1)
        record2 = Model(id=2)

        self.assertEqual(hash(record1), hash(record1bis))
        self.assertNotEqual(hash(record1), hash(record2))

    @with_transaction()
    def test_hash_without_id(self):
        "Test hash without id"
        pool = Pool()
        Model = pool.get('test.model')

        record1 = Model()
        record2 = Model()

        self.assertNotEqual(hash(record1), hash(record2))

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
    def test_names_record(self):
        "test __names__ with record"
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(name="Test")
        record.save()
        names = Model.__names__(record=record)

        self.assertEqual(names, {'model': "Model", 'record': "Test"})

    @with_transaction()
    def test_names_unsaved_record(self):
        "test __names__ with unsaved record"
        pool = Pool()
        Model = pool.get('test.model')

        record = Model()
        names = Model.__names__(record=record)

        self.assertEqual(names, {'model': "Model", 'record': record.id})

    @with_transaction()
    def test_names_value(self):
        "test __names__ with value"
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(name="Test")
        names = Model.__names__(field='name', record=record)

        self.assertEqual(
            names, {
                'model': "Model", 'field': "Name",
                'record': record.id, 'value': "Test"})

    @with_transaction()
    def test_names_value_selection(self):
        "test __names__ with selection value"
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(selection='foo')
        names = Model.__names__(field='selection', record=record)

        self.assertEqual(
            names, {
                'model': "Model", 'field': "Selection",
                'record': record.id, 'value': "Foo"})

    @with_transaction()
    def test_names_value_multiselection(self):
        "test __names__ with multiselection value"
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(multiselection=['foo', 'bar'])
        names = Model.__names__(field='multiselection', record=record)

        self.assertEqual(
            names, {
                'model': "Model", 'field': "MultiSelection",
                'record': record.id, 'value': "Foo, Bar"})

    @with_transaction()
    def test_names_value_list(self):
        "Test __names__ with value as list"
        pool = Pool()
        Model = pool.get('test.model_parent')
        Child = pool.get('test.model_child')

        record = Model(
            name="Test", children=[Child(name="Foo"), Child(name="Bar")])
        record.save()
        names = Model.__names__(field='children', record=record)

        self.assertEqual(
            names, {
                'model': "Model Parent", 'field': "Children",
                'record': "Test", 'value': "Foo, Bar"})

    @with_transaction()
    def test_names_unset_value(self):
        "test __names__ with unset value"
        pool = Pool()
        Model = pool.get('test.model')

        record = Model()
        names = Model.__names__(field='name', record=record)

        self.assertEqual(
            names, {
                'model': "Model", 'field': "Name",
                'record': record.id, 'value': 'None'})

    @with_transaction()
    def test_fields_get_no_write_access(self):
        "Test field is readonly when no write access on it"
        pool = Pool()
        Model = pool.get('test.model')
        FieldAccess = pool.get('ir.model.field.access')

        FieldAccess.create([{
                    'model': Model.__name__,
                    'field': 'name',
                    'perm_write': False,
                    }])

        definition = Model.fields_get(['name'])

        self.assertTrue(definition['name']['readonly'])

    @with_transaction()
    def test_copy(self):
        "Test copy an instance"
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(name='foo')

        record_copied = copy(record)

        self.assertEqual(record.name, record_copied.name)
        self.assertNotEqual(id(record), id(record_copied))

    @with_transaction()
    def test_copy_values(self):
        "Test copied instance has different values"
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(name='foo')

        record_copied = copy(record)
        record_copied.name = 'bar'

        self.assertEqual(record.name, 'foo')
        self.assertEqual(record_copied.name, 'bar')

    @with_transaction()
    def test_default_get(self):
        "Test default_get"
        pool = Pool()
        Model = pool.get('test.model.default')

        self.assertEqual(
            Model.default_get(['name', 'description']), {
                'description': "Test",
                })

    @with_transaction()
    def test_default_get_with_context(self):
        "Test default_get with context"
        pool = Pool()
        Model = pool.get('test.model.default')

        with Transaction().set_context(default_name="foo"):
            self.assertEqual(
                Model.default_get(['name']), {
                    'name': "foo",
                    })

    @with_transaction()
    def test_default_get_with_context_and_method(self):
        "Test default_get with context and method"
        pool = Pool()
        Model = pool.get('test.model.default')

        with Transaction().set_context(default_description="foo"):
            self.assertEqual(
                Model.default_get(['description']), {
                    'description': "foo",
                    })

    @with_transaction()
    def test_default_get_with_context_rec_name(self):
        "Test default_get with context rec_name"
        pool = Pool()
        Model = pool.get('test.model.default')

        with Transaction().set_context(default_rec_name="foo"):
            self.assertEqual(
                Model.default_get(['name']), {
                    'name': "foo",
                    })

    @with_transaction()
    def test_default_get_with_rec_name(self):
        "Test default_get with rec_name"
        pool = Pool()
        Model = pool.get('test.model.default')
        Target = pool.get('test.model')

        target = Target(name="Target")
        target.save()

        with Transaction().set_context(default_target=target.id):
            self.assertEqual(
                Model.default_get(['target'], with_rec_name=True), {
                    'target': target.id,
                    'target.': {
                        'rec_name': "Target",
                        },
                    })

    @with_transaction()
    def test_default_get_without_rec_name(self):
        "Test default_get without rec_name"
        pool = Pool()
        Model = pool.get('test.model.default')
        Target = pool.get('test.model')

        target = Target(name="Target")
        target.save()

        with Transaction().set_context(default_target=target.id):
            self.assertEqual(
                Model.default_get(['target'], with_rec_name=False), {
                    'target': target.id,
                    })


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


class RecordTestCase(unittest.TestCase):
    "Test record"

    def test_creation(self):
        "Test record creation"
        Record = record('model', ['foo', 'bar'])

        self.assertEqual(Record.__name__, 'model')
        self.assertEqual(set(Record.__slots__), {'foo', 'bar'})

    def test_init(self):
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='foo')

        self.assertEqual(rec.foo, 'foo')

    def test_getitem(self):
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='foo')

        self.assertEqual(rec['foo'], 'foo')

    def test_setitem(self):
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='foo')

        rec['foo'] = 'foo'
        self.assertEqual(rec['foo'], 'foo')

    def test_contains(self):
        "Test record contains"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='foo')

        self.assertTrue('foo' in rec)
        self.assertFalse('bar' in rec)

    def test_clear(self):
        "Test record clear"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='foo', bar='bar')

        rec._clear()

        with self.assertRaises(AttributeError):
            rec.foo
        with self.assertRaises(AttributeError):
            rec.bar

    def test_copy(self):
        "Test copy record"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='baz')
        copy = rec._copy()

        self.assertEqual(copy.foo, 'baz')
        self.assertNotEqual(rec, copy)
        self.assertIsInstance(copy, Record)

    def test_get(self):
        "Test get field from record"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='baz')

        self.assertEqual(rec._get('foo'), 'baz')
        self.assertEqual(rec._get('bar'), None)
        self.assertEqual(rec._get('bar', 42), 42)
        with self.assertRaises(KeyError):
            rec._get('baz')

    def test_keys(self):
        "Test record keys"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='baz')

        self.assertEqual(list(rec._keys()), ['foo'])

    def test_items(self):
        "Test record items"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='baz')

        self.assertEqual(list(rec._items()), [('foo', 'baz')])

    def test_pop(self):
        "Test pop field from record"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='baz')

        value = rec._pop('foo')
        self.assertEqual(value, 'baz')
        with self.assertRaises(AttributeError):
            rec.foo

        with self.assertRaises(KeyError):
            rec._pop('baz')

    def test_popitem(self):
        "Test popitem field from record"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='baz')

        value = rec._popitem('foo')
        self.assertEqual(value, ('foo', 'baz'))

    def test_setdefault(self):
        "Test set default field on record"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='foo')

        self.assertEqual(rec._setdefault('bar', 'bar'), 'bar')
        self.assertEqual(rec.bar, 'bar')
        self.assertEqual(rec._setdefault('foo', 'baz'), 'foo')
        self.assertEqual(rec.foo, 'foo')

    def test_update(self):
        "Test update record"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='foo')
        rec._update(foo='bar', bar='baz')

        self.assertEqual(rec.foo, 'bar')
        self.assertEqual(rec.bar, 'baz')

    def test_values(self):
        "Test record values"
        Record = record('model', ['foo', 'bar'])

        rec = Record(foo='baz')

        self.assertEqual(list(rec._values()), [('baz')])

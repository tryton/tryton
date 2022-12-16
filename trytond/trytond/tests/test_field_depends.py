# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import unittest

from trytond.model import ModelView, fields
from trytond.pyson import Eval
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldDependsTestCase(unittest.TestCase):
    'Test Field Depends'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def test_empty_depends(self):
        'Test depends are set if empty'

        class Model(object):
            @fields.depends('name')
            def dependant(self):
                pass
        record = Model()

        record.dependant()

        self.assertIsNone(record.name)

    def test_empty_depends_default(self):
        "Test depends are set with default value if empty"

        class Model(object):
            @fields.depends('name')
            def dependant(self):
                pass

            @classmethod
            def default_name(cls):
                return "foo"
        Model._defaults = {'name': Model.default_name}
        record = Model()

        record.dependant()

        self.assertEqual(record.name, "foo")

    def test_set_depends(self):
        'Test depends are not modified if set'

        class Model(object):
            @fields.depends('name')
            def dependant(self):
                pass
        record = Model()
        record.name = "Name"

        record.dependant()

        self.assertEqual(record.name, "Name")

    def test_parent(self):
        'Test _parent_ depends are set'

        class Model(object):
            @fields.depends('_parent_parent.name',
                '_parent_parent.description')
            def dependant(self):
                pass
        parent = Model()
        parent.description = "Description"
        record = Model()
        record.parent = parent

        record.dependant()

        self.assertIsNone(record.parent.name)
        self.assertEqual(record.parent.description, "Description")

    def test_nested_parent(self):
        'Test nested _parent_ depends are set'

        class Model(object):
            @fields.depends('_parent_parent.name',
                '_parent_parent.description',
                '_parent_parent._parent_parent.name',
                '_parent_parent._parent_parent.description',)
            def dependant(self):
                pass
        grantparent = Model()
        grantparent.description = "Description"
        parent = Model()
        parent.parent = grantparent
        record = Model()
        record.parent = parent

        record.dependant()

        self.assertIsNone(record.parent.name)
        self.assertIsNone(record.parent.description)
        self.assertIsNone(record.parent.parent.name)
        self.assertEqual(record.parent.parent.description, "Description")

    def test_inherit(self):
        "Tests inherited depends"

        class Parent(ModelView):
            name = fields.Char("Name")
            foo = fields.Char("Foo")

            @fields.depends('foo')
            def on_change_name(self):
                pass

        class Model(Parent):
            bar = fields.Char("Bar")

            @fields.depends('bar')
            def on_change_name(self):
                super(Model, self).on_change_name()

        Model.__setup__()
        Model.__post_setup__()

        self.assertEqual(Model.name.on_change, {'foo', 'bar'})

    def test_methods(self):
        "Tests depends on method"

        class Model(ModelView):
            name = fields.Char("Name")
            foo = fields.Char("Foo")
            bar = fields.Char("Bar")

            @fields.depends('foo', methods=['other_method'])
            def on_change_name(self):
                self.other_method()

            @fields.depends('bar')
            def other_method(self):
                pass

        Model.__setup__()
        Model.__post_setup__()

        self.assertEqual(Model.name.on_change, {'foo', 'bar'})

    def test_methods_2(self):
        "Tests depends on method on method"

        class Model(ModelView):
            name = fields.Char("Name")
            foo = fields.Char("Foo")
            bar = fields.Char("Bar")

            @fields.depends('foo', methods=['other_method'])
            def on_change_name(self):
                self.other_method()

            @fields.depends(methods=['another_method'])
            def other_method(self):
                self.another_method()

            @fields.depends('bar')
            def another_method(self):
                pass

        Model.__setup__()
        Model.__post_setup__()

        self.assertEqual(Model.name.on_change, {'foo', 'bar'})

    @with_transaction()
    def test_field_context(self):
        "Tests depends on field with context"

        class Model(ModelView):
            name = fields.Char("Name")
            foo = fields.Char(
                "Foo", context={'bar': Eval('bar')}, depends=['bar'])
            bar = fields.Char("Bar")

            @fields.depends('foo')
            def on_change_name(self):
                return

        Model.__setup__()
        Model.__post_setup__()

        self.assertEqual(
            set(Model.name.definition(Model, 'en')['on_change']),
            {'foo', 'bar', 'id'})

    @with_transaction()
    def test_field_context_parent(self):
        "Tests depends on parent field with context"

        class Target(ModelView):
            name = fields.Char(
                "Name", context={'bar': Eval('bar')}, depends=['bar'])
            bar = fields.Char("Bar")

        class Model(ModelView):
            name = fields.Char("Name")
            foo = fields.Many2One(None, "Foo")

            @fields.depends('_parent_foo.name')
            def on_change_name(self):
                return

        Model.foo.get_target = lambda: Target

        Target.__setup__()
        Target.__post_setup__()
        Model.__setup__()
        Model.__post_setup__()

        self.assertEqual(
            set(Model.name.definition(Model, 'en')['on_change']),
            {'_parent_foo.name', '_parent_foo.bar', 'id'})

    def test_property_depends(self):
        "Tests depends on a property"

        class Model(ModelView):
            "ModelView Property Depends"
            __name__ = 'test.modelview.property_depends'

            foo = fields.Char("Foo")
            bar = fields.Char("Bar")

            @property
            @fields.depends('foo')
            def len_foo(self):
                return len(self.foo)

            @len_foo.setter
            @fields.depends('bar')
            def len_foo(self, value):
                pass

            @fields.depends(methods=['len_foo'])
            def on_change_bar(self):
                pass

        Model.__setup__()
        Model.__post_setup__()

        self.assertEqual(Model.bar.on_change, {'foo', 'bar'})


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldDependsTestCase)

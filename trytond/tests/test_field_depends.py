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


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldDependsTestCase)

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class MultiSelection(ModelSQL):
    'MultiSelection'
    __name__ = 'test.multi_selection'
    selects = fields.MultiSelection([
            ('foo', "Foo"),
            ('bar', "Bar"),
            ('foobar', "FooBar"),
            ], "Selections")
    selects_string = selects.translated('selects')
    dyn_selects = fields.MultiSelection('get_dyn_selection',
        "Dynamic Selections")
    static_selects = fields.MultiSelection('get_static_selection',
        "Static Selectsions")

    @fields.depends('selects')
    def get_dyn_selection(self):
        if self.selects and 'foo' in self.selects:
            return [('foo', "Foo"), ('foobar', "FooBar")]
        else:
            return [('bar', "Bar"), ('baz', "Baz")]

    @classmethod
    def get_static_selection(cls):
        return cls.selects.selection


class MultiSelectionRequired(ModelSQL):
    "MultiSelection Required"
    __name__ = 'test.multi_selection_required'
    selects = fields.MultiSelection(
        [('foo', "Foo"), ('bar', "Bar")], "Selects", required=True)


def register(module):
    Pool.register(
        MultiSelection,
        MultiSelectionRequired,
        module=module, type_='model')

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class MultiSelection(ModelSQL):
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
    __name__ = 'test.multi_selection_required'
    selects = fields.MultiSelection(
        [('foo', "Foo"), ('bar', "Bar")], "Selects", required=True)


class MultiSelectionText(MultiSelection):
    __name__ = 'test.multi_selection_text'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.selects._sql_type = 'TEXT'
        cls.dyn_selects._sql_type = 'TEXT'
        cls.static_selects._sql_type = 'TEXT'


class MultiSelectionRequiredText(MultiSelectionRequired):
    __name__ = 'test.multi_selection_required_text'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.selects._sql_type = 'TEXT'


def register(module):
    Pool.register(
        MultiSelection,
        MultiSelectionRequired,
        MultiSelectionText,
        MultiSelectionRequiredText,
        module=module, type_='model')

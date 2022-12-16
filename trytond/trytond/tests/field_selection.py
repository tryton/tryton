# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Selection(ModelSQL):
    'Selection'
    __name__ = 'test.selection'
    select = fields.Selection([
            ('', ''), ('arabic', 'Arabic'), ('hexa', 'Hexadecimal')],
        'Selection')
    select_string = select.translated('select')
    dyn_select = fields.Selection('get_selection',
        'Instance Dynamic Selection')
    dyn_select_string = dyn_select.translated('dyn_select')
    dyn_select_static = fields.Selection('static_selection',
        'Static Selection')
    dyn_select_static_string = dyn_select_static.translated(
        'dyn_select_static')
    unsorted_select = fields.Selection([
            (None, ""),
            ('first', "First"),
            ('second', "Second"),
            ('last', "Last"),
            ], "Unsorted Selection", sort=False)

    @fields.depends('select')
    def get_selection(self):
        if self.select == 'arabic':
            return [('', '')] + [(str(i), str(i)) for i in range(1, 11)]
        else:
            return [('', '')] + [(hex(i), hex(i)) for i in range(1, 11)]

    @staticmethod
    def static_selection():
        return [('', '')] + [(str(i), str(i)) for i in range(1, 11)]


class SelectionRequired(ModelSQL):
    'Selection Required'
    __name__ = 'test.selection_required'
    select = fields.Selection([('arabic', 'Arabic'), ('latin', 'Latin')],
        'Selection', required=True)


class SelectionLabel(ModelSQL):
    "Selection with different label"
    __name__ = 'test.selection_label'
    select = fields.Selection([
            ('a', "Z"),
            ('b', "Y"),
            ('c', "X"),
            ], "Selection")


def register(module):
    Pool.register(
        Selection,
        SelectionRequired,
        SelectionLabel,
        module=module, type_='model')

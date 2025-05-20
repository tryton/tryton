# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import DictSchemaMixin, ModelSQL, fields
from trytond.pool import Pool


class HistoryDictSchema(DictSchemaMixin, ModelSQL):
    __name__ = 'test.history.dict.schema'


class TestHistory(ModelSQL):
    __name__ = 'test.history'
    _history = True
    value = fields.Integer('Value')
    lines = fields.One2Many('test.history.line', 'history', 'Lines')
    lines_at_stamp = fields.One2Many(
        'test.history.line', 'history', 'Lines at Stamp',
        datetime_field='stamp')
    stamp = fields.Timestamp('Stamp')
    dico = fields.Dict('test.history.dict.schema', "Dict")


class TestHistoryLine(ModelSQL):
    __name__ = 'test.history.line'
    _history = True
    history = fields.Many2One('test.history', 'History')
    name = fields.Char('Name')


def register(module):
    Pool.register(
        TestHistory,
        TestHistoryLine,
        module=module, type_='model')

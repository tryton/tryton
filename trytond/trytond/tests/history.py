# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields

__all__ = ['TestHistory', 'TestHistoryLine']


class TestHistory(ModelSQL):
    'Test History'
    __name__ = 'test.history'
    _history = True
    value = fields.Integer('Value')
    lines = fields.One2Many('test.history.line', 'history', 'Lines')
    lines_at_stamp = fields.One2Many(
        'test.history.line', 'history', 'Lines at Stamp',
        datetime_field='stamp')
    stamp = fields.Timestamp('Stamp')


class TestHistoryLine(ModelSQL):
    'Test History Line'
    __name__ = 'test.history.line'
    _history = True
    history = fields.Many2One('test.history', 'History')
    name = fields.Char('Name')

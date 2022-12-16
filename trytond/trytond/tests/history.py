#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields

__all__ = ['TestHistory']


class TestHistory(ModelSQL):
    'Test History'
    __name__ = 'test.history'
    _history = True
    value = fields.Integer('Value')

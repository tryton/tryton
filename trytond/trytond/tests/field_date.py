# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Date(ModelSQL):
    'Date'
    __name__ = 'test.date'
    date = fields.Date(string='Date', help='Test date',
            required=False)


class DateDefault(ModelSQL):
    'Date Default'
    __name__ = 'test.date_default'
    date = fields.Date(string='Date', help='Test date',
            required=False)

    @staticmethod
    def default_date():
        return datetime.date(2000, 1, 1)


class DateRequired(ModelSQL):
    'Date Required'
    __name__ = 'test.date_required'
    date = fields.Date(string='Date', help='Test date',
            required=True)


def register(module):
    Pool.register(
        Date,
        DateDefault,
        DateRequired,
        module=module, type_='model')

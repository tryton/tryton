# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class DateTime(ModelSQL):
    'DateTime'
    __name__ = 'test.datetime'
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=False)


class DateTimeDefault(ModelSQL):
    'DateTime Default'
    __name__ = 'test.datetime_default'
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=False)

    @staticmethod
    def default_datetime():
        return datetime.datetime(2000, 1, 1, 12, 0, 0, 0)


class DateTimeRequired(ModelSQL):
    'DateTime Required'
    __name__ = 'test.datetime_required'
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=True)


class DateTimeFormat(ModelSQL):
    'DateTime Format'
    __name__ = 'test.datetime_format'
    datetime = fields.DateTime(string='DateTime', format='%H:%M')


def register(module):
    Pool.register(
        DateTime,
        DateTimeDefault,
        DateTimeRequired,
        DateTimeFormat,
        module=module, type_='model')

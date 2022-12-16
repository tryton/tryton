# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Time(ModelSQL):
    'Time'
    __name__ = 'test.time'
    time = fields.Time(string='Time', help='Test time', required=False)


class TimeDefault(ModelSQL):
    'Time Default'
    __name__ = 'test.time_default'
    time = fields.Time(string='Time', help='Test time', required=False)

    @staticmethod
    def default_time():
        return datetime.time(16, 30)


class TimeRequired(ModelSQL):
    'Time'
    __name__ = 'test.time_required'
    time = fields.Time(string='Time', help='Test time', required=True)


class TimeFormat(ModelSQL):
    'Time Format'
    __name__ = 'test.time_format'
    time = fields.Time(string='Time', format='%H:%M')


def register(module):
    Pool.register(
        Time,
        TimeDefault,
        TimeRequired,
        TimeFormat,
        module=module, type_='model')

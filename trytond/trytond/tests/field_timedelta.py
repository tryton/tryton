# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class TimeDelta(ModelSQL):
    'TimeDelta'
    __name__ = 'test.timedelta'
    timedelta = fields.TimeDelta(string='TimeDelta', help='Test timedelta',
        required=False)


class TimeDeltaDefault(ModelSQL):
    'TimeDelta Default'
    __name__ = 'test.timedelta_default'
    timedelta = fields.TimeDelta(string='TimeDelta', help='Test timedelta',
        required=False)

    @staticmethod
    def default_timedelta():
        return datetime.timedelta(seconds=3600)


class TimeDeltaRequired(ModelSQL):
    'TimeDelta Required'
    __name__ = 'test.timedelta_required'
    timedelta = fields.TimeDelta(string='TimeDelta', help='Test timedelta',
        required=True)


def register(module):
    Pool.register(
        TimeDelta,
        TimeDeltaDefault,
        TimeDeltaRequired,
        module=module, type_='model')

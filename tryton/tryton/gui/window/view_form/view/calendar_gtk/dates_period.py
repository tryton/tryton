# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime


class DatesPeriod():
    """
    This class represents a period of time between two dates or two datetimes.
    """

    def __init__(self, start, end):
        assert type(start) == type(end)
        self.start = start
        self.end = end

    def is_in(self, period):
        return self.start >= period.start and self.end <= period.end

    def get_dates(self, format_datetime=False):
        if not format_datetime:
            return self.start, self.end

        midnight = datetime.time(0)
        start = datetime.datetime.combine(self.start, midnight)
        end = datetime.datetime.combine(self.end, midnight)
        return start, end

    def __str__(self):
        string = self.start.__str__() + ' => ' + self.end.__str__()
        return string

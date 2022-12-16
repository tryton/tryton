# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from unittest import TestCase

from tryton.common.timedelta import format, parse, DEFAULT_CONVERTER


class TimeDeltaTestCase(TestCase):
    "Test common timedelta"

    def _format_values(self):
        return [
            (None, ''),
            (dt.timedelta(), '00:00'),
            (dt.timedelta(days=3, hours=5, minutes=30), '3d 05:30'),
            (dt.timedelta(weeks=48), '11M 6d'),
            (dt.timedelta(weeks=50), '11M 2w 6d'),
            (dt.timedelta(weeks=52), '12M 4d'),
            (dt.timedelta(days=360), '12M'),
            (dt.timedelta(days=364), '12M 4d'),
            (dt.timedelta(days=365), '1Y'),
            (dt.timedelta(days=366), '1Y 1d'),
            (dt.timedelta(hours=2, minutes=5, seconds=10), '02:05:10'),
            (dt.timedelta(minutes=15, microseconds=42), '00:15:00.000042'),
            (dt.timedelta(days=1, microseconds=42), '1d .000042'),
            (dt.timedelta(seconds=-1), '-00:00:01'),
            (dt.timedelta(days=-1, hours=-5, minutes=-30), '-1d 05:30'),
            ]

    def _time_only_converter(self):
        converter = {}
        converter['s'] = DEFAULT_CONVERTER['s']
        converter['m'] = DEFAULT_CONVERTER['m']
        converter['h'] = DEFAULT_CONVERTER['h']
        converter['d'] = 0
        return converter

    def _time_only_converter_values(self):
        return [
            (None, ''),
            (dt.timedelta(), '00:00'),
            (dt.timedelta(days=5, hours=5, minutes=30), '125:30'),
            (dt.timedelta(hours=2, minutes=5, seconds=10), '02:05:10'),
            (dt.timedelta(minutes=15, microseconds=42), '00:15:00.000042'),
            (dt.timedelta(days=1, microseconds=42), '24:00:00.000042'),
            (dt.timedelta(seconds=-1), '-00:00:01'),
            (dt.timedelta(days=-1, hours=-5, minutes=-30), '-29:30'),
            ]

    def test_format(self):
        "Test format"
        for timedelta, text in self._format_values():
            self.assertEqual(format(timedelta), text,
                msg="format(%r)" % timedelta)

    def test_format_time_only_converter(self):
        "Test format with time only converter"
        converter = self._time_only_converter()
        for timedelta, text in self._time_only_converter_values():
            self.assertEqual(format(timedelta, converter), text,
                msg="format(%r)" % timedelta)

    def _parse_values(self):
        return self._format_values() + [
            (dt.timedelta(), '  '),
            (dt.timedelta(), 'foo'),
            (dt.timedelta(days=1.5), '1.5d'),
            (dt.timedelta(days=-2), '1d -1d'),
            (dt.timedelta(hours=1, minutes=5, seconds=10), '1:5:10:42'),
            (dt.timedelta(hours=2), '1: 1:'),
            (dt.timedelta(hours=.25), ':15'),
            (dt.timedelta(hours=1), '1h'),
            (dt.timedelta(hours=.25), '.25h'),
            ]

    def test_parse(self):
        "Test parse"
        for timedelta, text in self._parse_values():
            self.assertEqual(parse(text), timedelta,
                msg="parse(%r)" % text)

    def test_parse_time_only_converter(self):
        "Test parse with time only converter"
        converter = self._time_only_converter()
        for timedelta, text in self._time_only_converter_values():
            self.assertEqual(parse(text, converter), timedelta,
                msg="parse(%r)" % text)

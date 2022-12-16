# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
import gettext
import locale
import operator

__all__ = ['format', 'parse']

_ = gettext.gettext

DEFAULT_CONVERTER = {
    's': 1,
    }
DEFAULT_CONVERTER['m'] = DEFAULT_CONVERTER['s'] * 60
DEFAULT_CONVERTER['h'] = DEFAULT_CONVERTER['m'] * 60
DEFAULT_CONVERTER['d'] = DEFAULT_CONVERTER['h'] * 24
DEFAULT_CONVERTER['w'] = DEFAULT_CONVERTER['d'] * 7
DEFAULT_CONVERTER['M'] = DEFAULT_CONVERTER['d'] * 30
DEFAULT_CONVERTER['Y'] = DEFAULT_CONVERTER['d'] * 365


def _get_separators():
    return {
        'Y': _('Y'),
        'M': _('M'),
        'w': _('w'),
        'd': _('d'),
        'h': _('h'),
        'm': _('m'),
        's': _('s'),
        }


def format(value, converter=None):
    'Convert timedelta to text'
    if value is None:
        return ''
    if not converter:
        converter = DEFAULT_CONVERTER

    text = []
    value = value.total_seconds()
    sign = ''
    if value < 0:
        sign = '-'
    value = abs(value)
    converter = sorted(list(converter.items()), key=operator.itemgetter(1),
        reverse=True)
    values = []
    for k, v in converter:
        part = value // v
        value -= part * v
        values.append(part)

    for (k, _), v in zip(converter[:-3], values):
        if v:
            text.append(
                locale.format_string('%d', v, True) + _get_separators()[k])
    if any(values[-3:]) or not text:
        time = '%02d:%02d' % tuple(values[-3:-1])
        if values[-1] or value:
            time += ':%02d' % values[-1]
        text.append(time)
    text = sign + ' '.join(text)
    if value:
        if not any(values[-3:]):
            # Add space if no time
            text += ' '
        text += ('%.6f' % value)[1:]
    return text


def parse(text, converter=None):
    if not text:
        return
    if not converter:
        converter = DEFAULT_CONVERTER

    for separator in list(_get_separators().values()):
        text = text.replace(separator, separator + ' ')

    seconds = 0
    for part in text.split():
        if ':' in part:
            for t, v in zip(part.split(':'),
                    [converter['h'], converter['m'], converter['s']]):
                try:
                    seconds += abs(locale.atof(t)) * v
                except ValueError:
                    pass
        else:
            for key, separator in list(_get_separators().items()):
                if part.endswith(separator):
                    part = part[:-len(separator)]
                    try:
                        seconds += abs(locale.atof(part)) * converter[key]
                    except ValueError:
                        pass
                    break
            else:
                try:
                    seconds += abs(locale.atof(part))
                except ValueError:
                    pass

    if '-' in text:
        seconds *= -1
    return datetime.timedelta(seconds=seconds)


_tests = [
    (None, ''),
    (datetime.timedelta(), '00:00'),
    (datetime.timedelta(days=3, hours=5, minutes=30), '3d 05:30'),
    (datetime.timedelta(weeks=48), '11M 6d'),
    (datetime.timedelta(weeks=50), '11M 2w 6d'),
    (datetime.timedelta(weeks=52), '12M 4d'),
    (datetime.timedelta(days=360), '12M'),
    (datetime.timedelta(days=364), '12M 4d'),
    (datetime.timedelta(days=365), '1Y'),
    (datetime.timedelta(days=366), '1Y 1d'),
    (datetime.timedelta(hours=2, minutes=5, seconds=10), '02:05:10'),
    (datetime.timedelta(minutes=15, microseconds=42), '00:15:00.000042'),
    (datetime.timedelta(days=1, microseconds=42), '1d .000042'),
    (datetime.timedelta(seconds=-1), '-00:00:01'),
    (datetime.timedelta(days=-1, hours=-5, minutes=-30), '-1d 05:30'),
    ]


def test_format():
    for timedelta, text in _tests:
        assert format(timedelta) == text


_tests_parse = [
    (datetime.timedelta(), '  '),
    (datetime.timedelta(), 'foo'),
    (datetime.timedelta(days=1.5), '1.5d'),
    (datetime.timedelta(days=-2), '1d -1d'),
    (datetime.timedelta(hours=1, minutes=5, seconds=10), '1:5:10:42'),
    (datetime.timedelta(hours=2), '1: 1:'),
    (datetime.timedelta(hours=.25), ':15'),
    (datetime.timedelta(hours=1), '1h'),
    (datetime.timedelta(hours=.25), '.25h'),
    ]


def test_parse():
    for timedelta, text, in _tests + _tests_parse:
        assert parse(text) == timedelta


if __name__ == '__main__':
    for name in list(globals()):
        if name.startswith('test_'):
            func = globals()[name]
            func()

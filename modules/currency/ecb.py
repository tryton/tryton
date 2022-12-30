# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import ssl
import sys

try:
    from lxml import etree as ET
except ImportError:
    try:
        import xml.etree.cElementTree as ET
    except ImportError:
        import xml.etree.ElementTree as ET

from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import urlopen

_URL = 'https://www.ecb.europa.eu/stats/eurofxref/'
_URL_TODAY = _URL + 'eurofxref-daily.xml'
_URL_90 = _URL + 'eurofxref-hist-90d.xml'
_URL_HIST = _URL + 'eurofxref-hist.xml'
_START_DATE = dt.date(1999, 1, 4)
_CUBE_TAG = '{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}Cube'


class RatesNotAvailableError(Exception):
    pass


class UnsupportedCurrencyError(Exception):
    pass


def _parse_time(time):
    return dt.datetime.strptime(time, '%Y-%m-%d').date()


def _find_time(source, time=None):
    for _, element in ET.iterparse(source):
        if element.tag == _CUBE_TAG and 'time' in element.attrib:
            if time and _parse_time(element.attrib.get('time')) <= time:
                return element
            elif time is None:
                return element
            element.clear()


def get_rates(currency='EUR', date=None):
    if date is None:
        date = dt.date.today()
    if date < _START_DATE:
        date = _START_DATE
    context = ssl.create_default_context()
    try:
        with urlopen(_URL_TODAY, context=context) as response:
            element = _find_time(response)
            last_date = _parse_time(element.attrib['time'])
            if last_date < date:
                raise RatesNotAvailableError()
            elif last_date == date:
                return _compute_rates(element, currency, date)

        if last_date - date < dt.timedelta(days=90):
            url = _URL_90
        else:
            url = _URL_HIST
        with urlopen(url, context=context) as response:
            element = _find_time(response, date)
            if element is None and url == _URL_90:
                with urlopen(_URL_HIST, context=context) as response:
                    element = _find_time(response, date)
            return _compute_rates(element, currency, date)
    except HTTPError as e:
        raise RatesNotAvailableError() from e


def _compute_rates(element, currency, date):
    currencies = {}
    for cur in element:
        currencies[cur.attrib['currency']] = Decimal(cur.attrib['rate'])
    if currency != 'EUR':
        currencies['EUR'] = Decimal(1)
        try:
            base_rate = currencies.pop(currency)
        except KeyError:
            raise UnsupportedCurrencyError(f'{currency} is not available')
        for cur, rate in currencies.items():
            currencies[cur] = (rate / base_rate).quantize(Decimal('.0001'))
    return currencies


if __name__ == '__main__':
    currency = 'EUR'
    if len(sys.argv) > 1:
        currency = sys.argv[1]
    date = None
    if len(sys.argv) > 2:
        date = dt.datetime.strptime(sys.argv[2], '%Y-%m-%d').date()
    print(get_rates(currency, date))

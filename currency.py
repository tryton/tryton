# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
from decimal import Decimal

import requests
from lxml import etree

from trytond.config import config
from trytond.modules.currency.currency import CronFetchError
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

URL_10DAYS = 'https://bnr.ro/nbrfxrates10days.xml'
URL_YEAR = 'https://bnr.ro/files/xml/years/nbrfxrates%s.xml'
TIMEOUT = config.getfloat('currency_ro', 'requests_timeout', default=300)


class Cron(metaclass=PoolMeta):
    __name__ = 'currency.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.source.selection.append(('bnr_ro', "Romanian National Bank"))
        cls.currency.domain = [
            cls.currency.domain or [],
            If(Eval('source') == 'bnr_ro',
                ('code', '=', 'RON'),
                ()),
            ]

    def fetch_bnr_ro(self, date):
        if (dt.date.today() - date).days < 10:
            url = URL_10DAYS
        else:
            url = URL_YEAR % date.year
        try:
            response = requests.get(url, timeout=TIMEOUT)
        except requests.HTTPError as e:
            raise CronFetchError() from e
        tree = etree.fromstring(response.content)

        origin, = tree.xpath(
            '//x:Body/x:OrigCurrency',
            namespaces={'x': 'http://www.bnr.ro/xsd'})
        assert origin.text == self.currency.code

        cubes = tree.xpath(
            '//x:Body/x:Cube[@date="%s"]' % date.isoformat(),
            namespaces={'x': 'http://www.bnr.ro/xsd'})
        if cubes:
            cube, = cubes
            return {
                r.get('currency'): (
                    Decimal(r.get('multiplier', 1)) / Decimal(r.text))
                for r in cube.iter('{*}Rate')}
        else:
            return {}

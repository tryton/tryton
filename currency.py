# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from lxml import objectify
from zeep import Client, Transport
from zeep.exceptions import Error

from trytond.cache import Cache
from trytond.config import config
from trytond.model import fields
from trytond.modules.currency.currency import CronFetchError
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

URL = (
    'https://webservices.nbs.rs/CommunicationOfficeService1_0/'
    'ExchangeRateXmlService.asmx?WSDL')
TIMEOUT = config.getfloat('currency_rs', 'requests_timeout', default=300)


def get_client(username, password, license_id):
    client = Client(URL, transport=Transport(operation_timeout=TIMEOUT))
    client.set_default_soapheaders({
            'AuthenticationHeader': {
                'UserName': username,
                'Password': password,
                'LicenceID': license_id,
                },
            })
    return client


class Cron(metaclass=PoolMeta):
    __name__ = 'currency.cron'

    _states = {
        'required': Eval('source') == 'nbs_rs',
        'invisible': Eval('source') != 'nbs_rs',
        }

    rs_username = fields.Char("Username", states=_states)
    rs_password = fields.Char("Password", states=_states)
    rs_license_id = fields.Char("License ID", states=_states)
    rs_list_type = fields.Selection(
        'get_rs_list_types', "List Type", states=_states)
    _rs_list_types = Cache(__name__ + '.get_rs_list_types', context=False)

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.source.selection.append(('nbs_rs', "Serbian National Bank"))
        cls.currency.domain = [
            cls.currency.domain or [],
            If(Eval('source') == 'nbs_rs',
                ('code', '=', 'RSD'),
                ()),
            ]

    @fields.depends('rs_username', 'rs_password', 'rs_license_id')
    def _rs_client(self):
        return get_client(
            self.rs_username, self.rs_password, self.rs_license_id)

    @fields.depends('rs_list_type', methods=['_rs_client'])
    def get_rs_list_types(self):
        types = self._rs_list_types.get(None)
        if types is not None:
            return types
        try:
            client = self._rs_client()
            response = client.service.GetExchangeRateListType()
        except Error:
            return [(self.rs_list_type, self.rs_list_type or "")]
        types = []
        data = objectify.fromstring(response)
        for list_type in data.iterchildren():
            types.append(
                (str(list_type.ExchangeRateListTypeID), str(list_type.Name)))
        self._rs_list_types.set(None, types)
        return types

    def fetch_nbs_rs(self, date):
        try:
            client = self._rs_client()
            response = client.service.GetExchangeRateByDate(
                date.strftime('%Y%m%d'), self.rs_list_type)
        except Error as e:
            raise CronFetchError() from e
        data = objectify.fromstring(response)
        return {
            r.CurrencyCodeAlfaChar: (
                Decimal(r.Unit.text) / Decimal(r.MiddleRate.text))
            for r in data.iterchildren()
            if r.Date == date.strftime('%d.%m.%Y')}

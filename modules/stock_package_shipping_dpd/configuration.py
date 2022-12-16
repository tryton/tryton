# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from urllib.parse import urljoin
from zeep import Client
from zeep.transports import Transport

from trytond.config import config

SERVER_URLS = {
    'testing': 'https://public-ws-stage.dpd.com/services/',
    'production': 'https://public-ws.dpd.com/services/',
    }

LOGIN_SERVICE = 'LoginService/V2_0?wsdl'
SHIPMENT_SERVICE = 'ShipmentService/V3_2?wsdl'


def get_client(server, service):
    api_base_url = config.get('stock_package_shipping_dpd',
        server, default=SERVER_URLS[server])
    url = urljoin(api_base_url, service)
    # Disable the cache for testing because zeep's bug
    # https://github.com/mvantellingen/python-zeep/issues/48
    # which makes testing environments fail
    transport = (Transport(cache=None)
        if url.startswith(SERVER_URLS['testing']) else None)
    return Client(url, transport=transport)

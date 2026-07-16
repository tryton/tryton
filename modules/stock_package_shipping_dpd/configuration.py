# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from urllib.parse import urljoin

from zeep import Client
from zeep.cache import InMemoryCache
from zeep.transports import Transport

import trytond.config as config

SERVER_URLS = {
    'testing': 'https://public-ws-stage.dpd.com/services/',
    'production': 'https://public-ws.dpd.com/services/',
    }

LOGIN_SERVICE = 'LoginService/V2_0/?wsdl'
SHIPMENT_SERVICE = 'ShipmentService/V4_5/?wsdl'


def get_client(server, service):
    api_base_url = config.get('stock_package_shipping_dpd',
        server, default=SERVER_URLS[server])
    url = urljoin(api_base_url, service)
    timeout = config.get(
        'stock_package_shipping_dpd', 'requests_timeout', default=300)
    transport = Transport(cache=InMemoryCache(), operation_timeout=timeout)
    return Client(url, transport=transport)

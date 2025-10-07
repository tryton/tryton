# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib

from zeep import Client
from zeep.transports import Transport

import trytond.config as config

URLS = {
    'testing': 'https://api.test.mygls.%(country)s/%(service)s.svc?singleWsdl',
    'production': 'https://api.mygls.%(country)s/%(service)s.svc?singleWsdl',
    }


def get_client(credential, service):
    url = URLS[credential.server] % {
        'country': credential.country,
        'service': service,
        }
    timeout = config.get(
        'stock_package_shipping_mygls', 'requests_timeout', default=300)
    return Client(url, transport=Transport(operation_timeout=timeout))


def get_request(credential, name, **kwargs):
    return {
        name: {
            'Username': credential.username,
            'Password': hashlib.sha512(credential.password.encode()).digest(),
            **kwargs,
            },
        }

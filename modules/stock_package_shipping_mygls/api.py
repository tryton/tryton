# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib

from zeep import Client
from zeep.transports import Transport

from trytond.config import config

URLS = {
    'testing': 'https://api.test.mygls.%(country)s/%(service)s.svc?singleWsdl',
    'production': 'https://api.mygls.%(country)s/%(service)s.svc?singleWsdl',
    }
TIMEOUT = config.get(
    'stock_package_shipping_mygls', 'requests_timeout', default=300)


def get_client(credential, service):
    url = URLS[credential.server] % {
        'country': credential.country,
        'service': service,
        }
    return Client(url, transport=Transport(operation_timeout=TIMEOUT))


def get_request(credential, name, **kwargs):
    return {
        name: {
            'Username': credential.username,
            'Password': hashlib.sha512(credential.password.encode()).digest(),
            **kwargs,
            },
        }

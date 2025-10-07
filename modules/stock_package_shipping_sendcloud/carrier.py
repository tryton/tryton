# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import time
from functools import wraps

import requests

import trytond.config as config
from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.protocols.wrappers import HTTPStatus
from trytond.pyson import Eval, If

from .exceptions import SendcloudCredentialWarning, SendcloudError

SENDCLOUD_API_URL = 'https://panel.sendcloud.sc/api/v2/'
HEADERS = {
    'Sendcloud-Partner-Id': '03c1facb-63da-4bb1-889c-192fc91ec4e6',
    }


def sendcloud_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        nb_tries, error_message = 0, ''
        try:
            while nb_tries < 5:
                try:
                    return func(*args, **kwargs)
                except requests.HTTPError as e:
                    if e.response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                        error_message = e.args[0]
                        nb_tries += 1
                        time.sleep(1)
                    else:
                        raise
        except requests.HTTPError as e:
            error_message = e.args[0]
        raise SendcloudError(
            gettext('stock_package_shipping_sendcloud'
                '.msg_sendcloud_webserver_error',
                message=error_message))
    return wrapper


class CredentialSendcloud(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'carrier.credential.sendcloud'

    company = fields.Many2One('company.company', "Company")
    public_key = fields.Char("Public Key", required=True, strip=False)
    secret_key = fields.Char("Secret Key", required=True, strip=False)

    addresses = fields.One2Many(
        'carrier.sendcloud.address', 'sendcloud', "Addresses",
        states={
            'readonly': ~Eval('id') | (Eval('id', -1) < 0),
            })
    shipping_methods = fields.One2Many(
        'carrier.sendcloud.shipping_method', 'sendcloud', "Methods",
        states={
            'readonly': ~Eval('id') | (Eval('id', -1) < 0),
            })

    _addresses_sender_cache = Cache(
        'carrier.credential.sendcloud.addresses_sender',
        duration=config.getint(
            'stock_package_shipping_sendcloud', 'addresses_cache',
            default=15 * 60),
        context=False)
    _shiping_methods_cache = Cache(
        'carrier.credential.sendcloud.shipping_methods',
        duration=config.getint(
            'stock_package_shipping_sendcloud', 'shipping_methods_cache',
            default=60 * 60))

    @property
    def auth(self):
        return self.public_key, self.secret_key

    @property
    @sendcloud_api
    def addresses_sender(self):
        addresses = self._addresses_sender_cache.get(self.id)
        if addresses is not None:
            return addresses
        timeout = config.getfloat(
            'stock_package_shipping_sendcloud', 'requests_timeout',
            default=300)
        response = requests.get(
            SENDCLOUD_API_URL + 'user/addresses/sender',
            auth=self.auth, timeout=timeout, headers=HEADERS)
        response.raise_for_status()
        addresses = response.json()['sender_addresses']
        self._addresses_sender_cache.set(self.id, addresses)
        return addresses

    def get_sender_address(self, shipment_or_warehouse, pattern=None):
        pattern = pattern.copy() if pattern is not None else {}
        if shipment_or_warehouse.__name__ == 'stock.location':
            warehouse = shipment_or_warehouse
            pattern['warehouse'] = warehouse.id
        else:
            shipment = shipment_or_warehouse
            pattern['warehouse'] = shipment.shipping_warehouse.id
        for address in self.addresses:
            if address.match(pattern):
                return int(address.address) if address.address else None

    @sendcloud_api
    def get_shipping_methods(
            self, sender_address=None, service_point=None, is_return=False):
        key = (self.id, sender_address, service_point, is_return)
        methods = self._shiping_methods_cache.get(key)
        if methods is not None:
            return methods
        params = {}
        if sender_address:
            params['sender_address'] = sender_address
        if service_point:
            params['service_point'] = service_point
        if is_return:
            params['is_return'] = is_return
        timeout = config.getfloat(
            'stock_package_shipping_sendcloud', 'requests_timeout',
            default=300)
        response = requests.get(
            SENDCLOUD_API_URL + 'shipping_methods', params=params,
            auth=self.auth, timeout=timeout, headers=HEADERS)
        response.raise_for_status()
        methods = response.json()['shipping_methods']
        self._shiping_methods_cache.set(key, methods)
        return methods

    def get_shipping_method(self, shipment, package=None):
        pattern = self._get_shipping_method_pattern(shipment, package=package)
        for method in self.shipping_methods:
            if method.match(pattern):
                if method.shipping_method:
                    return int(method.shipping_method)
                else:
                    return None

    @classmethod
    def _get_shipping_method_pattern(cls, shipment, package=None):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')
        kg = UoM(ModelData.get_id('product', 'uom_kilogram'))

        if package:
            weight = UoM.compute_qty(
                package.weight_uom, package.total_weight, kg, round=False)
        else:
            weight = UoM.compute_qty(
                shipment.weight_uom, shipment.weight, kg, round=False)
        return {
            'carrier': shipment.carrier.id if shipment.carrier else None,
            'weight': weight,
            }

    @sendcloud_api
    def get_parcel(self, id):
        timeout = config.getfloat(
            'stock_package_shipping_sendcloud', 'requests_timeout',
            default=300)
        response = requests.get(
            SENDCLOUD_API_URL + 'parcels/%s' % id,
            auth=self.auth, timeout=timeout, headers=HEADERS)
        response.raise_for_status()
        return response.json()['parcel']

    @sendcloud_api
    def create_parcels(self, parcels):
        timeout = config.getfloat(
            'stock_package_shipping_sendcloud', 'requests_timeout',
            default=300)
        response = requests.post(
            SENDCLOUD_API_URL + 'parcels', json={'parcels': parcels},
            auth=self.auth, timeout=timeout, headers=HEADERS)
        if response.status_code == 400:
            msg = response.json()['error']['message']
            raise requests.HTTPError(msg, response=response)
        response.raise_for_status()
        return response.json()['parcels']

    @sendcloud_api
    def get_label(self, url):
        timeout = config.getfloat(
            'stock_package_shipping_sendcloud', 'requests_timeout',
            default=300)
        response = requests.get(
            url, auth=self.auth, timeout=timeout, headers=HEADERS)
        response.raise_for_status()
        return response.content

    @classmethod
    def check_modification(
            cls, mode, credentials, values=None, external=False):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        super().check_modification(
            mode, credentials, values=values, external=external)
        if (mode == 'write'
                and external
                and values.keys() & {'public_key', 'secret_key'}):
            warning_name = Warning.format(
                'sendcloud_credential', credentials)
            if Warning.check(warning_name):
                raise SendcloudCredentialWarning(
                    warning_name,
                    gettext('stock_package_shipping_sendcloud'
                        '.msg_sendcloud_credential_modified'))


class SendcloudAddress(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'carrier.sendcloud.address'

    sendcloud = fields.Many2One(
        'carrier.credential.sendcloud', "Sendcloud", required=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse",
        domain=[
            ('type', '=', 'warehouse'),
            ])
    address = fields.Selection(
        'get_addresses', "Address",
        help="Leave empty for the Sendcloud default.")

    @fields.depends('sendcloud', '_parent_sendcloud.id')
    def get_addresses(self):
        addresses = [('', "")]
        if (self.sendcloud
                and self.sendcloud.id is not None
                and self.sendcloud.id >= 0):
            for address in self.sendcloud.addresses_sender:
                addresses.append(
                    (str(address['id']), self._format_address(address)))
        return addresses

    @classmethod
    def _format_address(cls, address):
        return ', '.join(
            filter(None, [
                    address.get('company_name'),
                    address.get('street'),
                    address.get('house_number'),
                    address.get('postal_code'),
                    address.get('city'),
                    address.get('country')]))


class SendcloudShippingMethod(
        sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'carrier.sendcloud.shipping_method'

    sendcloud = fields.Many2One(
        'carrier.credential.sendcloud', "Sendcloud", required=True)
    carrier = fields.Many2One(
        'carrier', "Carrier",
        domain=[
            ('shipping_service', '=', 'sendcloud'),
            ])
    warehouse = fields.Many2One(
        'stock.location', "Warehouse",
        domain=[
            ('type', '=', 'warehouse'),
            ])
    min_weight = fields.Float(
        "Minimal Weight",
        domain=[
            ['OR',
                ('min_weight', '=', None),
                ('min_weight', '>', 0),
                ],
            If(Eval('max_weight', 0),
                ('min_weight', '<=', Eval('max_weight', 0)),
                ()),
            ],
        help="Minimal weight included in kg.")
    max_weight = fields.Float(
        "Maximal Weight",
        domain=[
            ['OR',
                ('max_weight', '=', None),
                ('max_weight', '>', 0),
                ],
            If(Eval('min_weight', 0),
                ('max_weight', '>=', Eval('min_weight', 0)),
                ()),
            ],
        help="Maximal weight included in kg.")
    shipping_method = fields.Selection(
        'get_shipping_methods', "Shipping Method")

    @fields.depends('sendcloud', 'warehouse', '_parent_sendcloud.id')
    def get_shipping_methods(self, pattern=None):
        methods = [(None, '')]
        if (self.sendcloud
                and self.sendcloud.id is not None
                and self.sendcloud.id >= 0):
            if self.warehouse:
                sender_address = self.sendcloud.get_sender_address(
                    self.warehouse, pattern=pattern)
            else:
                sender_address = None
            methods += [
                (str(m['id']), m['name'])
                for m in self.sendcloud.get_shipping_methods(
                    sender_address=sender_address)]
        return methods

    def match(self, pattern, match_none=False):
        pattern = pattern.copy()
        if (weight := pattern.pop('weight')) is not None:
            min_weight = self.min_weight or 0
            max_weight = self.max_weight or weight
            if not (min_weight <= weight <= max_weight):
                return False
        return super().match(pattern, match_none=match_none)


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    sendcloud_format = fields.Selection([
            ('normal 0', "A4 - Top left"),
            ('normal 1', "A4 - Top right"),
            ('normal 2', "A4 - Bottom left"),
            ('normal 3', "A4 - Bottom right"),
            ('label', "A6 - Full page"),
            ], "Format",
        states={
            'invisible': Eval('shipping_service') != 'sendcloud',
            'required': Eval('shipping_service') == 'sendcloud',
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipping_service.selection.append(('sendcloud', "Sendcloud"))

    @classmethod
    def default_sendcloud_format(cls):
        return 'label'

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ("/form/separator[@id='sendcloud']", 'states', {
                    'invisible': Eval('shipping_service') != 'sendcloud',
                    }),
            ]

    @property
    def shipping_label_mimetype(self):
        mimetype = super().shipping_label_mimetype
        if self.shipping_service == 'sendcloud':
            mimetype = 'application/pdf'
        return mimetype

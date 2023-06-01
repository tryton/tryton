# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class CredentialUPS(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'UPS Credential'
    __name__ = 'carrier.credential.ups'
    _rec_name = 'account_number'

    company = fields.Many2One('company.company', 'Company')
    client_id = fields.Char("Client ID", required=True)
    client_secret = fields.Char("Client Secret", required=True)
    account_number = fields.Char('Account Number', required=True)
    use_metric = fields.Boolean('Use Metric')
    server = fields.Selection([
            ('testing', 'Testing'),
            ('production', 'Production'),
            ], 'Server')

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        super().__register__(module)

        # Migration from 6.8: switch to OAuth
        table_h.drop_column('user_id')
        table_h.drop_column('password')
        table_h.drop_column('license')

    @classmethod
    def default_use_metric(cls):
        return True

    @classmethod
    def default_server(cls):
        return 'testing'

    def get_token(self):
        if self.server == 'production':
            url = 'https://onlinetools.ups.com/security/v1/oauth/token'
        else:
            url = 'https://wwwcie.ups.com/security/v1/oauth/token'
        client = BackendApplicationClient(client_id=self.client_id)
        oauth = OAuth2Session(client=client)
        token = oauth.fetch_token(
            token_url=url, client_id=self.client_id,
            client_secret=self.client_secret)
        return token['access_token']

    def get_shipment_url(self):
        if self.server == 'production':
            return 'https://onlinetools.ups.com/api/shipments/v1/ship'
        else:
            return 'https://wwwcie.ups.com/api/shipments/v1/ship'


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    ups_service_type = fields.Selection([
            (None, ''),
            ('01', 'Next Day Air'),
            ('02', '2nd Day Air'),
            ('03', 'Ground'),
            ('07', 'Express'),
            ('08', 'Expedited'),
            ('11', 'UPS Standard'),
            ('12', '3 Days Select'),
            ('13', 'Next Day Air Saver'),
            ('14', 'UPS Next Day Air Early'),
            ('17', "UPS Worldwide Economy DDU"),
            ('54', 'Express Plus'),
            ('59', '2nd Day Air A.M.'),
            ('65', 'UPS Saver'),
            ('M2', 'First Class Mail'),
            ('M3', 'Priority Mail'),
            ('M4', 'Expedited Mail Innovations'),
            ('M5', 'Priority Mail Innovations'),
            ('M6', 'Economy Mail Innovations'),
            ('M7', "Mail Innovations (MI) Returns"),
            ('70', 'UPS Access Point Economy'),
            ('71', "UPS Worldwide Express Freight Midday"),
            ('72', "UPS Worldwide Economy DDP"),
            ('74', "UPS Express 12:00"),
            ('82', 'UPS Today Standard'),
            ('83', 'UPS Today Dedicated Courier'),
            ('84', 'UPS Today Intercity'),
            ('85', 'UPS Today Express'),
            ('86', 'UPS Today Express Saver'),
            ('96', 'UPS Worldwide Express Freight'),
            ], 'Service Type', sort=False, translate=False,
        states={
            'required': Eval('shipping_service') == 'ups',
            'invisible': Eval('shipping_service') != 'ups',
            })
    ups_label_image_format = fields.Selection([
            (None, ''),
            ('EPL', 'EPL2'),
            ('SPL', 'SPL'),
            ('ZPL', 'ZPL'),
            ('GIF', 'GIF'),
            ('STARPL', 'Star Printer'),
            ], 'Label Image Format', sort=False, translate=False,
        states={
            'required': Eval('shipping_service') == 'ups',
            'invisible': Eval('shipping_service') != 'ups',
            })
    ups_label_height = fields.Selection([
            (None, ''),
            ('6', '6'),
            ('8', '8'),
            ], 'Label Height', sort=False, translate=False,
        states={
            'required': ((Eval('shipping_service') == 'ups')
                & (Eval('ups_label_image_format') != 'GIF')),
            'invisible': ((Eval('shipping_service') != 'ups')
                | (Eval('ups_label_image_format') == 'GIF')),
            })
    ups_notifications = fields.MultiSelection([
            ('5', "Quantum View In-transit"),
            ('6', "Quantum View Shop"),
            ('7', "Quantum View Exception"),
            ('8', "Quantum View Delivery"),
            ('2', "Return or Label Creation"),
            ('012', "Alternate Delivery Location"),
            ('013', "UPS Access Point Shipper"),
            ], "Notifications", sort=False,
        states={
            'invisible': Eval('shipping_service') != 'ups',
            })

    @classmethod
    def __setup__(cls):
        super(Carrier, cls).__setup__()
        cls.shipping_service.selection.append(('ups', 'UPS'))

    @classmethod
    def view_attributes(cls):
        return super(Carrier, cls).view_attributes() + [
            ("/form/separator[@id='ups']", 'states', {
                    'invisible': Eval('shipping_service') != 'ups',
                    }),
            ]

    @property
    def shipping_label_mimetype(self):
        mimetype = super().shipping_label_mimetype
        if self.shipping_service == 'ups':
            if self.ups_label_image_format == 'GIF':
                mimetype = 'image/gif'
        return mimetype

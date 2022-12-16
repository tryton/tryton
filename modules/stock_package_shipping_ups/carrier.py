# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, MatchMixin, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class CredentialUPS(ModelSQL, ModelView, MatchMixin):
    'UPS Credential'
    __name__ = 'carrier.credential.ups'

    company = fields.Many2One('company.company', 'Company')
    user_id = fields.Char('User ID', required=True)
    password = fields.Char('Password', required=True)
    license = fields.Char('License', required=True)
    account_number = fields.Char('Account Number', required=True)
    use_metric = fields.Boolean('Use Metric')
    server = fields.Selection([
            ('testing', 'Testing'),
            ('production', 'Production'),
            ], 'Server')

    @classmethod
    def default_use_metric(cls):
        return True

    @classmethod
    def default_server(cls):
        return 'testing'


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
            ('54', 'Express Plus'),
            ('59', '2nd Day Air A.M.'),
            ('65', 'UPS Saver'),
            ('M2', 'First Class Mail'),
            ('M3', 'Priority Mail'),
            ('M4', 'Expedited Mail Innovations'),
            ('M5', 'Priority Mail Innovations'),
            ('M6', 'Economy Mail Innovations'),
            ('70', 'UPS Access Point Economy'),
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
            },
        depends=['shipping_service'])
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
            },
        depends=['shipping_service'])
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
            },
        depends=['shipping_service', 'ups_label_image_format'])

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

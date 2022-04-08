# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If


class CredentialMyGLS(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    "MyGLS Credential"
    __name__ = 'carrier.credential.mygls'

    company = fields.Many2One('company.company', "Company")
    server = fields.Selection([
            ('testing', "Testing"),
            ('production', "Production"),
            ], "Server", required=True)
    country = fields.Selection([
            ('hr', "Croatia"),
            ('cz', "Czechia"),
            ('hu', "Hungary"),
            ('ro', "Romania"),
            ('si', "Slovenia"),
            ('sk', "Slovakia"),
            ], "Country", required=True)
    username = fields.Char("Username", required=True)
    password = fields.Char("Password", required=True)
    client_number = fields.Integer("Client Number", required=True)

    @classmethod
    def default_server(cls):
        return 'testing'


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    mygls_type_of_printer = fields.Selection([
            (None, ''),
            ('A4_2x2', "A4 2x2"),
            ('A4_4x1', "A4 4x1"),
            ('Connect', "Connect"),
            ('Thermo', "Thermo"),
            ], "Type of Printer", sort=False, translate=False,
        states={
            'invisible': Eval('shipping_service') != 'mygls',
            })
    mygls_print_position = fields.Integer(
        "Print Position",
        domain=[
            If(Eval('mygls_type_of_printer') == 'A4_2x2',
                ('mygls_print_position', 'in', [1, 2, 3, 4]),
                ('mygls_print_position', '=', None)),
            ],
        states={
            'required': Eval('mygls_type_of_printer') == 'A4_2x2',
            'invisible': (
                (Eval('mygls_type_of_printer') != 'A4_2x2')
                | (Eval('shipping_service') != 'mygls')),
            })
    mygls_services = fields.MultiSelection([
            ('24h', "Service guaranteed delivery shipment in 24 Hours"),
            ('AOS', "Addressee Only Service"),
            ('CS1', "Contact Service"),
            ('FDS', "Flexible Delivery Service"),
            ('FSS', "Flexible delivery Sms Service"),
            ('PRS', "Pick & Return Services"),
            ('PSS', "Pick & Ship Service"),
            ('SAT', "Saturday service"),
            ('SBS', "Stand By Service"),
            ('SM1', "SMS service"),
            ('SM2', "SMS pre-advice"),
            ('T09', "Express service (T09)"),
            ('T10', "Express service (T10)"),
            ('T12', "Express service (T12)"),
            ('TGS', "Think Green Service"),
            ('XS', "Exchange Service"),
            ], "Services",
        states={
            'invisible': Eval('shipping_service') != 'mygls',
            })

    mygls_sms = fields.Char(
        "SMS", translate=True,
        states={
            'invisible': Eval('shipping_service') != 'mygls',
            'required': Eval('mygls_services', []).contains('SM1'),
            },
        help="Variables that can be used in the text of the SMS:\n"
        "ParcelNr#, #COD#, #PickupDate#, #From_Name#, #ClientRef#")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipping_service.selection.append(('mygls', "MyGLS"))

    @classmethod
    def view_attributes(cls):
        return super(Carrier, cls).view_attributes() + [
            ("/form/separator[@id='mygls']", 'states', {
                    'invisible': Eval('shipping_service') != 'mygls',
                    }),
            ]

    @property
    def shipping_label_mimetype(self):
        mimetype = super().shipping_label_mimetype
        if self.shipping_service == 'mygls':
            mimetype = 'application/pdf'
        return mimetype

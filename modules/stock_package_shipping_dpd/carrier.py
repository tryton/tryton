# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import locale

from zeep.exceptions import Fault

from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from .configuration import LOGIN_SERVICE, get_client
from .exceptions import DPDCredentialWarning, DPDError


class CredentialDPD(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'carrier.credential.dpd'

    company = fields.Many2One('company.company', 'Company')
    user_id = fields.Char('User ID', required=True, strip=False)
    password = fields.Char('Password', required=True, strip=False)
    server = fields.Selection([
            ('testing', 'Testing'),
            ('production', 'Production'),
            ], 'Server')
    depot = fields.Char('Depot', readonly=True, strip=False)
    token = fields.Char('Token', readonly=True, strip=False)

    @classmethod
    def default_server(cls):
        return 'testing'

    def update_token(self):
        auth_client = get_client(self.server, LOGIN_SERVICE)
        lang = (self.company.party.lang.code
            if self.company.party.lang else 'en')
        lang = locale.normalize(lang)[:5]
        try:
            result = auth_client.service.getAuth(
                delisId=self.user_id, password=self.password,
                messageLanguage=lang)
        except Fault as e:
            error_message = e.detail[0].find('errorMessage')
            raise DPDError(
                gettext('stock_package_shipping_dpd.msg_dpd_webservice_error',
                    message=error_message.text)) from e

        self.token = result.authToken
        self.depot = result.depot
        self.save()

    @classmethod
    def check_modification(
            cls, mode, credentials, values=None, external=False):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        super().check_modification(
            mode, credentials, values=values, external=external)
        if (mode == 'write'
                and external
                and values.keys() & {'user_id', 'password', 'server'}):
            warning_name = Warning.format('dpd_credential', credentials)
            if Warning.check(warning_name):
                raise DPDCredentialWarning(
                    warning_name,
                    gettext('stock_package_shipping_dpd'
                        '.msg_dpd_credential_modified'))


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    dpd_product = fields.Selection([
            (None, ''),
            ('CL', "DPD CLASSIC"),
            ('E830', "DPD 8:30"),
            ('E10', "DPD 10:00"),
            ('E12', "DPD 12:00"),
            ('E18', "DPD 18:00"),
            ('IE2', "DPD EXPRESS"),
            ('PL', "DPD PARCEL Letter"),
            ('PL+', "DPD PARCEL Letter Plus"),
            ('MAIL', "DPD International Mail"),
            ], "Product", sort=False, translate=False,
        states={
            'required': Eval('shipping_service') == 'dpd',
            'invisible': Eval('shipping_service') != 'dpd',
            })
    dpd_printer_language = fields.Selection([
            (None, ''),
            ('PDF', "PDF"),
            ('ZPL', "ZPL"),
            ], "Printer Language", sort=False, translate=False,
        states={
            'required': Eval('shipping_service') == 'dpd',
            'invisible': Eval('shipping_service') != 'dpd',
            })
    dpd_paper_format = fields.Selection([
            (None, ''),
            ('A4', "A4"),
            ('A6', "A6"),
            ('A7', "A7"),
            ], "Paper Format", sort=False, translate=False,
        states={
            'required': Eval('shipping_service') == 'dpd',
            'invisible': Eval('shipping_service') != 'dpd',
            })

    dpd_notification = fields.Selection([
            (None, ""),
            ('email', "Email"),
            ('sms', "SMS"),
            ], "Notification",
        states={
            'invisible': Eval('shipping_service') != 'dpd',
            },
        help="The preferred notification channel.\n"
        "Leave empty for no notification.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipping_service.selection.append(('dpd', 'DPD'))

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ("/form/separator[@id='dpd']", 'states', {
                    'invisible': Eval('shipping_service') != 'dpd',
                    }),
            ]

    @property
    def shipping_label_mimetype(self):
        mimetype = super().shipping_label_mimetype
        if self.shipping_service == 'dpd':
            mimetype = 'application/pdf'
        return mimetype

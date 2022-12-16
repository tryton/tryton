# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import locale

from zeep.exceptions import Fault

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, MatchMixin, fields
from trytond.pool import PoolMeta

from .configuration import get_client, LOGIN_SERVICE
from .exceptions import DPDError


class CredentialDPD(ModelSQL, ModelView, MatchMixin):
    'DPD Credential'
    __name__ = 'carrier.credential.dpd'

    company = fields.Many2One('company.company', 'Company')
    user_id = fields.Char('User ID', required=True)
    password = fields.Char('Password', required=True)
    server = fields.Selection([
            ('testing', 'Testing'),
            ('production', 'Production'),
            ], 'Server')
    depot = fields.Char('Depot', readonly=True)
    token = fields.Char('Token', readonly=True)

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


class Carrier(metaclass=PoolMeta):
    __name__ = 'carrier'

    @classmethod
    def __setup__(cls):
        super(Carrier, cls).__setup__()
        cls.shipping_service.selection.append(('dpd', 'DPD'))

# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from base64 import b64decode, b64encode
from functools import wraps
from io import BytesIO
from urllib.parse import urljoin

import requests
from lxml import etree

from trytond.i18n import gettext
from trytond.model import fields
from trytond.modules.edocument_peppol.exceptions import PeppolServiceError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .exceptions import PeppyrusCredentialWarning, PeppyrusError

URLS = {
    'testing': 'https://api.test.peppyrus.be/v1/',
    'production': 'https://api.peppyrus.be/v1/',
    }


def peppyrus_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as e:
            error_message = e.response.text or e.args[0]
            raise PeppyrusError(
                gettext('edocument_peppol_peppyrus'
                    '.msg_peppyrus_webserver_error',
                    message=error_message)) from e
    return wrapper


class PeppolService(metaclass=PoolMeta):
    __name__ = 'edocument.peppol.service'

    peppyrus_api_key = fields.Char(
        "API Key",
        states={
            'invisible': Eval('service') != 'peppyrus',
            'required': Eval('service') == 'peppyrus',
            })
    peppyrus_server = fields.Selection([
            (None, ""),
            ('testing', "Testing"),
            ('production', "Production"),
            ], "Server",
        states={
            'invisible': Eval('service') != 'peppyrus',
            'required': Eval('service') == 'peppyrus',
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.service.selection.append(('peppyrus', "Peppyrus"))

    @fields.depends('service', 'peppyrus_server')
    def on_change_service(self):
        if (self.service == 'peppyrus'
                and not self.peppyrus_server):
            self.peppyrus_server = 'testing'

    @peppyrus_api
    def _post_peppyrus(self, document):
        tree = etree.parse(BytesIO(document.data))
        response = requests.post(
            urljoin(URLS[self.peppyrus_server], 'message'),
            json={
                'sender': self._peppyrus_sender(document.type, tree),
                'recipient': self._peppyrus_recipient(document.type, tree),
                'processType': (
                    self._peppyrus_process_type(document.type, tree)),
                'documentType': (
                    self._peppyrus_document_type(document.type, tree)),
                'fileContent': b64encode(document.data).decode(),
                },
            headers={
                'Accept': 'application/json',
                'X-Api-Key': self.peppyrus_api_key,
                })
        if response.status_code == 422:
            raise PeppolServiceError(response.json())
        response.raise_for_status()
        return response.json()['id']

    def _peppyrus_sender(self, type, tree):
        if type == 'bis-billing-3':
            el = tree.find(
                './/{*}AccountingSupplierParty/{*}Party/{*}EndpointID')
            if el is not None:
                scheme = el.get('schemeID', '')
                return f'{scheme}:{el.text}'

    def _peppyrus_recipient(self, type, tree):
        if type == 'bis-billing-3':
            el = tree.find(
                './/{*}AccountingCustomerParty/{*}Party/{*}EndpointID')
            if el is not None:
                scheme = el.get('schemeID', '')
                return f'{scheme}:{el.text}'

    def _peppyrus_process_type(self, type, tree):
        if type == 'bis-billing-3':
            return 'cenbii-procid-ubl::' + tree.findtext('.//{*}ProfileID')

    def _peppyrus_document_type(self, type, tree):
        if type == 'bis-billing-3':
            return (
                'busdox-docid-qns::'
                'urn:oasis:names:specification:ubl:'
                'schema:xsd:Invoice-2::Invoice##'
                + tree.findtext('.//{*}CustomizationID') + '::2.1')

    @peppyrus_api
    def _update_status_peppyrus(self, document):
        assert document.direction == 'out'
        response = requests.get(
            urljoin(
                URLS[self.peppyrus_server],
                f'message/{document.transmission_id}'),
            headers={
                'Accept': 'application/json',
                'X-Api-Key': self.peppyrus_api_key,
                })
        response.raise_for_status()
        message = response.json()
        assert message['id'] == document.transmission_id
        if message['folder'] == 'sent':
            document.succeed()
        elif message['folder'] == 'failed':
            document.fail(status=self._peppyrus_status(document))

    @peppyrus_api
    def _peppyrus_status(self, document):
        response = requests.get(
            urljoin(
                URLS[self.peppyrus_server],
                f'message/{document.transmission_id}/report'),
            headers={
                'Accept': 'application/json',
                'X-Api-Key': self.peppyrus_api_key,
                })
        response.raise_for_status()
        report = response.json()
        return report.get('transmissionRules')

    @classmethod
    def peppyrus_fetch(cls, services=None):
        if services is None:
            services = cls.search([('service', '=', 'peppyrus')])
        for service in services:
            service._peppyrus_fetch()

    @peppyrus_api
    def _peppyrus_fetch(self):
        assert self.service == 'peppyrus'
        response = requests.get(
            urljoin(URLS[self.peppyrus_server], 'message/list'),
            params={
                'folder': 'INBOX',
                'confirmed': 'false',
                'perPage': 100,
                },
            headers={
                'Accept': 'application/json',
                'X-Api-Key': self.peppyrus_api_key,
                })
        response.raise_for_status()
        for message in response.json()['items']:
            self.__class__.__queue__.peppyrus_store(self, message)

    def peppyrus_store(self, message):
        pool = Pool()
        Document = pool.get('edocument.peppol')
        transaction = Transaction()
        assert message['direction'] == 'IN'

        def confirm(server, api_key, message, silent=False):
            try:
                response = requests.patch(
                    urljoin(
                        URLS[server],
                        f"message/{message['id']}/confirm"),
                    headers={
                        'Accept': 'application/json',
                        'X-Api-Key': api_key,
                        })
                if response.status_code != 404:
                    response.raise_for_status()
            except Exception:
                if not silent:
                    raise

        server = self.peppyrus_server
        api_key = self.peppyrus_api_key
        if Document.search([
                    ('service', '=', self.id),
                    ('transmission_id', '=', message['id']),
                    ]):
            confirm(server, api_key, message)
            return
        document = Document(
            direction='in',
            company=self.company,
            type=self._peppyrus_type(message['documentType']),
            service=self,
            data=b64decode(message['fileContent']),
            transmission_id=message['id'],
            )
        document.save()
        document.submit()
        transaction.atexit(confirm, server, api_key, message, True)

    @classmethod
    def _peppyrus_type(cls, document_type):
        if document_type == (
                'busdox-docid-qns::urn:oasis:names:specification:ubl:'
                'schema:xsd:Invoice-2::Invoice##'
                'urn:cen.eu:en16931:2017#compliant#'
                'urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1'):
            return 'bis-billing-3'

    @classmethod
    def check_modification(cls, mode, services, values=None, external=False):
        pool = Pool()
        Warning = pool.get('res.user.warning')

        super().check_modification(
            mode, services, values=values, external=external)

        if mode == 'write' and external and 'peppyrus_api_key' in values:
            warning_name = Warning.format('peppyrus_credential', services)
            if Warning.check(warning_name):
                raise PeppyrusCredentialWarning(
                    warning_name,
                    gettext('edocument_peppol_peppyrus'
                        '.msg_peppyrus_credential_modified'))

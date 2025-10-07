# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import datetime
import logging
import posixpath
from collections import defaultdict

from oauthlib.oauth2 import BackendApplicationClient, TokenExpiredError
from requests_oauthlib import OAuth2Session
from sql.functions import CharLength

import trytond.config as config
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Unique, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction

from .exceptions import ChorusCredentialWarning, InvoiceChorusValidationError

OAUTH_TOKEN_URL = {
    'service-qualif': 'https://sandbox-oauth.piste.gouv.fr/api/oauth/token',
    'service': 'https://oauth.piste.gouv.fr/api/oauth/token',
    }
API_URL = {
    'service-qualif': 'https://sandbox-api.piste.gouv.fr',
    'service': 'https://api.piste.gouv.fr',
    }
EDOC2SYNTAX = {
    'edocument.uncefact.invoice': 'IN_DP_E1_CII_16B',
    }
EDOC2FILENAME = {
    'edocument.uncefact.invoice': 'UNCEFACT-%s.xml',
    }
if config.getboolean('account_fr_chorus', 'filestore', default=False):
    file_id = 'data_file_id'
    store_prefix = config.get(
        'account_payment_sepa', 'store_prefix', default=None)
else:
    file_id = None
    store_prefix = None

logger = logging.getLogger(__name__)


SUCCEEDED = {'IN_INTEGRE', 'IN_RECU', 'IN_TRAITE_SE_CPP'}
FAILED = {
    'IN_INCIDENTE', 'QP_IRRECEVABLE', 'QP_RECEVABLE_AVEC_ERREUR', 'IN_REJETE'}


class _SyntaxMixin(object):
    __slots__ = ()

    @classmethod
    def get_syntaxes(cls):
        pool = Pool()
        syntaxes = [(None, "")]
        try:
            doc = pool.get('edocument.uncefact.invoice')
        except KeyError:
            pass
        else:
            syntaxes.append((doc.__name__, "CII"))
        return syntaxes


class Configuration(_SyntaxMixin, metaclass=PoolMeta):
    __name__ = 'account.configuration'

    _states = {
        'required': Bool(Eval('chorus_login')),
        }

    chorus_piste_client_id = fields.MultiValue(
        fields.Char("Piste Client ID", strip=False))
    chorus_piste_client_secret = fields.MultiValue(
        fields.Char("Piste Client Secret", strip=False, states=_states))
    chorus_login = fields.MultiValue(fields.Char("Login", strip=False))
    chorus_password = fields.MultiValue(fields.Char(
            "Password", strip=False, states=_states))
    chorus_service = fields.MultiValue(fields.Selection([
                (None, ""),
                ('service-qualif', "Qualification"),
                ('service', "Production"),
                ], "Service", states=_states))
    chorus_syntax = fields.Selection(
        'get_syntaxes', "Syntax", states=_states)

    del _states

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {
                'chorus_piste_client_id', 'chorus_piste_client_secret',
                'chorus_login', 'chorus_password', 'chorus_service'}:
            return pool.get('account.credential.chorus')
        return super().multivalue_model(field)


class CredentialChorus(ModelSQL, CompanyValueMixin):
    __name__ = 'account.credential.chorus'

    chorus_piste_client_id = fields.Char("Piste Client ID", strip=False)
    chorus_piste_client_secret = fields.Char(
        "Piste Client Secret", strip=False)
    chorus_login = fields.Char("Login", strip=False)
    chorus_password = fields.Char("Password", strip=False)
    chorus_service = fields.Selection([
            (None, ""),
            ('service-qualif', "Qualification"),
            ('service', "Production"),
            ], "Service")

    @classmethod
    def get_session(cls):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        client = BackendApplicationClient(
            client_id=config.chorus_piste_client_id)
        session = OAuth2Session(client=client)
        cls._get_token(session)
        return session

    @classmethod
    def _get_token(cls, session):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        return session.fetch_token(
            OAUTH_TOKEN_URL[config.chorus_service],
            client_id=config.chorus_piste_client_id,
            client_secret=config.chorus_piste_client_secret)

    @classmethod
    def post(cls, path, payload, session=None):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        configuration = Configuration(1)
        if not session:
            session = cls.get_session()
        base_url = API_URL[configuration.chorus_service]
        url = posixpath.join(base_url, path)
        account = (
            f'{configuration.chorus_login}:{configuration.chorus_password}')
        headers = {
            'cpro-account': base64.b64encode(account.encode('utf-8')),
            }
        timeout = config.getfloat(
            'account_fr_chorus', 'requests_timeout', default=300)
        try:
            resp = session.post(
                url, headers=headers, json=payload,
                verify=True, timeout=timeout)
        except TokenExpiredError:
            cls._get_token(session)
            resp = session.post(
                url, headers=headers, json=payload,
                verify=True, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def check_modification(cls, mode, records, values=None, external=False):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        super().check_modification(
            mode, records, values=values, external=external)
        if mode == 'write' and external:
            for record in records:
                for field in [
                        'chorus_piste_client_id', 'chorus_piste_client_secret',
                        'chorus_login', 'chorus_password', 'chorus_service']:
                    if (field in values
                            and getattr(record, field)
                            and getattr(record, field) != values[field]):
                        warning_name = Warning.format(
                            'chorus_credential', [record])
                        if Warning.check(warning_name):
                            raise ChorusCredentialWarning(
                                warning_name,
                                gettext('account_fr_chorus'
                                    '.msg_chorus_credential_modified'))


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        InvoiceChorus = pool.get('account.invoice.chorus')
        posted_invoices = {
            i for i in invoices if i.state in {'draft', 'validated'}}
        super()._post(invoices)
        invoices_chorus = []
        for invoice in posted_invoices:
            if invoice.type == 'out' and invoice.party.chorus:
                invoices_chorus.append(InvoiceChorus(invoice=invoice))
        InvoiceChorus.save(invoices_chorus)


class InvoiceChorus(
        Workflow, ModelSQL, ModelView, _SyntaxMixin, metaclass=PoolMeta):
    __name__ = 'account.invoice.chorus'
    _history = True

    invoice = fields.Many2One(
        'account.invoice', "Invoice", required=True,
        domain=[
            ('type', '=', 'out'),
            ('state', 'in', If(Bool(Eval('number')),
                    ['posted', 'paid'],
                    ['posted'])),
            ])
    syntax = fields.Selection('get_syntaxes', "Syntax", required=True)
    filename = fields.Function(fields.Char("Filename"), 'get_filename')
    number = fields.Char(
        "Number", readonly=True, strip=False,
        states={
            'required': Eval('state') == 'sent',
            })
    date = fields.Date(
        "Date", readonly=True,
        states={
            'required': Eval('state') == 'sent',
            })
    data = fields.Binary(
        "Data", filename='filename',
        file_id=file_id, store_prefix=store_prefix, readonly=True)
    data_file_id = fields.Char("Data File ID", readonly=True)
    state = fields.Selection([
            ('draft', "Draft"),
            ('sent', "Sent"),
            ('done', "Done"),
            ('exception', "Exception"),
            ], "State", readonly=True, required=True, sort=False)

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        super().__setup__()

        t = cls.__table__()
        cls._sql_constraints = [
            ('invoice_unique', Unique(t, t.invoice),
                'account_fr_chorus.msg_invoice_unique'),
            ]

        cls._transitions |= {
            ('draft', 'sent'),
            ('sent', 'done'),
            ('sent', 'exception'),
            ('exception', 'sent'),
            }
        cls._buttons.update(
            send={
                'invisible': ~Eval('state').in_(['draft', 'exception']),
                'depends': ['state'],
                },
            update={
                'invisible': Eval('state') != 'sent',
                'depends': ['state'],
                },
            )

    @classmethod
    def __register__(cls, module):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        table_h = cls.__table_handler__(module)

        update_state = not table_h.column_exist('state')

        super().__register__(module)

        # Migration from 6.8: fill state
        if update_state:
            cursor.execute(*table.update([table.state], ['done']))

    @classmethod
    def default_syntax(cls):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        return config.chorus_syntax

    def get_filename(self, name):
        filename = EDOC2FILENAME[self.syntax] % self.invoice.number
        return filename.replace('/', '-')

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

    def get_rec_name(self, name):
        return self.invoice.rec_name

    @classmethod
    def validate(cls, records):
        super().validate(records)
        for record in records:
            addresses = [
                record.invoice.company.party.address_get('invoice'),
                record.invoice.invoice_address]
            for address in addresses:
                if not address.siret:
                    raise InvoiceChorusValidationError(
                        gettext('account_fr_chorus'
                            '.msg_invoice_address_no_siret',
                            invoice=record.invoice.rec_name,
                            address=address.rec_name))

    @classmethod
    def check_modification(cls, mode, invoices, values=None, external=False):
        super().check_modification(
            mode, invoices, values=values, external=external)
        if mode == 'delete':
            for invoice in invoices:
                if invoice.number:
                    raise AccessError(gettext(
                            'account_fr_chorus.msg_invoice_delete_sent',
                            invoice=invoice.rec_name))

    def _send_context(self):
        return {
            'company': self.invoice.company.id,
            }

    @classmethod
    @ModelView.button
    @Workflow.transition('sent')
    def send(cls, records=None):
        """Send invoice to Chorus

        The transaction is committed after each invoice.
        """
        pool = Pool()
        Credential = pool.get('account.credential.chorus')
        transaction = Transaction()

        if not records:
            records = cls.search([
                    ('invoice.company', '=',
                        transaction.context.get('company')),
                    ('state', '=', 'draft'),
                    ])

        sessions = defaultdict(Credential.get_session)
        cls.lock(records)
        for record in records:
            # Use clear cache after a commit
            record = cls(record.id)
            record.lock()
            context = record._send_context()
            with transaction.set_context(**context):
                payload = record.get_payload()
                resp = Credential.post(
                    'cpro/factures/v1/deposer/flux', payload,
                    session=sessions[tuple(context.items())])
                if resp['codeRetour']:
                    logger.error(
                        "Error when sending invoice %d to chorus: %s",
                        record.id, resp['libelle'])
                else:
                    record.number = resp['numeroFluxDepot']
                    record.date = datetime.datetime.strptime(
                        resp['dateDepot'], '%Y-%m-%d').date()
                    record.state = 'sent'
                    record.save()
            Transaction().commit()

    def get_payload(self):
        pool = Pool()
        Doc = pool.get(self.syntax)
        with Transaction().set_context(account_fr_chorus=True):
            self.data = Doc(self.invoice).render(None)
        return {
            'fichierFlux': base64.b64encode(self.data).decode('ascii'),
            'nomFichier': self.filename,
            'syntaxeFlux': EDOC2SYNTAX[self.syntax],
            'avecSignature': False,
            }

    @classmethod
    @ModelView.button
    def update(cls, records=None):
        "Update state from Chorus"
        pool = Pool()
        Credential = pool.get('account.credential.chorus')
        transaction = Transaction()

        if not records:
            records = cls.search([
                    ('invoice.company', '=',
                        transaction.context.get('company')),
                    ('state', '=', 'sent'),
                    ])

        sessions = defaultdict(Credential.get_session)
        succeeded, failed = [], []
        for record in records:
            if not record.number:
                continue
            context = record._send_context()
            with transaction.set_context(**context):
                payload = {
                    'numeroFluxDepot': record.number,
                    }
                resp = Credential.post(
                    'cpro/transverses/v1/consulterCR', payload,
                    session=sessions[tuple(context.items())])
                if resp['codeRetour']:
                    logger.info(
                        "Error when retrieve information about %d: %s",
                        record.id, resp['libelle'])
                elif resp['etatCourantFlux'] in SUCCEEDED:
                    succeeded.append(record)
                elif resp['etatCourantFlux'] in FAILED:
                    failed.append(record)
        if failed:
            cls.fail(failed)
        if succeeded:
            cls.succeed(succeeded)

    @classmethod
    @Workflow.transition('done')
    def succeed(cls, records):
        pass

    @classmethod
    @Workflow.transition('exception')
    def fail(cls, records):
        pass

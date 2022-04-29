# This file is part of Tryton. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from itertools import chain, groupby

from requests import Session
from zeep import Client
from zeep.exceptions import Error as ZeepError
from zeep.transports import Transport

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Unique, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

from .exceptions import ESSIIPostedInvoicesError

CERT = (
    config.get('account_es_sii', 'certificate'),
    config.get('account_es_sii', 'privatekey'))
SEND_SIZE = 10000


SII_URL = [
    (None, ""),
    ('aeat', "AEAT"),
    ('guipuzkoa', "Guipuzkoa"),
    # XXX: URLs for basque country and navarra should be added
    ]
WS_URL = {
    'aeat': ('https://www2.agenciatributaria.gob.es/static_files/'
        'common/internet/dep/aplicaciones/es/aeat/ssii_1_1/fact/ws/'),
    'guipuzkoa': (
        'https://egoitza.gipuzkoa.eus/ogasuna/sii/ficheros/v1.1/'),
    }


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    es_sii_url = fields.MultiValue(
        fields.Selection(
            SII_URL, "SII URL", translate=False,
            help="The URL where the invoices should be sent."))
    es_sii_environment = fields.MultiValue(fields.Selection([
                (None, ""),
                ('staging', "Staging"),
                ('production', "Production"),
                ], "SII Environment",
            states={
                'required': Bool(Eval('es_sii_url')),
                }))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'es_sii_url', 'es_sii_environment'}:
            return pool.get('account.credential.sii')
        return super().multivalue_model(field)


class CredentialSII(ModelSQL, CompanyValueMixin):
    "Account Credential SII"
    __name__ = 'account.credential.sii'

    es_sii_url = fields.Selection(SII_URL, "SII URL", translate=False)
    es_sii_environment = fields.Selection([
            (None, ""),
            ('staging', "Staging"),
            ('production', "Production"),
            ], "SII Environment")

    @classmethod
    def get_client(cls, endpoint, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        url = WS_URL.get(config.get_multivalue('es_sii_url', **pattern), '')
        if not url:
            raise AccessError(
                gettext('account_es_sii.msg_missing_sii_url'))
        service = endpoint
        environment = config.get_multivalue('es_sii_environment', **pattern)
        session = Session()
        session.cert = CERT
        transport = Transport(session=session)
        client = Client(url + endpoint + '.wsdl', transport=transport)
        if environment == 'staging':
            # Set guipuzkoa testing service
            if 'egoitza.gipuzkoa.eus' in url:
                client.create_service(
                    next(iter(client.wsdl.bindings.keys())),
                    'https://sii-prep.egoitza.gipuzkoa.eus/JBS/HACI/'
                    'SSII-FACT/')
            else:
                service += 'Pruebas'
        return client.bind('siiService', service)


class TaxTemplate(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    es_sii_tax_key = fields.Char("SII Tax Key")
    es_sii_operation_key = fields.Char("SII Operation Key")
    es_exclude_from_sii = fields.Boolean("Exclude from SII")

    def _get_tax_value(self, tax=None):
        values = super()._get_tax_value(tax)
        for name in [
                'es_sii_tax_key', 'es_sii_operation_key',
                'es_exclude_from_sii']:
            if not tax or getattr(tax, name) != getattr(self, name):
                values[name] = getattr(self, name)
        return values


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    _states = {
        'readonly': (Bool(Eval('template', -1))
            & ~Eval('template_override', False)),
        }
    es_sii_tax_key = fields.Char("SII Tax Key", states=_states)
    es_sii_operation_key = fields.Char("SII Operation Key", states=_states)
    es_exclude_from_sii = fields.Boolean("Exclude from SII", states=_states)
    del _states


class FiscalYear(metaclass=PoolMeta):
    __name__ = 'account.fiscalyear'

    es_sii_send_invoices = fields.Function(
        fields.Boolean("Send invoices to SII"),
        'get_es_sii_send_invoices', setter='set_es_sii_send_invoices')

    def get_es_sii_send_invoices(self, name):
        result = None
        for period in self.periods:
            if period.type != 'standard':
                continue
            value = period.es_sii_send_invoices
            if value is not None:
                if result is None:
                    result = value
                elif result != value:
                    result = None
                    break
        return result

    @classmethod
    def set_es_sii_send_invoices(cls, fiscalyears, name, value):
        pool = Pool()
        Period = pool.get('account.period')

        periods = []
        for fiscalyear in fiscalyears:
            periods.extend(
                p for p in fiscalyear.periods if p.type == 'standard')
        Period.write(periods, {name: value})


class Period(metaclass=PoolMeta):
    __name__ = 'account.period'
    es_sii_send_invoices = fields.Boolean(
        "Send invoices to SII",
        states={
            'invisible': Eval('type') != 'standard',
            },
        help="Check to create SII records for the invoices in the period.")

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        to_check = []
        for periods, values in zip(actions, actions):
            if 'es_sii_send_invoices' in values:
                for period in periods:
                    if (period.es_sii_send_invoices
                            != values['es_sii_send_invoices']):
                        to_check.append(period)
        cls.check_es_sii_posted_invoices(to_check)
        super().write(*args)

    @classmethod
    def check_es_sii_posted_invoices(cls, periods):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        for sub_ids in grouped_slice(list(map(int, periods))):
            invoices = Invoice.search([
                    ('move.period', 'in', sub_ids),
                    ], limit=1)
            if invoices:
                invoice, = invoices
                raise ESSIIPostedInvoicesError(
                    gettext('account_es_sii.msg_es_sii_posted_invoices',
                        period=invoice.move.period.rec_name))


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def _post(cls, invoices):
        pool = Pool()
        InvoiceSII = pool.get('account.invoice.sii')
        posted_invoices = {
            i for i in invoices if i.state in {'draft', 'validated'}}
        super()._post(invoices)
        InvoiceSII.save([
                InvoiceSII(invoice=i) for i in posted_invoices
                if i.es_send_to_sii])

    @property
    def es_send_to_sii(self):
        if not self.move.period.es_sii_send_invoices:
            return False
        if not self.taxes:
            return True
        if all(t.tax.es_exclude_from_sii for t in self.taxes):
            return False
        return True

    @property
    def es_sii_party_tax_identifier(self):
        return self.party_tax_identifier or self.party.tax_identifier

    @property
    def es_sii_product_type_detail(self):
        country = None
        if self.es_sii_party_tax_identifier:
            country = self.es_sii_party_tax_identifier.es_country()
        return self.type == 'out' and country != 'ES'


class InvoiceSII(ModelSQL, ModelView):
    "Invoice SII"
    __name__ = 'account.invoice.sii'

    invoice = fields.Many2One(
        'account.invoice', "Invoice", required=True, ondelete='RESTRICT',
        states={
            'readonly': Eval('state') != 'pending',
            },
        domain=[
            ('state', 'in', ['posted', 'paid', 'cancelled']),
            ])
    csv = fields.Char("CSV", readonly=True,
        help="A secure validation code that confirms the delivery of the "
        "related Invoice.")
    error_code = fields.Char("Error Code", readonly=True,
        states={
            'invisible': ~Bool(Eval('error_code')),
            })
    error_description = fields.Char("Error Description", readonly=True,
        states={
            'invisible': ~Bool(Eval('error_description')),
            })
    state = fields.Selection([
            ('pending', "Pending"),
            ('sent', "Sent"),
            ('wrong', "Wrong"),
            ('rejected', "Rejected"),
            ], "State", readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('invoice')

        t = cls.__table__()
        cls._sql_constraints = [
            ('invoice_unique', Unique(t, t.invoice),
                'account_es_sii.msg_es_sii_invoice_unique'),
            ]

    @classmethod
    def default_state(cls):
        return 'pending'

    def get_rec_name(self, name):
        return self.invoice.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('invoice.rec_name',) + tuple(clause[1:])]

    @classmethod
    def delete(cls, records):
        for record in records:
            if record.csv:
                raise AccessError(
                    gettext('account_es_sii.msg_es_sii_invoice_delete_sent',
                        invoice=record.invoice.rec_name))
        super().delete(records)

    @property
    def endpoint(self):
        if self.invoice.type == 'out':
            suffix = 'Emitidas'
        else:
            suffix = 'Recibidas'
        return 'SuministroFact%s' % suffix

    @property
    def invoice_type(self):
        tax_identifier = bool(self.invoice.es_sii_party_tax_identifier)
        if 'credit_note' in self.invoice._sequence_field:
            if tax_identifier:
                return 'R1'
            else:
                return 'R5'
        else:
            if tax_identifier:
                return 'F1'
            else:
                return 'F2'

    @property
    def operation_description(self):
        return self.invoice.description or '.'

    @classmethod
    def endpoint2method(cls, endpoint):
        return {
            'SuministroFactEmitidas': 'SuministroLRFacturasEmitidas',
            'SuministroFactRecibidas': 'SuministroLRFacturasRecibidas',
            }.get(endpoint)

    @classmethod
    def _grouping_key(cls, record):
        communication_type = 'A0'
        # Error 3000 means duplicated
        if (record.state == 'wrong'
                or (record.state == 'rejected'
                    and record.error_code == '3000')):
            communication_type = 'A1'
        return (
            ('endpoint', record.endpoint),
            ('company', record.invoice.company),
            ('tax_identifier', record.invoice.tax_identifier),
            ('communication_type', communication_type),
            # Split wrong/rejected to avoid rejection of correct new invoices
            ('new', record.state == 'pending'),
            )

    @classmethod
    def _credential_pattern(cls, key):
        return {
            'company': key['company'].id,
            }

    def set_state(self, response):
        self.state = {
            'Correcto': 'sent',
            'Anulada': 'sent',
            'Incorrecto': 'rejected',
            'AceptadoConErrores': 'wrong',
            }.get(response.EstadoRegistro, 'pending')

    @classmethod
    def set_error(cls, records, message, code):
        for record in records:
            record.error_description = message
            record.error_code = code
            record.state = 'rejected'

    @classmethod
    def send(cls, records=None):
        """
        Send invoices to SII

        The transaction is committed after each request (up to 10000 invoices).
        """
        pool = Pool()
        Credential = pool.get('account.credential.sii')
        transaction = Transaction()

        if not records:
            records = cls.search([
                    ('invoice.company', '=',
                        transaction.context.get('company')),
                    ('state', '!=', 'sent'),
                    ])
        else:
            records = list(filter(lambda r: r.state != 'sent', records))

        cls.lock(records)
        records = sorted(records, key=cls._grouping_key)
        for key, grouped_records in groupby(records, key=cls._grouping_key):
            key = dict(key)
            for sub_records in grouped_slice(list(grouped_records), SEND_SIZE):
                # Use clear cache after a commit
                sub_records = cls.browse(sub_records)
                cls.lock(sub_records)
                client = Credential.get_client(
                    key['endpoint'], **cls._credential_pattern(key))
                method = getattr(client, cls.endpoint2method(key['endpoint']))
                try:
                    resp = method(
                        cls.get_headers(key),
                        [r.get_payload() for r in sub_records])
                except ZeepError as e:
                    cls.set_error(sub_records, e.message, None)
                else:
                    for record, response in zip(
                            sub_records, resp.RespuestaLinea):
                        record.set_state(response)
                        if response.CodigoErrorRegistro:
                            record.error_code = response.CodigoErrorRegistro
                            record.error_description = (
                                response.DescripcionErrorRegistro)
                        else:
                            record.error_code = None
                            record.error_description = None
                        # The response has a CSV that's for all records
                        record.csv = response.CSV or resp.CSV
                cls.save(sub_records)
                transaction.commit()

    @classmethod
    def get_headers(cls, key):
        owner = {}
        tax_identifier = key['tax_identifier']
        if tax_identifier:
            owner = tax_identifier.es_sii_values()
        owner['NombreRazon'] = key['company'].rec_name
        return {
            'IDVersionSii': '1.1',
            'Titular': owner,
            'TipoComunicacion': key['communication_type'],
            }

    @classmethod
    def tax_grouping_key(cls, tax_line):
        pool = Pool()
        ModelData = pool.get('ir.model.data')

        if not tax_line.tax:
            return tuple()
        tax = tax_line.tax
        if tax.es_reported_with:
            tax = tax.es_reported_with
        if not tax.es_sii_operation_key:
            return tuple()
        invoice = tax_line.move_line.move.origin
        product_type = ''
        if invoice.es_sii_product_type_detail and tax.group:
            if tax.group.id == ModelData.get_id(
                    'account_es', 'tax_group_sale'):
                product_type = 'Entrega'
            elif tax.group.id == ModelData.get_id(
                    'account_es', 'tax_group_sale_service'):
                product_type = 'PrestacionServicios'
        return (
            ('cuota_suffix', (
                    'Repercutida' if invoice.type == 'out' else 'Soportada')),
            ('sii_key', tax.es_sii_tax_key or ''),
            ('operation_key', tax.es_sii_operation_key or ''),
            ('excluded', tax.es_exclude_from_sii),
            ('product_key', product_type),
            ('rate', tax.rate * 100),
            )

    @classmethod
    def get_tax_values(cls, key, tax_lines):
        if not key or key.get('excluded'):
            return

        base_amount = sum(
            t.amount for t in tax_lines
            if t.type == 'base' and not t.tax.es_reported_with)
        tax_amount = sum(
            t.amount for t in tax_lines
            if t.type == 'tax' and not t.tax.es_reported_with)
        values = {
            'BaseImponible': base_amount,
            'TipoImpositivo': str(key['rate']),
            'Cuota%s' % key['cuota_suffix']: tax_amount,
            }
        surcharge_taxes = list(t for t in tax_lines
            if t.type == 'tax' and t.tax.es_reported_with)
        if surcharge_taxes:
            values['CuotaRecargoEquivalencia'] = (
                sum(t.amount for t in surcharge_taxes))
            values['TipoRecargoEquivalencia'] = str(
                (surcharge_taxes[0].tax.rate * 100).normalize())

        return values

    def get_out_invoice_details(self, key, values):
        key = dict(key)
        sii_key = key['sii_key']
        subject_key = 'Sujeta'
        if sii_key[0] == 'E':
            values = {
                'Exenta': {
                    'DetalleExenta': {
                        'CausaExencion': sii_key,
                        'BaseImponible': sum(v['BaseImponible']
                            for v in values),
                        },
                    },
                }
        elif sii_key[0] == 'S':
            values = {
                'NoExenta': {
                        'TipoNoExenta': sii_key,
                        'DesgloseIVA': {
                            'DetalleIVA': values,
                            },
                        },
                }
        else:
            subject_key = 'NoSujeta'
            non_subject_key = ('ImporteTAIReglasLocalizacion'
                if sii_key == 'NSTAI'
                else 'ImportePorArticulos7_14_Otros')
            values = {
                non_subject_key: sum(v['BaseImponible']
                    for v in values),
                }
        detail_key = (subject_key, key['product_key'])
        return detail_key, values

    def get_invoice_detail(self,
            tax_values, operation_keys, total_amount, tax_amount):
        counterpart = {}
        invoice_type = self.invoice_type
        tax_identifier = self.invoice.es_sii_party_tax_identifier
        if tax_identifier:
            counterpart = tax_identifier.es_sii_values()
        counterpart['NombreRazon'] = self.invoice.party.name
        detail = {
            'TipoFactura': invoice_type,
            'DescripcionOperacion': self.operation_description,
            'RefExterna': self.invoice.rec_name,
            'Contraparte': counterpart,
            'ImporteTotal': str(total_amount),
            # XXX: Set FechaOperacion from stock moves
            }
        if invoice_type.startswith('R'):
            detail['TipoRectificativa'] = 'I'
        for idx, value in enumerate(operation_keys):
            key = 'ClaveRegimenEspecialOTrascendencia'
            if idx:
                key = '%sAdicional%d' % (key, idx)
            detail[key] = value
        if self.invoice.type == 'out':
            invoice_details = defaultdict(list)
            for key, values in tax_values.items():
                detail_key, detail_values = self.get_out_invoice_details(
                    key, values)
                invoice_details[detail_key].append(detail_values)
            detail['TipoDesglose'] = {}
            if self.invoice.es_sii_product_type_detail:
                detail['TipoDesglose'] = {
                    'DesgloseTipoOperacion': {},
                    }
                for key, invoice_detail in invoice_details.items():
                    subject_key, product_key = key
                    detail['TipoDesglose']['DesgloseTipoOperacion'][
                        product_key] = {
                            subject_key: invoice_detail,
                            }
            else:
                for key, invoice_detail in invoice_details.items():
                    subject_key, _ = key
                    detail['TipoDesglose'] = {
                        'DesgloseFactura': {
                            subject_key: invoice_detail,
                            },
                        }
        else:
            detail['DesgloseFactura'] = {
                # XXX: InversionSujetoPasivo
                'DesgloseIVA': {
                    'DetalleIVA': list(chain(*tax_values.values())),
                },
            }
            detail['FechaRegContable'] = self.invoice.move.post_date.strftime(
                '%d-%m-%Y')
            detail['CuotaDeducible'] = str(tax_amount)
        return detail

    def get_invoice_payload(self):
        tax_lines = list(chain(*(
                    l.tax_lines for l in self.invoice.move.lines)))
        tax_lines = sorted(tax_lines, key=self.tax_grouping_key)
        tax_values = defaultdict(list)
        operation_keys = set()
        total_amount = Decimal(0)
        tax_amount = Decimal(0)
        for tax_key, tax_lines in groupby(
                tax_lines, key=self.tax_grouping_key):
            key = dict(tax_key)
            values = self.get_tax_values(key, list(tax_lines))
            if not values:
                continue
            operation_keys.add(key['operation_key'])
            tax_amount += values["Cuota%s" % key['cuota_suffix']]
            total_amount += (
                values['BaseImponible']
                + values["Cuota%s" % key['cuota_suffix']])
            if 'CuotaRecargoEquivalencia' in values:
                total_amount += values['CuotaRecargoEquivalencia']
            tax_values[tax_key].append(values)
        return self.get_invoice_detail(
            tax_values, operation_keys, total_amount, tax_amount)

    def get_payload(self):
        if self.invoice.type == 'in':
            tax_identifier = self.invoice.es_sii_party_tax_identifier
            number = self.invoice.reference or self.invoice.number
        else:
            tax_identifier = self.invoice.tax_identifier
            number = self.invoice.number

        date = self.invoice.invoice_date
        payload = {
            'PeriodoLiquidacion': {
                'Ejercicio': "{:04}".format(self.invoice.move.date.year),
                'Periodo': "{:02}".format(self.invoice.move.date.month),
                },
            'IDFactura': {
                'IDEmisorFactura': (tax_identifier.es_sii_values()
                    if tax_identifier else {}),
                'NumSerieFacturaEmisor': number,
                'FechaExpedicionFacturaEmisor': date.strftime('%d-%m-%Y'),
                },
            }
        invoice_payload = self.get_invoice_payload()
        if self.invoice.type == 'in':
            payload['FacturaRecibida'] = invoice_payload
        else:
            payload['FacturaExpedida'] = invoice_payload
        return payload

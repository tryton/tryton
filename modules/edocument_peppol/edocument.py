# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.conditionals import NullIf
from sql.operators import Equal

import trytond.config as config
from trytond.model import (
    Exclude, MatchMixin, ModelSQL, ModelView, Workflow, dualmethod, fields,
    sequence_ordered)
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

from .exceptions import PeppolServiceError

if config.getboolean('edocument_peppol', 'filestore', default=True):
    file_id = 'file_id'
    store_prefix = config.get(
        'edocument_peppol', 'store_prefix', default=None)
else:
    file_id = store_prefix = None


class Peppol(Workflow, ModelSQL, ModelView):
    __name__ = 'edocument.peppol'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    direction = fields.Selection([
            ('in', "IN"),
            ('out', "OUT"),
            ], "Direction", required=True, states=_states)
    company = fields.Many2One(
        'company.company', "Company", required=True, states=_states)
    type = fields.Selection([
            (None, ""),
            ('bis-billing-3', "BIS Billing V3"),
            ], "Type", translate=False,
        states={
            'readonly': _states['readonly'],
            'required': Eval('state') != 'draft',
            })
    service = fields.Many2One(
        'edocument.peppol.service', "Service",
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('state') == 'draft',
                ('types', 'in', Eval('type')),
                ()),
            ],
        states={
            'readonly': _states['readonly'],
            'required': Eval('state') != 'draft',
            })
    invoice = fields.Many2One(
        'account.invoice', "Invoice", ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('direction') == 'out', [
                    ('type', '=', 'out'),
                    ('state', 'in', ['posted', 'paid']),
                    ], [
                    ('type', '=', 'in'),
                    ]),
            ],
        states={
            'readonly': _states['readonly'],
            'invisible': (
                ~Eval('type').in_([
                        'bis-billing-3',
                        ])
                | ((Eval('state') == 'draft')
                    & (Eval('direction') == 'in'))),
            'required': (
                (Eval('direction') == 'out')
                & Eval('type').in_([
                        'bis-billing-3',
                        ])),
            })
    data = fields.Binary(
        "Data",
        file_id=file_id, store_prefix=store_prefix,
        states={
            'invisible': (
                (Eval('state') == 'draft')
                & (Eval('direction') == 'out')),
            })
    file_id = fields.Char("File ID", readonly=False)
    transmission_id = fields.Char("Transmission ID", readonly=True)
    document_retried = fields.Many2One(
        'edocument.peppol', "Retry", readonly=True,
        states={
            'invisible': ~Eval('document_retried'),
            'required': Eval('state') == 'retried',
            })
    status = fields.Char(
        "Status", readonly=True,
        states={
            'invisible': ~Eval('status'),
            })
    state = fields.Selection([
            ('draft', "Draft"),
            ('submitted', "Submitted"),
            ('processing', "Processing"),
            ('succeeded', "Succeeded"),
            ('failed', "Failed"),
            ('retried', "Retried"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, required=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()

        t = cls.__table__()
        cls._sql_constraints += [
            ('service_transmission_id_unique',
                Exclude(t,
                    (t.service, Equal),
                    (NullIf(t.transmission_id, ''), Equal)),
                'edocument_peppol.msg_service_transmission_id_unique'),
            ]

        cls._transitions |= {
            ('draft', 'submitted'),
            ('submitted', 'processing'),
            ('processing', 'processing'),
            ('processing', 'succeeded'),
            ('processing', 'failed'),
            ('failed', 'retried'),
            ('failed', 'cancelled'),
            }
        cls._buttons.update(
            draft={
                'invisible': Eval('state') != 'submitted',
                'depends': ['state'],
                },
            submit={
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            process={
                'invisible': ~Eval('state').in_(['submitted', 'processing']),
                'depends': ['state'],
                },
            retry={
                'invisible': Eval('state') != 'failed',
                'depends': ['state'],
                },
            cancel={
                'invisible': Eval('state') != 'failed',
                'depends': ['state'],
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, documents):
        pass

    @dualmethod
    @ModelView.button
    @Workflow.transition('submitted')
    def submit(cls, documents):
        pool = Pool()
        Service = pool.get('edocument.peppol.service')
        for document in documents:
            if not document.service:
                document.service = Service.get_service(document)
            if document.direction == 'out':
                document.data = document.render()
        cls.save(documents)
        cls.__queue__.process(documents)

    def get_service_pattern(self):
        return {
            'type': self.type,
            }

    def render(self):
        pool = Pool()
        Invoice = pool.get('edocument.ubl.invoice')
        assert self.direction == 'out'
        if self.type == 'bis-billing-3':
            return Invoice(self.invoice).render(
                '2', specification='peppol-bis-3')

    @dualmethod
    @ModelView.button
    @Workflow.transition('processing')
    def process(cls, documents):
        cls.lock(documents)
        for document in documents:
            if document.direction == 'out':
                cls.__queue__._process(document)
            else:
                document._process()

    def _process(self):
        pool = Pool()
        Invoice = pool.get('edocument.ubl.invoice')
        if self.state != 'processing':
            return
        self.lock()
        if self.direction == 'out':
            if self.transmission_id:
                return
            try:
                self.transmission_id = self.service.post(self)
                self.save()
            except PeppolServiceError as e:
                self.fail(status=str(e))
        elif self.direction == 'in':
            if self.type == 'bis-billing-3':
                if self.invoice:
                    return
                self.invoice = Invoice.parse(self.data)
                self.succeeded()

    @classmethod
    def update_status(cls, documents=None):
        if documents is None:
            documents = cls.search([
                    ('direction', '=', 'out'),
                    ('state', '=', 'processing'),
                    ])
        for document in documents:
            document._update_status()
        cls.save(documents)

    def _update_status(self):
        assert self.direction == 'out'
        self.service.update_status(self)

    @dualmethod
    @Workflow.transition('succeeded')
    def succeed(cls, documents, status=None):
        cls.write(documents, {'status': status})

    @dualmethod
    @Workflow.transition('failed')
    def fail(cls, documents, status=None):
        cls.write(documents, {'status': status})

    @classmethod
    @Workflow.transition('retried')
    def retry(cls, documents):
        retries = cls.copy(documents)
        for document, retry in zip(documents, retries):
            document.document_retried = retry
        cls.save(documents)
        cls.submit(retries)

    @classmethod
    @Workflow.transition('cancelled')
    def cancel(cls, documents):
        pass

    @classmethod
    def copy(cls, documents, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('service')
        default.setdefault('data')
        default.setdefault('transmission_id')
        default.setdefault('document_retried')
        default.setdefault('status')
        return super().copy(documents, default=default)


class PeppolService(sequence_ordered(), MatchMixin, ModelSQL, ModelView):
    __name__ = 'edocument.peppol.service'

    company = fields.Many2One(
        'company.company', "Company", required=True)
    service = fields.Selection([
            ], "Service")
    types = fields.MultiSelection(
        'get_peppol_types', "Types",
        help="The types of document supported by the service provider.")

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def get_service(cls, document):
        pattern = document.get_service_pattern()
        for service in cls.search([('company', '=', document.company)]):
            if service.match(pattern):
                return service

    def match(self, pattern, match_none=False):
        if 'type' in pattern:
            pattern = pattern.copy()
            if pattern.pop('type') not in self.types:
                return False
        return super().match(pattern, match_none=match_none)

    @classmethod
    def get_peppol_types(cls):
        pool = Pool()
        Peppol = pool.get('edocument.peppol')
        return [
            (v, l) for v, l in Peppol.fields_get(['type'])['type']['selection']
            if v is not None]

    @classmethod
    def default_types(cls):
        return ['bis-billing-3']

    def post(self, document):
        if meth := getattr(self, f'_post_{self.service}', None):
            return meth(document)

    def update_status(self, document):
        if meth := getattr(self, f'_update_status_{self.service}', None):
            return meth(document)

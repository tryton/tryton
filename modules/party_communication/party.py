# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If, PYSONEncoder
from trytond.transaction import Transaction


class Purpose(DeactivableMixin, ModelSQL, ModelView):
    "Purpose"
    __name__ = 'party.communication.event.purpose'

    name = fields.Char("Name", required=True)


class CaseStatus(DeactivableMixin, sequence_ordered(), ModelSQL, ModelView):
    'Case Status'
    __name__ = 'party.communication.case.status'

    _get_default_status_cache = Cache(
        'party.communication_case_status.get_default_status')
    _get_window_domains_cache = Cache(
        'party.communication_case_status.get_window_domains')

    name = fields.Char("Name", required=True, translate=True)
    default = fields.Boolean(
        "Default", help="Check to use as default status.")
    count = fields.Boolean(
        "Count",
        help="Check to show the number of cases in this status.")

    @classmethod
    def get_default_status(cls):
        status = cls._get_default_status_cache.get(None, -1)
        if status != -1:
            return status
        records = cls.search([
                ('default', '=', True)
                ], limit=1)
        if records:
            status = records[0].id
        else:
            status = None
        cls._get_default_status_cache.set(None, status)
        return status

    @classmethod
    def create(cls, vlist):
        cls._get_default_status_cache.clear()
        cls._get_window_domains_cache.clear()
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        super().write(*args)
        cls._get_default_status_cache.clear()
        cls._get_window_domains_cache.clear()

    @classmethod
    def delete(cls, status):
        cls._get_default_status_cache.clear()
        cls._get_window_domains_cache.clear()
        super().delete(status)

    @classmethod
    def get_window_domains(cls, action):
        domains = cls._get_window_domains_cache.get(action.id)
        if domains is not None:
            return domains
        encoder = PYSONEncoder()
        domains = []
        for status in cls.search([]):
            domain = encoder.encode([('status', '=', status.id)])
            domains.append((status.name, domain, status.count))
        if domains:
            domains.append(
                (gettext('party_communication.msg_domain_all'), '[]', False))
        cls._get_window_domains_cache.set(action.id, domains)
        return domains


class Case(ModelSQL, ModelView):
    "Case"
    __name__ = 'party.communication.case'

    name = fields.Char("Name", required=True)
    description = fields.Text("Description")
    party = fields.Many2One('party.party', "Party")
    reference = fields.Reference("Reference", 'get_reference')
    start = fields.DateTime("Start")
    end = fields.DateTime("End")
    events = fields.One2Many('party.communication.event', 'case', "Events")
    # works: One2Many function to linked party.communication.work.effort
    status = fields.Many2One(
        'party.communication.case.status', "Status", required=True)

    @classmethod
    def default_status(cls):
        pool = Pool()
        CaseStatus = pool.get('party.communication.case.status')
        return CaseStatus.get_default_status()

    @classmethod
    def _get_reference(cls):
        return []

    @classmethod
    def get_reference(cls):
        IrModel = Pool().get('ir.model')
        get_name = IrModel.get_name
        models = cls._get_reference()
        return [(None, '')] + [(m, get_name(m)) for m in models]


class EventParty(ModelSQL):
    "Event - Party"
    __name__ = 'party.communication.event-party.party'

    event = fields.Many2One(
        'party.communication.event', "Event", required=True,
        ondelete='CASCADE')
    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE')


class EventContact(ModelSQL):
    "Event - Contact"
    __name__ = 'party.communication.event-party.contact_mechanism'

    event = fields.Many2One(
        'party.communication.event', "Event", required=True,
        ondelete='CASCADE')
    contact_mechanism = fields.Many2One(
        'party.contact_mechanism', "Contact Mechanism", required=True,
        ondelete='CASCADE')


class Event(ModelSQL, ModelView):
    "Event"
    __name__ = 'party.communication.event'

    company = fields.Many2One('company.company', "Company", required=True)
    parties = fields.Many2Many(
        'party.communication.event-party.party', 'event', 'party', "Parties")
    type = fields.Selection('get_types', "Type", required=True)
    contacts = fields.Many2Many(
        'party.communication.event-party.contact_mechanism', 'event',
        'contact_mechanism', "Contact Mechanisms",
        domain=[
            ('party', 'in', Eval('parties', [-1])),
            ('type', '=', Eval('type')),
            ])
    case = fields.Many2One('party.communication.case', "Case",
        domain=[
            ('party', 'in', Eval('parties', [-1])),
            ])
    reference = fields.Function(
        fields.Reference("Reference", 'get_reference',
        states={
            'readonly': Bool(Eval('case', 0)),
            }),
        'on_change_with_reference', setter='set_reference',
        searcher='search_reference')
    start = fields.DateTime("Start", required=True)
    end = fields.DateTime("End",
        states={
            'required': Eval('state') == 'completed',
            })
    purpose = fields.Many2One('party.communication.event.purpose', "Purpose")
    note = fields.Text("Note")
    # follow up: One2Many to party.communication.work.effort
    state = fields.Selection([
        ('scheduled', "Scheduled"),
        ('in progress', "In progress"),
        ('completed', "Completed"),
        ('cancelled', "Cancelled"),
        ], "State", required=True)

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_parties(cls):
        pool = Pool()
        Employee = pool.get('company.employee')
        context = Transaction().context
        parties = context.get('event_parties', [])
        employee_id = context.get('employee')
        if employee_id:
            employee = Employee(employee_id)
            parties.append(employee.party.id)
        return parties

    @classmethod
    def default_state(cls):
        return 'scheduled'

    @classmethod
    def get_types(cls):
        pool = Pool()
        Mechanism = pool.get('party.contact_mechanism')
        return Mechanism.fields_get(['type'])['type']['selection']

    @classmethod
    def get_reference(cls):
        pool = Pool()
        Case = pool.get('party.communication.case')
        return Case.get_reference()

    def get_case(self, reference):
        pool = Pool()
        Case = pool.get('party.communication.case')
        if not reference or not self.parties:
            return
        case = Case()
        case.start = self.start
        case.party = self.parties[0]
        case.reference = reference
        case.name = reference
        try:
            model, id_ = reference.split(',')
            Model = pool.get(model)
            record = Model(id_)
            case.name = record.rec_name
        except (ValueError, KeyError):
            pass
        return case

    @fields.depends('case', '_parent_case.reference')
    def on_change_with_reference(self, name=None):
        if self.case and self.case.reference:
            return str(self.case.reference)

    @classmethod
    def set_reference(cls, records, name, value):
        pool = Pool()
        Case = pool.get('party.communication.case')
        to_update, cases = [], []
        for record in records:
            if record.case:
                continue
            case = record.get_case(value)
            if case:
                to_update.append(record)
                cases.append(case)
        if cases:
            Case.save(cases)
            for record, case in zip(to_update, cases):
                record.case = case
            cls.save(to_update)

    @classmethod
    def search_reference(cls, name, clause):
        field_name = 'case.reference'
        nested = clause[0][len(name):]
        if nested:
            field_name += nested
        return [(field_name,) + tuple(clause[1:])]

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('state') == 'cancelled', 'muted', '')),
            ]


class Case_Invoice(metaclass=PoolMeta):
    __name__ = 'party.communication.case'

    @classmethod
    def _get_reference(cls):
        references = super()._get_reference()
        references.append('account.invoice')
        return references


class Case_Purchase(metaclass=PoolMeta):
    __name__ = 'party.communication.case'

    @classmethod
    def _get_reference(cls):
        references = super()._get_reference()
        references.append('purchase.purchase')
        return references


class Case_PurchaseRequestQuotation(metaclass=PoolMeta):
    __name__ = 'party.communication.case'

    @classmethod
    def _get_reference(cls):
        references = super()._get_reference()
        references.append('purchase.request.quotation')
        return references


class Case_Sale(metaclass=PoolMeta):
    __name__ = 'party.communication.case'

    @classmethod
    def _get_reference(cls):
        references = super()._get_reference()
        references.append('sale.sale')
        return references


class Case_SaleComplaint(metaclass=PoolMeta):
    __name__ = 'party.communication.case'

    @classmethod
    def _get_reference(cls):
        references = super()._get_reference()
        references.append('sale.complaint')
        return references


class Case_SaleOpportunity(metaclass=PoolMeta):
    __name__ = 'party.communication.case'

    @classmethod
    def _get_reference(cls):
        references = super()._get_reference()
        references.append('sale.opportunity')
        return references


class Case_SaleSubscription(metaclass=PoolMeta):
    __name__ = 'party.communication.case'

    @classmethod
    def _get_reference(cls):
        references = super()._get_reference()
        references.append('sale.subscription')
        return references

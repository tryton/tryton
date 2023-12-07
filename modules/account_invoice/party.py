# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.modules.party.exceptions import EraseError
from trytond.pool import Pool, PoolMeta

customer_payment_term = fields.Many2One(
    'account.invoice.payment_term', "Customer Payment Term",
    ondelete='RESTRICT')
supplier_payment_term = fields.Many2One(
    'account.invoice.payment_term', "Supplier Payment Term",
    ondelete='RESTRICT')


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'
    invoice = fields.Boolean('Invoice')


class ContactMechanism(metaclass=PoolMeta):
    __name__ = 'party.contact_mechanism'
    invoice = fields.Boolean('Invoice')

    @classmethod
    def usages(cls, _fields=None):
        if _fields is None:
            _fields = []
        _fields.append('invoice')
        return super(ContactMechanism, cls).usages(_fields=_fields)


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    customer_payment_term = fields.MultiValue(customer_payment_term)
    supplier_payment_term = fields.MultiValue(supplier_payment_term)
    payment_terms = fields.One2Many(
        'party.party.payment_term', 'party', "Payment Terms")

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'customer_payment_term', 'supplier_payment_term'}:
            return pool.get('party.party.payment_term')
        return super(Party, cls).multivalue_model(field)

    @classmethod
    def default_customer_payment_term(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        payment_term = config.get_multivalue(
            'default_customer_payment_term', **pattern)
        return payment_term.id if payment_term else None


class PartyPaymentTerm(ModelSQL, ValueMixin):
    "Party Payment Term"
    __name__ = 'party.party.payment_term'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE')
    customer_payment_term = customer_payment_term
    supplier_payment_term = supplier_payment_term


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.invoice', 'party'),
            ('account.invoice.line', 'party'),
            ('account.invoice.alternative_payee', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        super().check_erase_company(party, company)

        invoices = Invoice.search([
                ['OR',
                    ('party', '=', party.id),
                    ('alternative_payees', '=', party.id),
                    ],
                ('company', '=', company.id),
                ('state', 'not in', ['paid', 'cancelled']),
                ])
        if invoices:
            raise EraseError(
                gettext('account_invoice.msg_erase_party_pending_invoice',
                    party=party.rec_name,
                    company=company.rec_name))

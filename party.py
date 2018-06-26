# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelView, ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta
from trytond.tools.multivalue import migrate_property

__all__ = ['Address', 'Party', 'PartyPaymentTerm',
    'PartyReplace', 'PartyErase']
customer_payment_term = fields.Many2One(
    'account.invoice.payment_term', "Customer Payment Term")
supplier_payment_term = fields.Many2One(
    'account.invoice.payment_term', "Supplier Payment Term")


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


class Party(ModelSQL, ModelView):
    __name__ = 'party.party'
    customer_payment_term = fields.MultiValue(customer_payment_term)
    supplier_payment_term = fields.MultiValue(supplier_payment_term)
    payment_terms = fields.One2Many(
        'party.party.payment_term', 'party', "Payment Terms")

    @classmethod
    def __register__(cls, module_name):
        ModelField = Pool().get('ir.model.field')

        # Migration from 2.2: property field payment_term renamed
        # to customer_payment_term
        fields = ModelField.search([
                ('name', '=', 'payment_term'),
                ('model.model', '=', 'party.party')
                ])
        if fields:
            ModelField.write(fields, {
                    'name': 'customer_payment_term',
                    })

        super(Party, cls).__register__(module_name)

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'customer_payment_term', 'supplier_payment_term'}:
            return pool.get('party.party.payment_term')
        return super(Party, cls).multivalue_model(field)


class PartyPaymentTerm(ModelSQL, ValueMixin):
    "Party Payment Term"
    __name__ = 'party.party.payment_term'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    customer_payment_term = customer_payment_term
    supplier_payment_term = supplier_payment_term

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(PartyPaymentTerm, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(['customer_payment_term', 'supplier_payment_term'])
        value_names.extend(['customer_payment_term', 'supplier_payment_term'])
        migrate_property(
            'party.party', field_names, cls, value_names,
            parent='party', fields=fields)


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('account.invoice', 'party'),
            ('account.invoice.line', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    @classmethod
    def __setup__(cls):
        super(PartyErase, cls).__setup__()
        cls._error_messages.update({
                'pending_invoice': (
                    'The party "%(party)s" can not be erased '
                    'because he has pending invoices '
                    'for the company "%(company)s".'),
                })

    def check_erase_company(self, party, company):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        super(PartyErase, self).check_erase_company(party, company)

        invoices = Invoice.search([
                ('party', '=', party.id),
                ('state', 'not in', ['paid', 'cancel']),
                ])
        if invoices:
            self.raise_user_error('pending_invoice', {
                    'party': party.rec_name,
                    'company': company.rec_name,
                    })

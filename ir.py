# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.tools import escape_wildcard
from trytond.transaction import Transaction


class Email(metaclass=PoolMeta):
    __name__ = 'ir.email'

    @classmethod
    def _match(cls, name, email):
        pool = Pool()
        ContactMechanism = pool.get('party.contact_mechanism')
        yield from super()._match(name, email)
        domain = ['OR']
        for field in ['name', 'party.name', 'value']:
            for value in [name, email]:
                if value and len(value) >= 3:
                    domain.append(
                        (field, 'ilike', '%' + escape_wildcard(value) + '%'))
        for contact in ContactMechanism.search([
                    ('type', '=', 'email'),
                    ('value', '!=', ''),
                    domain,
                    ], order=[]):
            yield contact.name or contact.party.name, contact.value


class EmailTemplate(metaclass=PoolMeta):
    __name__ = 'ir.email.template'

    contact_mechanism = fields.Selection(
        'get_contact_mechanisms', "Contact Mechanism",
        help="Define which email address to use "
        "from the party's contact mechanisms.")

    @classmethod
    def get_contact_mechanisms(cls):
        pool = Pool()
        ContactMechanism = pool.get('party.contact_mechanism')
        return ContactMechanism.usages()

    def get(self, record):
        with Transaction().set_context(usage=self.contact_mechanism):
            return super().get(record)

    @classmethod
    def email_models(cls):
        return super().email_models() + ['party.party']

    @classmethod
    def _get_address(cls, record):
        pool = Pool()
        Party = pool.get('party.party')
        address = super()._get_address(record)
        if isinstance(record, Party):
            usage = Transaction().context.get('usage')
            contact = record.contact_mechanism_get('email', usage=usage)
            if contact and contact.email:
                address = (contact.name or record.name, contact.email)
        return address

    @classmethod
    def _get_language(cls, record):
        pool = Pool()
        Party = pool.get('party.party')
        language = super()._get_language(record)
        if isinstance(record, Party) and record.lang:
            language = record.lang
        return language

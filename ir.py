# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.tools import escape_wildcard


class Email(metaclass=PoolMeta):
    __name__ = 'ir.email'

    @classmethod
    def _match(cls, name, email):
        pool = Pool()
        User = pool.get('web.user')
        yield from super()._match(name, email)
        domain = ['OR']
        for field in ['party.name', 'value']:
            for value in [name, email]:
                if value and len(value) >= 3:
                    domain.append(
                        (field, 'ilike', '%' + escape_wildcard(value) + '%'))
        for user in User.search([
                    ('email', '!=', ''),
                    domain,
                    ], order=[]):
            yield user.party.name if user.party else '', user.email


class EmailTemplate(metaclass=PoolMeta):
    __name__ = 'ir.email.template'

    @classmethod
    def email_models(cls):
        return super().email_models() + ['web.user']

    @classmethod
    def _get_address(cls, record):
        pool = Pool()
        User = pool.get('web.user')
        address = super()._get_address(record)
        if isinstance(record, User):
            name = None
            if record.party:
                name = record.party.name
            address = (name, record.email)
        return address

    @classmethod
    def _get_language(cls, record):
        pool = Pool()
        User = pool.get('web.user')
        language = super()._get_language(record)
        if isinstance(record, User):
            if record.party:
                language = cls._get_language(record.party)
        return language

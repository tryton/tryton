# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


class EmailTemplate(metaclass=PoolMeta):
    __name__ = 'ir.email.template'

    @classmethod
    def email_models(cls):
        return super().email_models() + ['commission.agent']

    @classmethod
    def _get_address(cls, record):
        pool = Pool()
        Agent = pool.get('commission.agent')
        address = super()._get_address(record)
        if isinstance(record, Agent):
            address = cls._get_address(record.party)
        return address

    @classmethod
    def _get_language(cls, record):
        pool = Pool()
        Agent = pool.get('commission.agent')
        language = super()._get_language(record)
        if isinstance(record, Agent):
            language = cls._get_language(record.party)
        return language

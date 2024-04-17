# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond import backend
from trytond.model import ModelSQL, ModelView, dualmethod, fields
from trytond.pool import Pool, PoolMeta
from trytond.tools import timezone as tz
from trytond.transaction import Transaction


class Sequence(metaclass=PoolMeta):
    __name__ = 'ir.sequence'
    company = fields.Many2One(
        'company.company', "Company",
        help="Restricts the sequence usage to the company.")

    @classmethod
    def __setup__(cls):
        super(Sequence, cls).__setup__()
        cls._order.insert(0, ('company', 'ASC'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class SequenceStrict(Sequence):
    __name__ = 'ir.sequence.strict'


class Date(metaclass=PoolMeta):
    __name__ = 'ir.date'

    @classmethod
    def today(cls, timezone=None):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if timezone is None and company_id:
            company = Company(company_id)
            if company.timezone:
                timezone = tz.ZoneInfo(company.timezone)
        return super(Date, cls).today(timezone=timezone)


class Rule(metaclass=PoolMeta):
    __name__ = 'ir.rule'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.domain.help += (
            '\n- "companies" as list of ids from the current user')

    @classmethod
    def _get_cache_key(cls, model_names):
        pool = Pool()
        User = pool.get('res.user')
        key = super()._get_cache_key(model_names)
        return (*key, User.get_companies())

    @classmethod
    def _get_context(cls, model_name):
        pool = Pool()
        User = pool.get('res.user')
        context = super()._get_context(model_name)
        context['companies'] = User.get_companies()
        return context


class Cron(metaclass=PoolMeta):
    __name__ = "ir.cron"
    companies = fields.Many2Many('ir.cron-company.company', 'cron', 'company',
            'Companies', help='Companies registered for this cron.')

    @dualmethod
    @ModelView.button
    def run_once(cls, crons):
        for cron in crons:
            if not cron.companies:
                super(Cron, cls).run_once([cron])
            else:
                for company in cron.companies:
                    with Transaction().set_context(company=company.id):
                        super(Cron, cls).run_once([cron])

    @staticmethod
    def default_companies():
        Company = Pool().get('company.company')
        return list(map(int, Company.search([])))


class CronCompany(ModelSQL):
    'Cron - Company'
    __name__ = 'ir.cron-company.company'
    cron = fields.Many2One(
        'ir.cron', "Cron", ondelete='CASCADE', required=True)
    company = fields.Many2One(
        'company.company', "Company", ondelete='CASCADE', required=True)

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename('cron_company_rel', cls._table)
        super().__register__(module)


class EmailTemplate(metaclass=PoolMeta):
    __name__ = 'ir.email.template'

    @classmethod
    def email_models(cls):
        return super().email_models() + ['company.employee']

    @classmethod
    def _get_address(cls, record):
        pool = Pool()
        Employee = pool.get('company.employee')
        address = super()._get_address(record)
        if isinstance(record, Employee):
            address = cls._get_address(record.party)
        return address

    @classmethod
    def _get_language(cls, record):
        pool = Pool()
        Employee = pool.get('company.employee')
        language = super()._get_language(record)
        if isinstance(record, Employee):
            language = cls._get_language(record.party)
        return language

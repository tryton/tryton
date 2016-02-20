# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


__all__ = ['Cron', 'CronCompany']


class Cron:
    __metaclass__ = PoolMeta
    __name__ = "ir.cron"
    companies = fields.Many2Many('ir.cron-company.company', 'cron', 'company',
            'Companies', help='Companies registered for this cron')

    @classmethod
    def _callback(cls, cron):
        User = Pool().get('res.user')
        if not cron.companies:
            return super(Cron, cls)._callback(cron)
        # TODO replace with context
        for company in cron.companies:
            User.write([cron.user], {
                    'company': company.id,
                    'main_company': company.id,
                    })
            with Transaction().set_context(company=company.id):
                super(Cron, cls)._callback(cron)
        User.write([cron.user], {
                'company': None,
                'main_company': None,
                })

    @staticmethod
    def default_companies():
        Company = Pool().get('company.company')
        return map(int, Company.search([]))


class CronCompany(ModelSQL):
    'Cron - Company'
    __name__ = 'ir.cron-company.company'
    _table = 'cron_company_rel'
    cron = fields.Many2One('ir.cron', 'Cron', ondelete='CASCADE',
            required=True, select=True)
    company = fields.Many2One('company.company', 'Company', ondelete='CASCADE',
            required=True, select=True)

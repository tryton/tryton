#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool


class Cron(ModelSQL, ModelView):
    "Cron"
    _name = "ir.cron"
    companies = fields.Many2Many('ir.cron-company.company', 'cron', 'company',
            'Companies', help='Companies registered for this cron')

    def _callback(self, cron):
        user_obj = Pool().get('res.user')
        if not cron.companies:
            return super(Cron, self)._callback(cron)
        # TODO replace with context
        for company in cron.companies:
            user_obj.write(cron.user.id, {
                'company': company.id,
                'main_company': company.id,
            })
            super(Cron, self)._callback(cron)
        user_obj.write(cron.user.id, {
            'company': None,
            'main_company': None,
        })

    def default_companies(self):
        company_obj = Pool().get('company.company')
        return company_obj.search([])

Cron()


class CronCompany(ModelSQL):
    'Cron - Company'
    _name = 'ir.cron-company.company'
    _table = 'cron_company_rel'
    cron = fields.Many2One('ir.cron', 'Cron', ondelete='CASCADE',
            required=True, select=True)
    company = fields.Many2One('company.company', 'Company', ondelete='CASCADE',
            required=True, select=True)

CronCompany()

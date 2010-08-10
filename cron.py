#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction

class Cron(ModelSQL, ModelView):
    "Cron"
    _name = "ir.cron"
    companies = fields.Many2Many('ir.cron-company.company', 'cron', 'company',
            'Companies', help='Companies registered for this cron')

    def _callback(self, cron):
        cursor = Transaction().cursor
        cursor.execute("SELECT company from cron_company_rel "
                       "WHERE cron = %s", (cron['id'],))
        for company, in cursor.fetchall():
            cursor.execute(
                "UPDATE res_user SET company = %s, main_company = %s "
                "WHERE id = %s", (company, company, cron['user']))
            super(Cron, self)._callback(cron)
        cursor.execute(
            "UPDATE res_user SET company = NULL, main_company = NULL "
            "WHERE id = %s", (cron['user'],))

    def default_companies(self):
        company_obj = self.pool.get('company.company')
        return company_obj.search([])

Cron()


class CronCompany(ModelSQL):
    'Cron - Company'
    _name = 'ir.cron-company.company'
    _table = 'cron_company_rel'
    cron = fields.Many2One('ir.cron', 'Cron', ondelete='CASCADE',
            required=True, select=1)
    company = fields.Many2One('company.company', 'Company', ondelete='CASCADE',
            required=True, select=1)

CronCompany()
